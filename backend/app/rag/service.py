"""The production retriever: embed the query, then search pgvector.

Tests replace get_retriever with a fake, so they need no model and no vector table.
"""
from typing import Callable

from app.db import SessionLocal
from app.rag.search import Hit, search


def retrieve(query: str) -> list[Hit]:
    from app.rag.embedder import embed  # loads the embedding model on first use

    with SessionLocal() as db:
        return search(db, embed([query])[0])


def get_retriever() -> Callable[[str], list[Hit]]:
    return retrieve