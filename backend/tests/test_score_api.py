from app.models import Transaction
from score_helpers import GOOD, post_score


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_score_returns_decision(client):
    response = post_score(client)
    assert response.status_code == 201
    body = response.json()
    assert 0.0 <= body["risk_score"] <= 1.0
    assert body["decision"] in ("Approve", "Review", "Decline")
    assert body["model_version"] == "1.0.0"
    assert body["id"] >= 1


def test_result_is_saved(client, session_factory):
    post_score(client, key="save-1")
    with session_factory() as db:
        rows = db.query(Transaction).all()
    assert len(rows) == 1
    assert rows[0].amount == 42.5
    assert rows[0].idempotency_key == "save-1"
    assert rows[0].client_id
    assert rows[0].decision in ("Approve", "Review", "Decline")


def test_night_high_amount_online_scores_higher_than_ordinary_home_purchase(client):
    # Based on patterns seen in the training data (night, large, online shopping),
    # NOT on a general rule about fraud. The model learned simulated data.
    risky = {**GOOD, "timestamp": "2020-12-30T23:30:00", "amount": 1200.0, "category": "shopping_net"}
    ordinary = {**GOOD, "amount": 60.0, "category": "home"}  # GOOD is 13:15, daytime
    risky_score = post_score(client, risky).json()["risk_score"]
    ordinary_score = post_score(client, ordinary).json()["risk_score"]
    assert risky_score > ordinary_score, f"risky={risky_score}, ordinary={ordinary_score}"


def test_very_high_amount_is_never_approved(client):
    body = post_score(client, {**GOOD, "amount": 20000.0}).json()
    assert "high_amount" in body["rules_triggered"]
    assert body["decision"] in ("Review", "Decline")


def test_negative_amount_rejected(client):
    assert post_score(client, {**GOOD, "amount": -5}).status_code == 422


def test_unknown_category_rejected_with_clear_message(client):
    response = post_score(client, {**GOOD, "category": "casino"})
    assert response.status_code == 422
    assert "grocery_net" in response.text  # the error lists the allowed values


def test_bad_latitude_rejected(client):
    assert post_score(client, {**GOOD, "lat": 200}).status_code == 422


def test_missing_field_rejected(client):
    bad = {k: v for k, v in GOOD.items() if k != "amount"}
    assert post_score(client, bad).status_code == 422