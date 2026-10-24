from fastapi.testclient import TestClient

from app.main import app
from app.models import Transaction
from app.routers import transactions as transactions_module
from score_helpers import GOOD, post_score


def test_same_key_same_body_returns_saved_result_and_one_row(client, session_factory):
    first = post_score(client, GOOD, key="abc-123")
    second = post_score(client, GOOD, key="abc-123")
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.headers["Idempotent-Replay"] == "true"
    assert second.json() == first.json()
    with session_factory() as db:
        assert db.query(Transaction).count() == 1


def test_same_key_different_body_is_409(client, session_factory):
    post_score(client, GOOD, key="k1")
    response = post_score(client, {**GOOD, "amount": 99.0}, key="k1")
    assert response.status_code == 409
    with session_factory() as db:
        assert db.query(Transaction).count() == 1


def test_different_keys_make_different_rows(client, session_factory):
    a = post_score(client, GOOD, key="k-a").json()
    b = post_score(client, GOOD, key="k-b").json()
    assert a["id"] != b["id"]
    with session_factory() as db:
        assert db.query(Transaction).count() == 2


def test_missing_idempotency_key_is_rejected(client):
    response = client.post("/transactions/score", json=GOOD)
    assert response.status_code == 422
    assert "Idempotency-Key" in response.text


def test_race_is_caught_by_the_database(client, session_factory, monkeypatch):
    """Simulate two requests with the same key at the same moment.

    The first lookup says "not found" (as if the other request had not saved yet).
    The insert then hits the unique constraint, and we return the saved result.
    """
    first = post_score(client, GOOD, key="race-1")

    real_find = transactions_module.find_existing
    calls = {"n": 0}

    def flaky_find(db, client_id, key):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_find(db, client_id, key)

    monkeypatch.setattr(transactions_module, "find_existing", flaky_find)

    second = post_score(client, GOOD, key="race-1")
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    with session_factory() as db:
        assert db.query(Transaction).count() == 1


def test_same_key_from_two_clients_does_not_collide(client, session_factory, monkeypatch):
    monkeypatch.setattr("app.auth.API_KEYS", ["dev-key-change-me", "other-key"])
    other = TestClient(app, headers={"X-API-Key": "other-key"})

    a = post_score(client, GOOD, key="shared-key")
    b = post_score(other, GOOD, key="shared-key")
    assert a.status_code == 201
    assert b.status_code == 201
    assert a.json()["id"] != b.json()["id"]
    with session_factory() as db:
        assert db.query(Transaction).count() == 2