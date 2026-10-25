"""FraudLens API entry point."""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import require_client
from app.config import API_KEYS, APP_ENV, DEFAULT_DEV_API_KEY
from app.db import get_db, init_db
from app.ml.scorer import get_scorer
from app.routers import explain, transactions


@asynccontextmanager
async def lifespan(app: FastAPI):
    if APP_ENV == "prod" and DEFAULT_DEV_API_KEY in API_KEYS:
        raise RuntimeError("Refusing to start in prod with the default dev API key. Set API_KEYS.")
    init_db()      # extension + tables
    get_scorer()   # load the model now, so a bad model fails at startup
    yield


app = FastAPI(title="FraudLens", version="0.4.0", lifespan=lifespan)
app.include_router(transactions.router)
app.include_router(explain.router)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))  # proves the database is reachable
    return {"status": "ok", "model_version": get_scorer().version}


@app.get("/auth/check")
def auth_check(client_id: str = Depends(require_client)):
    """The login screen calls this to see if an API key works."""
    return {"status": "ok", "client_id": client_id}