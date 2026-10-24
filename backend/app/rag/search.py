"""Find the knowledge chunks closest in meaning to a question."""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import RAG_TOP_K
from app.rag.models import DocumentChunk


@dataclass(frozen=True)
class Hit:
    source: str
    title: str
    chunk_index: int
    text: str
    score: float  # cosine similarity: 1.0 = same meaning, 0 = unrelated


def search(db: Session, query_embedding: list[float], k: int = RAG_TOP_K) -> list[Hit]:
    # <=> is pgvector's cosine distance. similarity = 1 - distance.
    distance = DocumentChunk.embedding.cosine_distance(query_embedding)
    rows = db.execute(
        select(
            DocumentChunk.source,
            DocumentChunk.title,
            DocumentChunk.chunk_index,
            DocumentChunk.text,
            distance.label("distance"),
        )
        .order_by(distance)
        .limit(k)
    ).all()
    return [
        Hit(source=r.source, title=r.title, chunk_index=r.chunk_index, text=r.text,
            score=round(1.0 - float(r.distance), 4))
        for r in rows
    ]