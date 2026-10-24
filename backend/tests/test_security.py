import pytest
from fastapi import HTTPException

from app.ratelimit import RateLimiter, rate_limiter


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_no_api_key_is_401(anon_client):
    assert anon_client.get("/transactions").status_code == 401


def test_wrong_api_key_is_401(anon_client):
    response = anon_client.get("/transactions", headers={"X-API-Key": "nope"})
    assert response.status_code == 401
    assert "Invalid" in response.text


def test_unauthenticated_caller_gets_401_not_validation_details(anon_client):
    response = anon_client.post("/transactions/score", json={})
    assert response.status_code == 401


def test_auth_check_works_with_valid_key(client):
    response = client.get("/auth/check")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_is_public(anon_client):
    assert anon_client.get("/health").status_code == 200


def test_limiter_blocks_after_limit_then_recovers():
    clock = FakeClock()
    limiter = RateLimiter(limit_per_minute=2, clock=clock)
    limiter.check("a")
    limiter.check("a")
    with pytest.raises(HTTPException) as error:
        limiter.check("a")
    assert error.value.status_code == 429
    assert int(error.value.headers["Retry-After"]) >= 1
    clock.now += 61
    limiter.check("a")  # allowed again after the window


def test_limiter_is_per_client():
    limiter = RateLimiter(limit_per_minute=1, clock=FakeClock())
    limiter.check("a")
    limiter.check("b")  # a different client is not affected
    with pytest.raises(HTTPException):
        limiter.check("a")


def test_api_returns_429_with_retry_after(client, monkeypatch):
    monkeypatch.setattr(rate_limiter, "limit", 2)
    assert client.get("/transactions").status_code == 200
    assert client.get("/transactions").status_code == 200
    third = client.get("/transactions")
    assert third.status_code == 429
    assert "Retry-After" in third.headers