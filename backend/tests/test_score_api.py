from app.models import Transaction

GOOD = {
    "timestamp": "2020-12-30T13:15:00",
    "amount": 42.5,
    "category": "grocery_net",
    "merchant": "Test Shop",
    "lat": 36.08,
    "long": -81.18,
    "merchant_lat": 36.01,
    "merchant_long": -82.05,
    "city_pop": 3495,
}


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_score_returns_decision(client):
    response = client.post("/transactions/score", json=GOOD)
    assert response.status_code == 201
    body = response.json()
    assert 0.0 <= body["risk_score"] <= 1.0
    assert body["decision"] in ("Approve", "Review", "Decline")
    assert body["model_version"] == "1.0.0"
    assert body["id"] >= 1


def test_result_is_saved(client, session_factory):
    client.post("/transactions/score", json=GOOD)
    with session_factory() as db:
        rows = db.query(Transaction).all()
    assert len(rows) == 1
    assert rows[0].amount == 42.5
    assert rows[0].decision in ("Approve", "Review", "Decline")

def test_night_high_amount_online_scores_higher_than_ordinary_home_purchase(client):
    # Based on patterns seen in the training data (night, large, online shopping),
    # NOT on a general rule about fraud. The model learned simulated data.
    risky = {**GOOD, "timestamp": "2020-12-30T23:30:00", "amount": 1200.0, "category": "shopping_net"}
    ordinary = {**GOOD, "amount": 60.0, "category": "home"}  # GOOD is 13:15, daytime
    risky_score = client.post("/transactions/score", json=risky).json()["risk_score"]
    ordinary_score = client.post("/transactions/score", json=ordinary).json()["risk_score"]
    assert risky_score > ordinary_score, f"risky={risky_score}, ordinary={ordinary_score}"


def test_very_high_amount_is_never_approved(client):
    payload = {**GOOD, "amount": 20000.0}
    body = client.post("/transactions/score", json=payload).json()
    assert "high_amount" in body["rules_triggered"]
    assert body["decision"] in ("Review", "Decline")


def test_negative_amount_rejected(client):
    response = client.post("/transactions/score", json={**GOOD, "amount": -5})
    assert response.status_code == 422


def test_unknown_category_rejected_with_clear_message(client):
    response = client.post("/transactions/score", json={**GOOD, "category": "casino"})
    assert response.status_code == 422
    assert "grocery_net" in response.text  # the error lists the allowed values


def test_bad_latitude_rejected(client):
    response = client.post("/transactions/score", json={**GOOD, "lat": 200})
    assert response.status_code == 422


def test_missing_field_rejected(client):
    bad = {k: v for k, v in GOOD.items() if k != "amount"}
    response = client.post("/transactions/score", json=bad)
    assert response.status_code == 422