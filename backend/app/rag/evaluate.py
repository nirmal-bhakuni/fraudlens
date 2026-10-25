"""Score retrieval on the question set. No LLM is called, so it costs no API quota.

Run from the backend folder, with the database up and the documents ingested:
    python -m app.rag.evaluate
To try another cutoff without editing .env:
    $env:RAG_MIN_SCORE = "0.35"; python -m app.rag.evaluate
"""
import argparse
import sys

from sqlalchemy import func, select

from app.config import BASE_DIR, KNOWLEDGE_DIR, RAG_MIN_SCORE, RAG_TOP_K
from app.db import SessionLocal
from app.rag.eval_metrics import Retrieved, judge, load_questions, recommend_cutoff, summarize, sweep
from app.rag.models import DocumentChunk
from app.rag.search import search

QUESTIONS_FILE = BASE_DIR / "eval" / "questions.json"
CUTOFFS = [round(0.10 + 0.05 * i, 2) for i in range(11)]  # 0.10 ... 0.60


def pct(value: float) -> str:
    return f"{100 * value:5.1f}%"


def show(title: str, s: dict) -> None:
    print(
        f"  {title:<30} pass {pct(s['pass_rate'])} ({s['questions']:>2} q) | "
        f"answerable {pct(s['answerable_pass_rate'])} ({s['answerable']:>2}) | "
        f"refused right {pct(s['refusal_rate'])} ({s['unanswerable']}) | "
        f"hit@1 {pct(s['hit_at_1'])} | MRR {s['mrr']:.2f}"
    )


def main(min_pass: float) -> None:
    from app.rag.embedder import embed  # loads the embedding model

    questions = load_questions(QUESTIONS_FILE)
    docs = {path.name for path in KNOWLEDGE_DIR.glob("*.md")}
    missing = sorted({s for q in questions for s in q.expected_sources} - docs)
    if missing:
        sys.exit(f"Questions expect documents that do not exist: {missing}")

    with SessionLocal() as db:
        stored = set(db.scalars(select(DocumentChunk.source).distinct()))
        if not stored:
            sys.exit("No chunks stored. Run: python -m app.rag.ingest")
        if stored != docs:
            sys.exit("The stored documents differ from the knowledge folder. Run: python -m app.rag.ingest")
        vectors = embed([q.question for q in questions])
        retrieved = {
            q.id: [Retrieved(h.source, h.score) for h in search(db, vector, k=RAG_TOP_K)]
            for q, vector in zip(questions, vectors)
        }

    cutoff = RAG_MIN_SCORE
    outcomes = [judge(q, retrieved[q.id], cutoff) for q in questions]
    print(f"\nQuestions: {len(questions)}   cutoff in use: {cutoff}   top-k: {RAG_TOP_K}")
    show("ALL", summarize(outcomes))
    for split in ("dev", "test"):
        show(split.upper(), summarize([o for o in outcomes if o.question.split == split]))

    failed = [o for o in outcomes if not o.passed]
    print(f"\nFailed at cutoff {cutoff}: {len(failed)}")
    for outcome in failed:
        q = outcome.question
        top = ", ".join(f"{r.source} {r.score:.2f}" for r in retrieved[q.id][:2]) or "nothing"
        wanted = ", ".join(q.expected_sources) or "REFUSE"
        print(f"  {q.id} [{q.split}] {q.question}\n      expected: {wanted}\n      top hits: {top}")

    rows = sweep(questions, retrieved, CUTOFFS, "dev")
    best = recommend_cutoff(rows)
    print("\nCutoff sweep on the DEV questions only:")
    for value, rate in rows:
        marker = "  <-- in use" if abs(value - cutoff) < 1e-9 else ""
        print(f"  {value:.2f}   pass {pct(rate)}{marker}")
    print(f"Best cutoff on dev: {best}")

    print("\nTEST questions (never used to choose the cutoff):")
    test_questions = [q for q in questions if q.split == "test"]
    for label, value in (("in use", cutoff), ("best on dev", best)):
        show(f"cutoff {value} ({label})", summarize([judge(q, retrieved[q.id], value) for q in test_questions]))
    print("\nReminder: about 22 questions per split. One question moves a score by ~4.5 points.")

    test_pass = summarize([o for o in outcomes if o.question.split == "test"])["pass_rate"]
    if test_pass < min_pass:
        sys.exit(f"Test pass rate {test_pass:.3f} is below --min-pass {min_pass}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-pass", type=float, default=0.0, help="exit with an error below this test pass rate")
    main(parser.parse_args().min_pass)