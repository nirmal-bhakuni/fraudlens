"""Transaction endpoints."""
import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.ml.features import build_features
from app.ml.scorer import Scorer, get_scorer
from app.models import Transaction
from app.rules import apply_rules, check_rules
from app.schemas import ScoreOut, TransactionIn

router = APIRouter(prefix="/transactions", tags=["transactions"])


# A normal "def" (not "async def") on purpose: XGBoost and SQLAlchemy block,
# so FastAPI runs this in a thread pool and other requests are not stuck.
@router.post("/score", response_model=ScoreOut, status_code=201)
def score_transaction(
    payload: TransactionIn,
    db: Session = Depends(get_db),
    scorer: Scorer = Depends(get_scorer),
):
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
    db.commit()
    db.refresh(row)

    return ScoreOut(
        id=row.id,
        risk_score=round(risk_score, 4),
        decision=decision,
        rules_triggered=hits,
        model_version=scorer.version,
    )