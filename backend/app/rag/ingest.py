"""Load knowledge documents into the database.

Run from the backend folder:   python -m app.rag.ingest
Running it again replaces all chunks, so it is safe to repeat.
"""
from pathlib import Path
from typing import Callable

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import KNOWLEDGE_DIR
from app.db import SessionLocal, init_db
from app.rag.documents import chunk_document, load_documents
from app.rag.models import DocumentChunk


def ingest(db: Session, embed_fn: Callable[[list[str]], list[list[float]]], docs_dir: Path) -> tuple[int, int]:
    """Replace all stored chunks. Returns (number of documents, number of chunks)."""
    documents = load_documents(docs_dir)
    pieces = [
        (doc, index, chunk)
        for doc in documents
        for index, chunk in enumerate(chunk_document(doc.body))
    ]
    # The title is part of the embedded text, so a chunk keeps its topic.
    vectors = embed_fn([f"{doc.title}\n{chunk}" for doc, _, chunk in pieces])

    db.execute(delete(DocumentChunk))
    db.add_all(
        DocumentChunk(source=doc.source, title=doc.title, chunk_index=index, text=chunk, embedding=vector)
        for (doc, index, chunk), vector in zip(pieces, vectors)
    )
    db.commit()
    return len(documents), len(pieces)


def main() -> None:
    from app.rag.embedder import embed

    init_db()
    with SessionLocal() as db:
        n_docs, n_chunks = ingest(db, embed, KNOWLEDGE_DIR)
    print(f"Ingested {n_docs} documents as {n_chunks} chunks from {KNOWLEDGE_DIR}")


if __name__ == "__main__":
    main()