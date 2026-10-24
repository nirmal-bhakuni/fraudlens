"""Settings. Values come from environment variables, with safe local defaults."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]  # the backend folder

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://fraudlens:fraudlens@localhost:5433/fraudlens",
)
MODEL_VERSION = os.getenv("MODEL_VERSION", "1.0.0")
MODEL_DIR = Path(os.getenv("MODEL_DIR", BASE_DIR / "models"))