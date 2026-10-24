"""Transaction endpoints."""
import hashlib
from datetime import date, datetime, time, timedelta
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_client
from app.db import get_db
from app.ml.features import build_features
from app.ml.scorer import Scorer, get_scorer
from app.models import Transaction
from app.rules import apply_rules, check_rules
from app.schemas import Decision, ScoreOut, TransactionIn, TransactionOut, TransactionPage

router = APIRouter(prefix="/transactions", tags=["transactions"])

IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=100)]


def find_existing(db: Session, client_id: str, key: str) -> Transaction | None:
    return db.scalar(
        select(Transaction).where(
            Transaction.client_id == client_id,
            Transaction.idempotency_key == key,
        )
    )


def to_score_out(row: Transaction) -> ScoreOut:
    return ScoreOut(
        id=row.id,
        risk_score=round(row.risk_score, 4),
        decision=row.decision,
        rules_triggered=row.rules_triggered,
        model_version=row.model_version,
    )


def replay(existing: Transaction, request_hash: str, response: Response) -> ScoreOut:
    """Same key again: give back the saved answer, or 409 if the body is different."""
    if existing.request_hash != request_hash:
        raise HTTPException(
            status_code=409,
            detail="This Idempotency-Key was already used with a different request body.",
        )
    response.status_code = 200
    response.headers["Idempotent-Replay"] = "true"
    return to_score_out(existing)


# A normal "def" (not "async def") on purpose: XGBoost and SQLAlchemy block,
# so FastAPI runs this in a thread pool and other requests are not stuck.
@router.post("/score", response_model=ScoreOut, status_code=201)
def score_transaction(
    payload: TransactionIn,
    response: Response,
    idempotency_key: IdempotencyKey,
    client_id: str = Depends(require_client),
    db: Session = Depends(get_db),
    scorer: Scorer = Depends(get_scorer),
):
    request_hash = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()

    # Fast path: we already saw this key.
    existing = find_existing(db, client_id, idempotency_key)
    if existing is not None:
        return replay(existing, request_hash, response)

    # The model was trained on local clock times, so we drop any timezone info.
    trans_time = payload.timestamp.replace(tzinfo=None)

    raw = pd.DataFrame([{
        "trans_date_trans_time": trans_time,
        "amt": payload.amount,
        "category": payload.category,
        "lat": payload.lat,
        "long": payload.long,
        "merch_lat": payload.merchant_lat,
        "merch_long": payload.merchant_long,
        "city_pop": payload.city_pop,
    }])
    features = build_features(raw)

    risk_score = scorer.score(features)          # the ML model decides...
    model_decision = scorer.decide(risk_score)
    hits = check_rules(payload.amount, bool(features["is_night"].iloc[0]))
    decision = apply_rules(model_decision, hits)  # ...rules can only be stricter

    row = Transaction(
        client_id=client_id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        trans_time=trans_time,
        amount=payload.amount,
        category=payload.category,
        merchant=payload.merchant,
        lat=payload.lat,
        long=payload.long,
        merchant_lat=payload.merchant_lat,
        merchant_long=payload.merchant_long,
        city_pop=payload.city_pop,
        risk_score=risk_score,
        model_decision=model_decision,
        decision=decision,
        flagged=decision != "Approve",
        rules_triggered=hits,
        model_version=scorer.version,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Two requests with the same key arrived at the same time and the other one
        # won. The unique constraint caught it. Return the winner's saved result.
        db.rollback()
        existing = find_existing(db, client_id, idempotency_key)
        if existing is None:
            raise
        return replay(existing, request_hash, response)

    db.refresh(row)
    return to_score_out(row)


@router.get("", response_model=TransactionPage)
def list_transactions(
    client_id: str = Depends(require_client),
    db: Session = Depends(get_db),
    flagged: bool | None = None,
    decision: Decision | None = None,
    date_from: date | None = Query(default=None, description="Transaction date, inclusive"),
    date_to: date | None = Query(default=None, description="Transaction date, inclusive"),
    min_amount: float | None = Query(default=None, ge=0),
    max_amount: float | None = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        raise HTTPException(status_code=422, detail="min_amount cannot be greater than max_amount")
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from cannot be after date_to")

    conditions = [Transaction.client_id == client_id]  # a client only sees its own rows
    if flagged is not None:
        conditions.append(Transaction.flagged == flagged)
    if decision is not None:
        conditions.append(Transaction.decision == decision)
    if date_from is not None:
        conditions.append(Transaction.trans_time >= datetime.combine(date_from, time.min))
    if date_to is not None:
        # date_to is inclusive, so we stop at the start of the NEXT day.
        conditions.append(Transaction.trans_time < datetime.combine(date_to + timedelta(days=1), time.min))
    if min_amount is not None:
        conditions.append(Transaction.amount >= min_amount)
    if max_amount is not None:
        conditions.append(Transaction.amount <= max_amount)

    total = db.scalar(select(func.count()).select_from(Transaction).where(*conditions))
    rows = db.scalars(
        select(Transaction)
        .where(*conditions)
        .order_by(Transaction.trans_time.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return TransactionPage(
        items=[TransactionOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(
    transaction_id: int,
    client_id: str = Depends(require_client),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.client_id == client_id,
        )
    )
    if row is None:
        # Same answer for "does not exist" and "belongs to someone else".
        raise HTTPException(status_code=404, detail="Transaction not found")
    return TransactionOut.model_validate(row)