"""Load the saved model once and use it to score one transaction."""
import json
from functools import lru_cache
from pathlib import Path

import pandas as pd
import xgboost as xgb

from app.config import MODEL_DIR, MODEL_VERSION
from app.ml.features import FEATURE_COLUMNS


class Scorer:
    def __init__(self, model_dir: Path):
        meta = json.loads((model_dir / "metadata.json").read_text(encoding="utf-8"))
        if meta["features"] != FEATURE_COLUMNS:
            raise RuntimeError("Saved model features do not match features.py. Retrain the model.")
        self.model = xgb.XGBClassifier()
        self.model.load_model(str(model_dir / "model.json"))
        self.version = meta["model_version"]
        self.review_threshold = meta["thresholds"]["review"]
        self.decline_threshold = meta["thresholds"]["decline"]

    def score(self, features: pd.DataFrame) -> float:
        """Risk score from 0 to 1 for a one-row feature table."""
        return float(self.model.predict_proba(features)[0, 1])

    def decide(self, score: float) -> str:
        if score >= self.decline_threshold:
            return "Decline"
        if score >= self.review_threshold:
            return "Review"
        return "Approve"


@lru_cache
def get_scorer() -> Scorer:
    """Loaded once, then reused for every request."""
    return Scorer(MODEL_DIR / MODEL_VERSION)