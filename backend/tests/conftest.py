import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import DEFAULT_DEV_API_KEY
from app.db import Base, get_db
from app.main import app
from app.ratelimit import rate_limiter
from app.models import Transaction

@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    """Tests must not depend on environment variables set on your machine."""
    monkeypatch.setattr("app.auth.API_KEYS", [DEFAULT_DEV_API_KEY])
    monkeypatch.setattr(rate_limiter, "limit", 1000)
    rate_limiter.reset()
    yield
    rate_limiter.reset()


@pytest.fixture
def session_factory():
    """A fresh in-memory SQLite database for every test."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine, tables=[Transaction.__table__])
    return sessionmaker(bind=engine, autoflush=False)


@pytest.fixture
def _override_db(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


# No "with" on TestClient, so startup code is skipped and no real Postgres is needed.
@pytest.fixture
def client(_override_db):
    """A client that is logged in with the dev API key."""
    return TestClient(app, headers={"X-API-Key": DEFAULT_DEV_API_KEY})


@pytest.fixture
def anon_client(_override_db):
    """A client with no API key."""
    return TestClient(app)