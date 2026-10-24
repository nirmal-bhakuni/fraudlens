import uuid
from datetime import datetime

from fastapi.testclient import TestClient

from app.auth import client_id_for
from app.config import DEFAULT_DEV_API_KEY
from app.main import app
from app.models import Transaction


def add_row(session_factory, client_id=None, **overrides):
    """Insert a row directly, so these tests do not depend on model output."""
    data = dict(
        client_id=client_id or client_id_for(DEFAULT_DEV_API_KEY),
        idempotency_key=str(uuid.uuid4()),
        request_hash="x",
        trans_time=datetime(2020, 12, 1, 10, 0),
        amount=10.0, category="home", merchant=None,
        lat=36.08, long=-81.18, merchant_lat=36.01, merchant_long=-82.05, city_pop=3495,
        risk_score=0.01, model_decision="Approve", decision="Approve", flagged=False,
        rules_triggered=[], model_version="1.0.0",
    )
    data.update(overrides)
    with session_factory() as db:
        row = Transaction(**data)
        db.add(row)
        db.commit()
        return row.id


def seed(session_factory):
    """Four rows. Returns their ids in this order: approve_dec, review, decline, approve_nov."""
    return [
        add_row(session_factory, amount=10.0, trans_time=datetime(2020, 12, 1, 10, 0)),
        add_row(session_factory, amount=500.0, trans_time=datetime(2020, 12, 15, 23, 0),
                decision="Review", flagged=True, risk_score=0.3),
        add_row(session_factory, amount=9000.0, trans_time=datetime(2020, 12, 30, 12, 0),
                decision="Decline", flagged=True, risk_score=0.95, rules_triggered=["high_amount"]),
        add_row(session_factory, amount=60.0, trans_time=datetime(2020, 11, 20, 9, 0)),
    ]


def amounts(response):
    return [item["amount"] for item in response.json()["items"]]


def test_list_returns_all_newest_first(client, session_factory):
    seed(session_factory)
    response = client.get("/transactions")
    assert response.status_code == 200
    assert response.json()["total"] == 4
    assert amounts(response) == [9000.0, 500.0, 10.0, 60.0]


def test_filter_flagged(client, session_factory):
    seed(session_factory)
    assert amounts(client.get("/transactions?flagged=true")) == [9000.0, 500.0]
    assert amounts(client.get("/transactions?flagged=false")) == [10.0, 60.0]


def test_filter_decision(client, session_factory):
    seed(session_factory)
    assert amounts(client.get("/transactions?decision=Decline")) == [9000.0]


def test_filter_dates_include_the_whole_last_day(client, session_factory):
    seed(session_factory)
    response = client.get("/transactions?date_from=2020-12-01&date_to=2020-12-15")
    assert amounts(response) == [500.0, 10.0]  # the 23:00 row on Dec 15 is included


def test_filter_amount_range(client, session_factory):
    seed(session_factory)
    response = client.get("/transactions?min_amount=50&max_amount=600")
    assert amounts(response) == [500.0, 60.0]


def test_pagination(client, session_factory):
    seed(session_factory)
    body = client.get("/transactions?limit=2&offset=2").json()
    assert body["total"] == 4
    assert len(body["items"]) == 2
    assert [i["amount"] for i in body["items"]] == [10.0, 60.0]


def test_bad_filters_give_clear_errors(client):
    assert client.get("/transactions?min_amount=10&max_amount=5").status_code == 422
    assert client.get("/transactions?date_from=2020-12-31&date_to=2020-12-01").status_code == 422
    assert client.get("/transactions?limit=1000").status_code == 422
    assert client.get("/transactions?date_from=not-a-date").status_code == 422
    assert client.get("/transactions?decision=Maybe").status_code == 422


def test_client_cannot_see_another_clients_rows(client, session_factory, monkeypatch):
    seed(session_factory)
    monkeypatch.setattr("app.auth.API_KEYS", ["dev-key-change-me", "other-key"])
    other = TestClient(app, headers={"X-API-Key": "other-key"})
    assert other.get("/transactions").json()["total"] == 0


def test_detail(client, session_factory):
    ids = seed(session_factory)
    response = client.get(f"/transactions/{ids[2]}")
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "Decline"
    assert body["timestamp"].startswith("2020-12-30")
    assert body["rules_triggered"] == ["high_amount"]


def test_detail_404_for_missing_and_for_other_client(client, session_factory, monkeypatch):
    ids = seed(session_factory)
    assert client.get("/transactions/99999").status_code == 404
    monkeypatch.setattr("app.auth.API_KEYS", ["dev-key-change-me", "other-key"])
    other = TestClient(app, headers={"X-API-Key": "other-key"})
    assert other.get(f"/transactions/{ids[0]}").status_code == 404