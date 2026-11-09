from types import SimpleNamespace

import openai
import pytest

from backend.app.generation.answer import (
    ABSTENTION,
    SYSTEM_PROMPT,
    AnswerGenerator,
    cited_evidence,
    select_context,
)
from backend.app.indexing.embeddings import OpenAIEmbedder
from backend.app.models.contracts import Evidence
from backend.app.retrieval.base import ProviderError
from tests.retrieval_fakes import BUILT_AT, FakeChat


def evidence(rank: int, text: str = "body") -> Evidence:
    return Evidence(
        document_id=f"DOC-{rank}",
        document_title=f"Doc {rank}",
        doc_type="runbook",
        source_uri="x",
        created_at=BUILT_AT,
        section_path=None,
        text=text,
        span_start=0,
        span_end=len(text),
        rank=rank,
        score=1.0,
    )


def test_answer_maps_citations_back_to_evidence():
    chat = FakeChat("Pool leak [2], confirmed [1, 2]. Ignored [9].")
    items = [evidence(1), evidence(2)]
    answer = AnswerGenerator(chat).generate("why?", items)
    assert answer.citations == [items[1].evidence_id, items[0].evidence_id]
    assert not answer.abstained
    assert (answer.prompt_tokens, answer.completion_tokens) == (10, 5)


def test_sources_are_numbered_in_the_prompt():
    chat = FakeChat()
    AnswerGenerator(chat).generate("why?", [evidence(1, "first"), evidence(2, "second")])
    system, user = chat.calls[0]
    assert system == SYSTEM_PROMPT
    assert "[1] Doc 1" in user and "[2] Doc 2" in user and "Question: why?" in user


@pytest.mark.parametrize("reply", [ABSTENTION, "Not enough evidence. Nothing covers revenue."])
def test_abstention_is_detected_and_cites_nothing(reply):
    answer = AnswerGenerator(FakeChat(reply + " [1]")).generate("q", [evidence(1)])
    assert answer.abstained and answer.citations == []


def test_no_evidence_abstains_without_calling_the_model():
    chat = FakeChat()
    answer = AnswerGenerator(chat).generate("q", [])
    assert answer.abstained and answer.model is None and chat.calls == []


def test_context_budget_keeps_the_highest_ranked_evidence():
    items = [evidence(1, "a" * 60), evidence(2, "b" * 60), evidence(3, "c")]
    assert [e.rank for e in select_context(items, budget=100)] == [1]


def test_out_of_range_citations_are_ignored():
    assert cited_evidence("[0] [5]", [evidence(1)]) == []


def fake_embedding_client(create):
    return SimpleNamespace(embeddings=SimpleNamespace(create=create))


def test_embedder_batches_and_sums_usage():
    batches = []

    def create(model, input):
        batches.append(len(input))
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.0]) for _ in input],
            usage=SimpleNamespace(total_tokens=len(input)),
        )

    embedder = OpenAIEmbedder("key", "model")
    embedder.client = fake_embedding_client(create)
    result = embedder.embed(["t"] * 130)
    assert batches == [128, 2]
    assert len(result.vectors) == 130 and result.tokens == 130


def test_provider_errors_do_not_expose_details():
    def create(model, input):
        raise openai.OpenAIError("Incorrect API key provided: sk-secret")

    embedder = OpenAIEmbedder("key", "model")
    embedder.client = fake_embedding_client(create)
    with pytest.raises(ProviderError) as caught:
        embedder.embed(["t"])
    assert "sk-secret" not in str(caught.value)
