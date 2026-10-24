"""Ingest and search against the real Postgres + pgvector.

Everything happens inside a transaction that is rolled back, so your data is not touched.
The tests skip themselves if Postgres is not running.
A fake keyword embedder is used, so no model is downloaded.
"""
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db import engine, init_db
from app.rag.ingest import ingest
from app.rag.models import EMBEDDING_DIMS, DocumentChunk
from app.rag.search import search


def fake_embed(texts):
    """Three topics = three axes. 'night' -> axis 0, 'amount' -> axis 1, anything else -> axis 2."""
    vectors = []
    for t in texts:
        vector = [0.0] * EMBEDDING_DIMS
        low = t.lower()
        vector[0 if "night" in low else 1 if "amount" in low else 2] = 1.0
        vectors.append(vector)
    return vectors


@pytest.fixture
def pg_session():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError:
        pytest.skip("Postgres is not running (docker compose up -d db)")
    init_db()
    conn = engine.connect()
    outer = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()  # undo everything the test wrote
    conn.close()


@pytest.fixture
def docs_dir(tmp_path):
    (tmp_path / "night.md").write_text("# Night purchases\n\nRisky at night.", encoding="utf-8")
    (tmp_path / "amount.md").write_text("# Big amounts\n\nA large amount is a signal.", encoding="utf-8")
    (tmp_path / "other.md").write_text("# Something else\n\nNothing related.", encoding="utf-8")
    return tmp_path


def count_chunks(db):
    return db.scalar(select(func.count()).select_from(DocumentChunk))


def test_ingest_counts(pg_session, docs_dir):
    assert ingest(pg_session, fake_embed, docs_dir) == (3, 3)
    assert count_chunks(pg_session) == 3


def test_ingest_twice_does_not_duplicate(pg_session, docs_dir):
    ingest(pg_session, fake_embed, docs_dir)
    ingest(pg_session, fake_embed, docs_dir)
    assert count_chunks(pg_session) == 3


def test_search_returns_closest_chunk_first_with_source(pg_session, docs_dir):
    ingest(pg_session, fake_embed, docs_dir)
    hits = search(pg_session, fake_embed(["a question about night"])[0], k=3)
    assert hits[0].source == "night.md"
    assert hits[0].title == "Night purchases"
    assert hits[0].score == pytest.approx(1.0, abs=1e-3)
    assert hits[1].score == pytest.approx(0.0, abs=1e-3)  # unrelated topics are orthogonal


def test_search_respects_k(pg_session, docs_dir):
    ingest(pg_session, fake_embed, docs_dir)
    assert len(search(pg_session, fake_embed(["amount"])[0], k=2)) == 2


def test_search_on_empty_table_returns_nothing(pg_session):
    pg_session.execute(text("DELETE FROM document_chunks"))
    assert search(pg_session, fake_embed(["night"])[0]) == []