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

# "dev" or "prod". In prod the app refuses to start with the default API key.
APP_ENV = os.getenv("APP_ENV", "dev")
DEFAULT_DEV_API_KEY = "dev-key-change-me"
# Comma separated list, e.g. API_KEYS="key-one,key-two"
API_KEYS = [
    k.strip() for k in os.getenv("API_KEYS", DEFAULT_DEV_API_KEY).split(",") if k.strip()
]
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))