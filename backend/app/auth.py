"""API key check. Every protected endpoint uses require_client."""
import hashlib
import hmac

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from app.config import API_KEYS
from app.ratelimit import rate_limiter

# auto_error=False so we can send our own clear 401 message.
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def client_id_for(api_key: str) -> str:
    """A short id for a key. We store this, never the key itself."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def require_client(api_key: str | None = Depends(api_key_header)) -> str:
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key. Send it in the X-API-Key header.")

    # compare_digest avoids timing leaks. We check every key, with no early exit.
    matched = False
    for valid_key in API_KEYS:
        if hmac.compare_digest(api_key.encode(), valid_key.encode()):
            matched = True
    if not matched:
        raise HTTPException(status_code=401, detail="Invalid API key.")

    client_id = client_id_for(api_key)
    rate_limiter.check(client_id)  # raises 429 if over the limit
    return client_id