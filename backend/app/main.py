"""FraudLens API entry point."""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models  # noqa: F401  (imported so the table is registered)
from app.db import Base, engine, get_db
from app.ml.scorer import get_scorer
from app.routers import transactions


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)  # create tables if missing
    get_scorer()                      # load the model now, so a bad model fails at startup
    yield


app = FastAPI(title="FraudLens", version="0.1.0", lifespan=lifespan)
app.include_router(transactions.router)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))  # proves the database is reachable
    return {"status": "ok", "model_version": get_scorer().version}