import pytest
from fastapi.testclient import TestClient

from backend.app.api.query import get_example_store, get_query_service
from backend.app.generation.answer import AnswerGenerator
from backend.app.main import create_app
from backend.app.models.contracts import ExampleQuestion, RetrievalResult
from backend.app.retrieval.base import ProviderError, Unsupported
from backend.app.retrieval.registry import build_retrievers
from backend.app.services.query_service import NO_INDEX_MESSAGE, NO_KEY_MESSAGE, QueryService
from tests.retrieval_fakes import FakeChat, FakeEmbedder, FakeStore

QUESTION = {"question": "  connection pool exhaustion  "}


class Raising:
    label = "Raising"
    description = "Always fails"

    def __init__(self, error: Exception) -> None:
        self.error = error

    def retrieve(self, request) -> RetrievalResult:
        raise self.error


def make_client(store=None, chat=None, extra=None, examples=None) -> TestClient:
    store = store or FakeStore()
    retrievers = {**build_retrievers(store, lambda model: FakeEmbedder()), **(extra or {})}
    service = QueryService(
        retrievers, store, AnswerGenerator(chat) if chat else None, "engineering-ops-v1"
    )
    app = create_app()
    app.dependency_overrides[get_query_service] = lambda: service
    if examples is not None:
        app.dependency_overrides[get_example_store] = lambda: examples
    return TestClient(app)


def test_options_list_strategies_and_ready_indexes():
    body = make_client(chat=FakeChat()).get("/query/options").json()
    assert [s["id"] for s in body["strategies"]] == ["bm25", "vector"]
    assert [i["id"] for i in body["indexes"]] == ["test-index"]
    assert body["generation_available"] is True


def test_query_returns_ranked_evidence_without_generation_by_default():
    chat = FakeChat()
    body = make_client(chat=chat).post("/query", json={**QUESTION, "strategy": "bm25"}).json()
    assert body["status"] == "ok"
    assert body["evidence"][0]["document_id"] == "DOC-1"
    assert body["evidence"][0]["evidence_id"].startswith("DOC-1:")
    assert body["answer"] is None and chat.calls == []


def test_query_with_generation_reports_answer_usage_and_latency():
    client = make_client(chat=FakeChat())
    body = client.post("/query", json={**QUESTION, "strategy": "vector", "generate": True}).json()
    assert body["answer"]["citations"] == [body["evidence"][0]["evidence_id"]]
    assert body["usage"] == {"embedding_tokens": 1, "prompt_tokens": 10, "completion_tokens": 5}
    assert body["latency"]["generation_ms"] is not None


def test_compare_runs_every_strategy_on_the_same_normalized_question():
    body = make_client().post("/query/compare", json=QUESTION).json()
    assert body["question"] == "connection pool exhaustion"
    assert body["index_profile"] == "test-index"
    assert [r["strategy"] for r in body["results"]] == ["bm25", "vector"]


def test_compare_can_be_limited_to_named_strategies():
    body = make_client().post("/query/compare", json={**QUESTION, "strategies": ["vector"]}).json()
    assert [r["strategy"] for r in body["results"]] == ["vector"]


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/query", {**QUESTION, "strategy": "nope"}),
        ("/query/compare", {**QUESTION, "strategies": ["bm25", "nope"]}),
        ("/query", {"question": "", "strategy": "bm25"}),
        ("/query", {**QUESTION, "strategy": "bm25", "top_k": 0}),
    ],
)
def test_invalid_requests_are_rejected(path, payload):
    assert make_client().post(path, json=payload).status_code == 422


def test_missing_index_is_reported_not_hidden():
    body = make_client(store=FakeStore(ready=False)).post("/query/compare", json=QUESTION).json()
    assert {r["status"] for r in body["results"]} == {"unsupported"}
    assert body["results"][0]["message"] == NO_INDEX_MESSAGE


def test_unknown_index_profile_is_reported():
    payload = {**QUESTION, "strategy": "bm25", "index_profile": "other"}
    body = make_client().post("/query", json=payload).json()
    assert body["status"] == "unsupported" and body["evidence"] == []


def test_one_failing_strategy_does_not_affect_the_others():
    extra = {"down": Raising(ProviderError("OpenAI failed")), "off": Raising(Unsupported("no"))}
    body = make_client(extra=extra).post("/query/compare", json=QUESTION).json()
    statuses = {r["strategy"]: r["status"] for r in body["results"]}
    assert statuses == {"bm25": "ok", "vector": "ok", "down": "error", "off": "unsupported"}


def test_generation_failure_keeps_the_retrieved_evidence():
    class FailingChat(FakeChat):
        def complete(self, system, user):
            raise ProviderError("OpenAI chat request failed (APIError)")

    payload = {**QUESTION, "strategy": "bm25", "generate": True}
    body = make_client(chat=FailingChat()).post("/query", json=payload).json()
    assert body["status"] == "ok" and body["evidence"]
    assert body["answer"] is None and "OpenAI chat" in body["answer_error"]


def test_generation_without_a_key_explains_why():
    payload = {**QUESTION, "strategy": "bm25", "generate": True}
    body = make_client(chat=None).post("/query", json=payload).json()
    assert body["answer_error"] == NO_KEY_MESSAGE and body["evidence"]


def test_keyword_search_with_no_match_abstains_without_a_model_call():
    chat = FakeChat()
    payload = {"question": "zzqx", "strategy": "bm25", "generate": True}
    body = make_client(chat=chat).post("/query", json=payload).json()
    assert body["evidence"] == [] and body["answer"]["abstained"] and chat.calls == []


def test_examples_expose_only_the_question():
    class Examples:
        def showcase(self):
            return [ExampleQuestion(id="Q-001", category="exact_id", question="What?")]

    body = make_client(examples=Examples()).get("/examples").json()
    assert body == [{"id": "Q-001", "category": "exact_id", "question": "What?"}]
