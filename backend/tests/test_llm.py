import json

import httpx
import pytest

from app.llm import GeminiClient, LLMError, LLMResult


def gemini(handler, key="SECRET123", fallback="fallback-model", thinking="low"):
    return GeminiClient(
        api_key=key, model="main-model", fallback_model=fallback,
        transport=httpx.MockTransport(handler),
        sleep=lambda seconds: None,  # tests must not wait
        thinking_level=thinking,
    )


def ok_body(text="Hello", finish="STOP"):
    return {"candidates": [{"finishReason": finish, "content": {"parts": [{"text": text}]}}]}


def is_main(request):
    return "main-model" in str(request.url)


def test_generate_returns_text_and_model_and_key_goes_only_in_the_header():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-goog-api-key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=ok_body("Answer [1]."))

    result = gemini(handler).generate("SYSTEM", "PROMPT")
    assert result == LLMResult(text="Answer [1].", model="main-model")
    assert seen["key"] == "SECRET123"
    assert "SECRET123" not in seen["url"]
    assert "main-model:generateContent" in seen["url"]
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "SYSTEM"
    assert seen["body"]["contents"][0]["parts"][0]["text"] == "PROMPT"
    config = seen["body"]["generationConfig"]
    assert config["thinkingConfig"] == {"thinkingLevel": "low"}
    assert config["maxOutputTokens"] >= 4096


def test_thinking_setting_is_left_out_when_empty():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content)["generationConfig"])
        return httpx.Response(200, json=ok_body("x"))

    gemini(handler, thinking="").generate("s", "p")
    assert "thinkingConfig" not in seen[0]


def test_thinking_parts_are_skipped():
    def handler(request):
        parts = [{"text": "private thoughts", "thought": True}, {"text": "Final answer."}]
        return httpx.Response(200, json={"candidates": [{"content": {"parts": parts}}]})

    assert gemini(handler).generate("s", "p").text == "Final answer."


def test_missing_key_fails_without_any_http_call():
    def handler(request):
        raise AssertionError("no HTTP call should be made")

    with pytest.raises(LLMError) as error:
        gemini(handler, key="").generate("s", "p")
    assert error.value.status_code == 503
    assert "GEMINI_API_KEY" in str(error.value)


def test_model_that_rejects_thinking_is_retried_without_it():
    bodies = []

    def handler(request):
        config = json.loads(request.content)["generationConfig"]
        bodies.append(config)
        if "thinkingConfig" in config:
            return httpx.Response(400, text="Thinking level is not supported for this model")
        return httpx.Response(200, json=ok_body("Fine."))

    assert gemini(handler).generate("s", "p").text == "Fine."
    assert len(bodies) == 2
    assert "thinkingConfig" not in bodies[1]


def test_other_400_errors_are_not_retried_and_never_leak_the_key():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(400, text="API key not valid: SECRET123")

    with pytest.raises(LLMError) as error:
        gemini(handler).generate("s", "p")
    assert error.value.status_code == 502
    assert "400" in str(error.value)
    assert "SECRET123" not in str(error.value)
    assert len(calls) == 1


def test_overload_is_retried_on_the_same_model_and_can_succeed():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(503, json={"error": {"status": "UNAVAILABLE"}})
        return httpx.Response(200, json=ok_body("Recovered."))

    result = gemini(handler).generate("s", "p")
    assert result.text == "Recovered."
    assert result.model == "main-model"
    assert len(calls) == 3


def test_overloaded_main_model_falls_back_to_the_second_model():
    def handler(request):
        if is_main(request):
            return httpx.Response(503, json={"error": {"status": "UNAVAILABLE"}})
        return httpx.Response(200, json=ok_body("From fallback."))

    result = gemini(handler).generate("s", "p")
    assert result == LLMResult(text="From fallback.", model="fallback-model")


def test_quota_error_on_main_goes_to_fallback_without_retrying_main():
    main_calls = []

    def handler(request):
        if is_main(request):
            main_calls.append(1)
            return httpx.Response(429, json={"error": "quota"})
        return httpx.Response(200, json=ok_body("From fallback."))

    assert gemini(handler).generate("s", "p").model == "fallback-model"
    assert len(main_calls) == 1


def test_both_models_busy_gives_503_busy():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503, json={"error": {"status": "UNAVAILABLE"}})

    with pytest.raises(LLMError) as error:
        gemini(handler).generate("s", "p")
    assert error.value.status_code == 503
    assert "busy" in str(error.value)
    assert len(calls) == 6  # 3 tries per model


def test_no_fallback_configured_gives_busy_after_three_tries():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503, json={})

    with pytest.raises(LLMError):
        gemini(handler, fallback="").generate("s", "p")
    assert len(calls) == 3


def test_cut_off_answer_on_main_uses_fallback():
    def handler(request):
        if is_main(request):
            return httpx.Response(200, json=ok_body("The biggest", finish="MAX_TOKENS"))
        return httpx.Response(200, json=ok_body("Complete answer."))

    assert gemini(handler).generate("s", "p") == LLMResult("Complete answer.", "fallback-model")


def test_cut_off_everywhere_is_an_error_and_never_a_half_answer():
    def handler(request):
        return httpx.Response(200, json=ok_body("The biggest", finish="MAX_TOKENS"))

    with pytest.raises(LLMError) as error:
        gemini(handler).generate("s", "p")
    assert "cut off" in str(error.value)
    assert "The biggest" not in str(error.value)


def test_retired_model_404_is_not_retried_and_does_not_leak_the_key():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(404, text="model not found, key SECRET123")

    with pytest.raises(LLMError) as error:
        gemini(handler).generate("s", "p")
    assert error.value.status_code == 502
    assert "404" in str(error.value)
    assert "SECRET123" not in str(error.value)
    assert len(calls) == 1


def test_empty_answer_on_both_models_is_an_error():
    with pytest.raises(LLMError):
        gemini(lambda request: httpx.Response(200, json={"candidates": []})).generate("s", "p")


def test_timeout_on_main_uses_fallback():
    def handler(request):
        if is_main(request):
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json=ok_body("Fast enough."))

    assert gemini(handler).generate("s", "p").model == "fallback-model"


def test_connection_failure_is_an_error_and_does_not_try_the_fallback():
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(LLMError) as error:
        gemini(handler).generate("s", "p")
    assert error.value.status_code == 502
    assert len(calls) == 1