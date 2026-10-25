from fastapi.testclient import TestClient

from app.llm import LLMError, LLMResult, get_llm
from app.main import app
from app.rag.explain import NO_INFO_ANSWER
from app.rag.search import Hit
from app.rag.service import get_retriever
from score_helpers import GOOD, post_score

RISKY = {
    **GOOD, "timestamp": "2020-12-30T23:30:00", "amount": 1200.0,
    "category": "shopping_net", "merchant": "Secret Merchant Name",
}


def make_hit(score, source="night-purchases.md", title="Night purchases",
             text="Purchases at night are riskier."):
    return Hit(source=source, title=title, chunk_index=0, text=text, score=score)


class FakeLLM:
    def __init__(self, reply="The night timing and amount raised the score [1].",
                 error=None, model="fake-model"):
        self.reply, self.error, self.model, self.calls = reply, error, model, []

    def generate(self, system_instruction, prompt):
        self.calls.append((system_instruction, prompt))
        if self.error:
            raise self.error
        return LLMResult(text=self.reply, model=self.model)


class FakeRetriever:
    def __init__(self, hits):
        self.hits, self.queries = hits, []

    def __call__(self, query):
        self.queries.append(query)
        return self.hits


def setup(hits, llm=None):
    """Replace the retriever and the LLM. The conftest clears overrides after each test."""
    retriever, llm = FakeRetriever(hits), llm or FakeLLM()
    app.dependency_overrides[get_retriever] = lambda: retriever
    app.dependency_overrides[get_llm] = lambda: llm
    return retriever, llm


def create(client, key="e-1"):
    return post_score(client, RISKY, key=key).json()


def test_explain_happy_path(client):
    tx = create(client)
    retriever, llm = setup([make_hit(0.66), make_hit(0.12, "x.md", "Other", "Unrelated.")])
    response = client.post(f"/transactions/{tx['id']}/explain")
    assert response.status_code == 200
    body = response.json()
    assert body["answered"] is True
    assert body["answer"] == llm.reply
    assert body["llm_model"] == "fake-model"
    assert body["decision"] == tx["decision"]
    assert [s["source"] for s in body["sources"]] == ["night-purchases.md"]  # 0.12 is below the cutoff

    system, prompt = llm.calls[0]
    assert "never decide" in system
    assert "Purchases at night are riskier." in prompt
    assert "Unrelated." not in prompt
    assert "Secret Merchant Name" not in prompt  # free text from the caller stays out of the prompt


def test_response_names_the_model_that_really_answered(client):
    tx = create(client)
    setup([make_hit(0.66)], FakeLLM(model="the-fallback-model"))
    body = client.post(f"/transactions/{tx['id']}/explain").json()
    assert body["llm_model"] == "the-fallback-model"


def test_default_query_is_built_from_the_reasons(client):
    tx = create(client)
    retriever, _ = setup([make_hit(0.66)])
    client.post(f"/transactions/{tx['id']}/explain")
    increasing = [r["text"] for r in tx["reasons"] if r["direction"] == "increases risk"]
    assert any(text in retriever.queries[0] for text in increasing)


def test_typed_question_is_searched_alone(client):
    tx = create(client)
    retriever, _ = setup([make_hit(0.66)])
    client.post(f"/transactions/{tx['id']}/explain", json={"question": "Why does the hour matter?"})
    assert retriever.queries == ["Why does the hour matter?"]


def test_nothing_relevant_means_refusal_and_no_llm_call(client):
    tx = create(client)
    _, llm = setup([make_hit(0.05), make_hit(-0.02)])
    body = client.post(f"/transactions/{tx['id']}/explain", json={"question": "Capital of France?"}).json()
    assert body["answered"] is False
    assert body["answer"] == NO_INFO_ANSWER
    assert body["sources"] == []
    assert body["llm_model"] is None
    assert llm.calls == []


def test_empty_search_result_means_refusal(client):
    tx = create(client)
    _, llm = setup([])
    body = client.post(f"/transactions/{tx['id']}/explain").json()
    assert body["answered"] is False
    assert llm.calls == []


def test_llm_saying_no_info_gives_no_sources(client):
    tx = create(client)
    setup([make_hit(0.66)], FakeLLM(reply="I don\u2019t have enough information to answer that."))
    body = client.post(f"/transactions/{tx['id']}/explain").json()
    assert body["answered"] is False
    assert body["sources"] == []


def test_explain_never_changes_the_transaction(client):
    tx = create(client)
    before = client.get(f"/transactions/{tx['id']}").json()
    setup([make_hit(0.66)])
    client.post(f"/transactions/{tx['id']}/explain")
    after = client.get(f"/transactions/{tx['id']}").json()
    assert after == before  # decision, score, reasons, rules: everything is identical


def test_busy_llm_gives_503(client):
    tx = create(client)
    setup([make_hit(0.66)], FakeLLM(error=LLMError("The explanation service is busy.", 503)))
    response = client.post(f"/transactions/{tx['id']}/explain")
    assert response.status_code == 503
    assert "busy" in response.json()["detail"]


def test_llm_failure_gives_502_and_decision_is_still_readable(client):
    tx = create(client)
    setup([make_hit(0.66)], FakeLLM(error=LLMError("The explanation service returned an error.")))
    assert client.post(f"/transactions/{tx['id']}/explain").status_code == 502
    assert client.get(f"/transactions/{tx['id']}").json()["decision"] == tx["decision"]


def test_unknown_transaction_is_404(client):
    setup([make_hit(0.66)])
    assert client.post("/transactions/99999/explain").status_code == 404


def test_other_clients_transaction_is_404(client, monkeypatch):
    tx = create(client)
    setup([make_hit(0.66)])
    monkeypatch.setattr("app.auth.API_KEYS", ["dev-key-change-me", "other-key"])
    other = TestClient(app, headers={"X-API-Key": "other-key"})
    assert other.post(f"/transactions/{tx['id']}/explain").status_code == 404


def test_explain_needs_an_api_key(anon_client):
    assert anon_client.post("/transactions/1/explain").status_code == 401


def test_bad_questions_are_rejected(client):
    tx = create(client)
    setup([make_hit(0.66)])
    url = f"/transactions/{tx['id']}/explain"
    assert client.post(url, json={"question": "ab"}).status_code == 422
    assert client.post(url, json={"question": "   "}).status_code == 422
    assert client.post(url, json={"question": "x" * 301}).status_code == 422