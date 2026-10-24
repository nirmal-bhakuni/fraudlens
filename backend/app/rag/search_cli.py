"""Try a question against the knowledge base.

Run from the backend folder:   python -m app.rag.search_cli "why is a night purchase risky"
"""
import sys

from app.config import RAG_MIN_SCORE
from app.db import SessionLocal
from app.rag.embedder import embed
from app.rag.search import search


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python -m app.rag.search_cli "your question"')
    question = " ".join(sys.argv[1:])
    with SessionLocal() as db:
        hits = search(db, embed([question])[0])
    print(f"Question: {question}   (cutoff = {RAG_MIN_SCORE})")
    if not hits:
        print("No chunks stored. Run: python -m app.rag.ingest")
    for hit in hits:
        verdict = "above cutoff" if hit.score >= RAG_MIN_SCORE else "BELOW cutoff"
        print(f"  {hit.score:6.3f}  {hit.source:28s} {verdict}")
        print(f"          {hit.text[:90]}...")


if __name__ == "__main__":
    main()