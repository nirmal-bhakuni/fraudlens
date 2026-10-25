"""'Ask why': explain a saved decision using the knowledge base and an LLM.

The ML model and the rules decide. This endpoint only explains. It never changes the transaction.
"""
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_client
from app.config import RAG_MIN_SCORE
from app.db import get_db
from app.llm import LLMError, get_llm
from app.models import Transaction
from app.rag.explain import (
    NO_INFO_ANSWER, SYSTEM_INSTRUCTION, build_prompt, build_query, is_no_info, relevant_hits,
)
from app.rag.search import Hit
from app.rag.service import get_retriever
from app.schemas import ExplainIn, ExplainOut, Source

router = APIRouter(prefix="/transactions", tags=["explain"])


def to_sources(hits: list[Hit]) -> list[Source]:
    return [Source(source=h.source, title=h.title, score=h.score, text=h.text) for h in hits]


# A normal "def" on purpose: the embedder, the database and the HTTP call all block,
# so FastAPI runs this in a thread pool.
@router.post("/{transaction_id}/explain", response_model=ExplainOut)
def explain_transaction(
    transaction_id: int,
    payload: ExplainIn | None = None,
    client_id: str = Depends(require_client),
    db: Session = Depends(get_db),
    retrieve: Callable[[str], list[Hit]] = Depends(get_retriever),
    llm: Any = Depends(get_llm),
):
    row = db.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.client_id == client_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    question = payload.question if payload else None
    query = build_query(question, row.reasons, row.rules_triggered)
    hits = relevant_hits(retrieve(query), RAG_MIN_SCORE)

    def out(answered: bool, answer: str, sources: list[Source], llm_model: str | None) -> ExplainOut:
        return ExplainOut(
            transaction_id=row.id, decision=row.decision, answered=answered,
            answer=answer, sources=sources, llm_model=llm_model,
        )

    if not hits:
        # Nothing relevant was found, so we do not call the LLM at all.
        return out(False, NO_INFO_ANSWER, [], None)

    prompt = build_prompt(
        row.decision, row.model_decision, row.risk_score,
        row.rules_triggered, row.reasons, hits, question,
    )
    try:
        result = llm.generate(SYSTEM_INSTRUCTION, prompt)
    except LLMError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from None

    if is_no_info(result.text):
        return out(False, result.text, [], result.model)
    return out(True, result.text, to_sources(hits), result.model)