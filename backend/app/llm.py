"""Call the Gemini API over plain HTTP (REST).

Each protection below fixes a problem we really hit:
- The API key goes only in a header, never in a URL or an error message.
- 503 (overloaded): retry twice with a short wait.
- Answer cut off (MAX_TOKENS, often because hidden "thinking" used the budget):
  an error, never a half answer.
- Thinking is limited. If a model rejects that setting, we retry once without it.
- If the main model is busy, times out or cuts off, we try the fallback model once.
"""
import logging
import time
from dataclasses import dataclass

import httpx

from app.config import (
    GEMINI_API_KEY,
    GEMINI_FALLBACK_MODEL,
    GEMINI_MODEL,
    GEMINI_THINKING_LEVEL,
    GEMINI_TIMEOUT,
)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
logger = logging.getLogger("fraudlens.llm")

UNAFFECTED = "The decision is unaffected."
OVERLOAD_RETRY_DELAYS = (1.0, 3.0)  # seconds to wait before retry 1 and retry 2
MAX_OUTPUT_TOKENS = 4096  # hidden "thinking" tokens count against this limit too


class LLMError(Exception):
    """A problem with the explanation service. The message is safe to show to a client."""

    def __init__(self, message: str, status_code: int = 502, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable  # True = another model might work


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str  # the model that really answered (main or fallback)


class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY, model: str = GEMINI_MODEL,
                 fallback_model: str = GEMINI_FALLBACK_MODEL, timeout: float = GEMINI_TIMEOUT,
                 transport: httpx.BaseTransport | None = None, sleep=time.sleep,
                 thinking_level: str = GEMINI_THINKING_LEVEL):
        self.api_key = api_key
        self.model = model
        self.fallback_model = fallback_model
        self.timeout = timeout
        self.thinking_level = thinking_level
        self._transport = transport  # tests pass a mock transport here
        self._sleep = sleep          # tests pass a no-op so they do not wait

    def _post(self, model: str, body: dict) -> httpx.Response:
        url = f"{BASE_URL}/models/{model}:generateContent"
        try:
            with httpx.Client(timeout=self.timeout, transport=self._transport) as http:
                return http.post(url, headers={"x-goog-api-key": self.api_key}, json=body)
        except httpx.TimeoutException:
            logger.warning("Gemini request to %s timed out", model)
            raise LLMError(f"The explanation service timed out. {UNAFFECTED}", 502, retryable=True) from None
        except httpx.HTTPError as error:
            logger.warning("Gemini request failed: %s: %s", type(error).__name__, str(error)[:200])
            raise LLMError(f"The explanation service could not be reached. {UNAFFECTED}") from None

    def _body(self, system_instruction: str, prompt: str, with_thinking: bool) -> dict:
        generation_config = {"temperature": 0.2, "maxOutputTokens": MAX_OUTPUT_TOKENS}
        if with_thinking and self.thinking_level:
            generation_config["thinkingConfig"] = {"thinkingLevel": self.thinking_level}
        return {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }

    def _ask(self, model: str, system_instruction: str, prompt: str) -> str:
        body = self._body(system_instruction, prompt, with_thinking=True)
        response = self._post(model, body)

        # This model may reject the thinking setting. Retry once without it.
        if response.status_code == 400 and self.thinking_level and "think" in response.text.lower():
            logger.warning("%s rejected the thinking setting. Retrying without it.", model)
            body = self._body(system_instruction, prompt, with_thinking=False)
            response = self._post(model, body)

        # 503 = overloaded for a moment. Retry a couple of times on the same model.
        for delay in OVERLOAD_RETRY_DELAYS:
            if response.status_code != 503:
                break
            logger.warning("%s overloaded (503). Retrying in %.0f s", model, delay)
            self._sleep(delay)
            response = self._post(model, body)

        if response.status_code in (429, 503):
            reason = "provider overloaded" if response.status_code == 503 else "provider rate limit"
            raise LLMError(
                f"The explanation service is busy ({reason}). Try again in a minute. {UNAFFECTED}",
                503, retryable=True,
            )
        if response.status_code >= 400:
            # The detail goes to our log only. A 404 usually means the model name is retired,
            # and 400/403 usually mean a wrong or restricted API key.
            logger.warning("%s returned %s: %s", model, response.status_code, response.text[:300])
            raise LLMError(f"The explanation service returned an error (provider status {response.status_code}). {UNAFFECTED}")

        try:
            data = response.json()
            candidate = data["candidates"][0]
        except (KeyError, IndexError, TypeError, ValueError):
            data, candidate = {}, {}

        if candidate.get("finishReason") == "MAX_TOKENS":
            # A half answer must never be shown as a complete one.
            logger.warning("%s answer was cut off (MAX_TOKENS). usage=%s", model, data.get("usageMetadata"))
            raise LLMError(f"The explanation was cut off. Please try again. {UNAFFECTED}", 502, retryable=True)

        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
        if not text:
            logger.warning("%s returned no text: %s", model, response.text[:300])
            raise LLMError(f"The explanation service returned no text. {UNAFFECTED}", 502, retryable=True)
        return text

    def generate(self, system_instruction: str, prompt: str) -> LLMResult:
        if not self.api_key:
            raise LLMError("Explanations are not configured: set GEMINI_API_KEY in backend/.env.", 503)
        try:
            return LLMResult(self._ask(self.model, system_instruction, prompt), self.model)
        except LLMError as error:
            if not (error.retryable and self.fallback_model and self.fallback_model != self.model):
                raise
            logger.warning("Model %s failed (%s). Trying fallback model %s.", self.model, error, self.fallback_model)
            return LLMResult(self._ask(self.fallback_model, system_instruction, prompt), self.fallback_model)


def get_llm() -> GeminiClient:
    """FastAPI dependency. Tests replace it with a fake."""
    return GeminiClient()