"""Settings. Values come from environment variables, with safe local defaults."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]  # the backend folder

# Reads backend/.env if it exists. Real environment variables win over the file.
load_dotenv(BASE_DIR / ".env")

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

# RAG
KNOWLEDGE_DIR = Path(os.getenv("KNOWLEDGE_DIR", BASE_DIR / "knowledge"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))
# Below this similarity we say "I don't have enough information".
# 0.30 is a first guess. We calibrate it with real scores and the evaluation set.
RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.30"))

# LLM (Gemini). The key stays in .env or in the host's secret settings, never in code.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Preview models can be retired. A 404 in the server log means: run the model list and update .env.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.1-flash-lite-preview")
# "minimal", "low", "medium" or "high" for Gemini 3 models. Empty = do not send the setting.
GEMINI_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "low")
GEMINI_TIMEOUT = float(os.getenv("GEMINI_TIMEOUT", "30"))