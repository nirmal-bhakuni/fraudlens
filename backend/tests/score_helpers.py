"""Shared test data and helpers."""
import uuid

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


def post_score(client, payload=None, key=None):
    """POST a transaction. A fresh Idempotency-Key is made unless one is given."""
    return client.post(
        "/transactions/score",
        json=GOOD if payload is None else payload,
        headers={"Idempotency-Key": key or str(uuid.uuid4())},
    )