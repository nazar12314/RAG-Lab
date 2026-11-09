from itertools import count

import openai
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from backend.app.agent.runner import MAX_TOOL_CALLS, AgentRetriever, number_citations, rank_evidence
from backend.app.agent.tools import AgentData, AgentToolbox
from backend.app.generation.answer import ABSTENTION
from backend.app.models.contracts import RetrievalRequest
from backend.app.retrieval.base import ProviderError, Unsupported
from backend.app.retrieval.graph import GraphRetriever
from backend.app.retrieval.keyword import BM25Retriever
from backend.app.retrieval.vector import VectorRetriever
from backend.app.storage.business import AggregateResult, Record, RecordFilter
from backend.app.storage.documents import FullDocument
from tests.retrieval_fakes import BUILT_AT, FakeEmbedder, FakeGraphStore, FakeStore, make_profile

DOC_1 = "DOC-1:0-61"
INCIDENT = Record(
    "incidents/INC-104", "Incident INC-104", "Incident: INC-104", BUILT_AT, ("incidents/INC-104",)
)


class FakeRecords:
    def __init__(self) -> None:
        self.filters: list[RecordFilter] = []

    def lookup(self, record_type, filters, limit=25):
        self.filters.append(filters)
        return [INCIDENT]

    def record(self, ref):
        return INCIDENT if ref == INCIDENT.ref else None

    def aggregate(self, entity, group_by, filters):
        self.filters.append(filters)
        return AggregateResult([{"severity": 1, "count": 4}], 4, ["incidents/INC-104"])


class FakeDocuments:
    def document(self, document_id):
        if document_id != "DOC-1":
            return None
        return FullDocument("DOC-1", "Doc one", "runbook", "docs/1.md", BUILT_AT, "full body text")


_ids = count()


class ScriptedModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def call(name: str, **args) -> AIMessage:
    # Real models give every call and message its own id; LangGraph merges messages sharing one.
    number = next(_ids)
    payload = {"reason": "it fits", **args}
    return AIMessage(
        id=f"m-{number}",
        content="",
        tool_calls=[{"name": name, "args": payload, "id": f"c-{number}"}],
    )


def data(records=None) -> AgentData:
    store = FakeStore()
    return AgentData(
        BM25Retriever(store),
        VectorRetriever(store, lambda model: FakeEmbedder()),
        GraphRetriever(FakeGraphStore()),
        records or FakeRecords(),
        FakeDocuments(),
    )


def request() -> RetrievalRequest:
    return RetrievalRequest(question="pool?", index=make_profile(), top_k=3)


def run(messages, records=None):
    model = ScriptedModel(messages=iter(messages))
    return AgentRetriever(data(records), model, "fake-model").retrieve(request())


def toolbox() -> AgentToolbox:
    return AgentToolbox(data(), request(), max_calls=8, deadline=float("inf"))


def test_agent_uses_several_tools_then_answers_with_numbered_citations():
    result = run(
        [
            call("keyword_search", query="pool"),
            call("graph_traverse", entity="pool", hops=1),
            AIMessage(content=f"The pool leaked [{DOC_1}]."),
        ]
    )
    assert [c.tool for c in result.tool_trace] == ["keyword_search", "graph_traverse"]
    assert result.tool_trace[0].reason == "it fits"
    assert DOC_1 in result.tool_trace[0].evidence_ids
    assert result.answer.text == "The pool leaked [1]."
    assert result.answer.citations == [DOC_1]
    assert result.evidence[0].evidence_id == DOC_1
    assert result.evidence[0].score == 1.0
    assert result.metadata["stop_reason"] == "answered"
    assert result.graph_paths


def test_uncited_evidence_is_kept_after_cited_evidence():
    result = run([call("keyword_search", query="pool"), AIMessage(content=f"Yes [{DOC_1}].")])
    assert [e.rank for e in result.evidence] == list(range(1, len(result.evidence) + 1))
    assert all(e.score == 0.0 for e in result.evidence[1:])


def test_abstention_cites_nothing_but_keeps_what_was_searched():
    result = run([call("keyword_search", query="pool"), AIMessage(content=ABSTENTION)])
    assert result.answer.abstained and result.answer.citations == []
    assert result.evidence


def test_invented_citations_are_not_counted():
    result = run([call("keyword_search", query="pool"), AIMessage(content="True [DOC-FAKE:1-2].")])
    assert result.answer.citations == []
    assert "[DOC-FAKE:1-2]" in result.answer.text


def test_tool_budget_stops_further_retrieval():
    calls = [call("keyword_search", query="pool") for _ in range(MAX_TOOL_CALLS + 2)]
    result = run([*calls, AIMessage(content=ABSTENTION)])
    assert [c.status for c in result.tool_trace].count("budget") == 2
    assert len(result.tool_trace) == MAX_TOOL_CALLS + 2
    assert result.metadata["stop_reason"] == "budget_reached"


def test_a_model_that_never_stops_is_cut_off_and_abstains():
    result = run(call("keyword_search", query="pool") for _ in count())
    assert result.answer.abstained
    assert result.metadata["stop_reason"] == "recursion_limit"


def test_tool_failures_are_shown_to_the_model_and_the_trace():
    result = run(
        [
            call("graph_traverse", entity="nothing known"),
            AIMessage(content=ABSTENTION),
        ]
    )
    assert result.tool_trace[0].status == "error"
    assert "No entity found" in result.tool_trace[0].message


def test_token_usage_is_summed_across_model_turns():
    usage = {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}
    first = call("semantic_search", query="pool")
    first.usage_metadata = usage
    result = run([first, AIMessage(content=ABSTENTION, usage_metadata=usage)])
    assert result.usage.prompt_tokens == 20 and result.usage.completion_tokens == 4
    assert result.usage.embedding_tokens == 1


def test_missing_key_is_unsupported():
    with pytest.raises(Unsupported, match="OPENAI_API_KEY"):
        AgentRetriever(data(), None, "").retrieve(request())


def test_provider_failure_is_reported_without_details():
    class Failing(ScriptedModel):
        def _generate(self, *args, **kwargs):
            raise openai.OpenAIError("secret detail")

    with pytest.raises(ProviderError) as caught:
        AgentRetriever(data(), Failing(messages=iter([])), "m").retrieve(request())
    assert "secret detail" not in str(caught.value)


def test_the_tool_set_is_the_six_read_only_operations():
    tools = {tool.name: tool for tool in toolbox().tools()}
    assert set(tools) == {
        "exact_lookup",
        "aggregate_records",
        "keyword_search",
        "semantic_search",
        "graph_traverse",
        "fetch_evidence",
    }
    fields = {name for tool in tools.values() for name in tool.args_schema.model_fields}
    assert not fields & {"sql", "statement", "table", "column"}
    assert all("reason" in tool.args_schema.model_fields for tool in tools.values())


def test_exact_lookup_returns_record_evidence_with_stable_ids():
    box = toolbox()
    output = box.exact_lookup("an ID was given", "incident", record_id="INC-104")
    assert "[incidents/INC-104]" in output
    assert box.evidence["incidents/INC-104"].source_kind == "record"
    assert box.evidence["incidents/INC-104"].record_refs == ["incidents/INC-104"]
    assert box.trace[0].args == {"record_type": "incident", "record_id": "INC-104"}


def test_service_names_are_resolved_before_querying():
    records = FakeRecords()
    box = AgentToolbox(data(records), request(), max_calls=8, deadline=float("inf"))
    box.exact_lookup("by service", "deployment", service="pool")
    assert records.filters[0].service_id == "SVC-POOL"


def test_unknown_service_is_an_error_not_an_unfiltered_query():
    records = FakeRecords()
    box = AgentToolbox(data(records), request(), max_calls=8, deadline=float("inf"))
    output = box.exact_lookup("by service", "deployment", service="made up")
    assert "Unknown service" in output and records.filters == []


def test_aggregate_evidence_ids_are_stable_and_list_their_records():
    box, other = toolbox(), toolbox()
    box.aggregate_records("counting", "incidents", group_by=["severity"], severity=[1])
    other.aggregate_records("counting", "incidents", group_by=["severity"], severity=[1])
    assert list(box.evidence) == list(other.evidence)
    item = next(iter(box.evidence.values()))
    assert item.doc_type == "aggregate" and "Total: 4" in item.text
    assert item.record_refs == ["incidents/INC-104"]


def test_fetch_evidence_reads_whole_documents_and_records():
    box = toolbox()
    assert "full body text" in box.fetch_evidence("verify", DOC_1)
    assert "Incident: INC-104" in box.fetch_evidence("verify", "incidents/INC-104")
    assert "No evidence found" in box.fetch_evidence("verify", "DOC-NOPE:1-2")


def test_budget_also_applies_after_the_deadline():
    box = AgentToolbox(data(), request(), max_calls=8, deadline=0.0)
    assert "budget exhausted" in box.keyword_search("late", "pool")
    assert box.trace[0].status == "budget" and box.evidence == {}


def test_multiple_ids_in_one_bracket_are_numbered():
    collected = toolbox()
    collected.keyword_search("search", "pool")
    ids = list(collected.evidence)[:2]
    text = f"Claim [{ids[0]}, {ids[1]}]."
    ranked, cited = rank_evidence(text, collected.evidence)
    assert cited == ids
    assert number_citations(text, ranked) == "Claim [1, 2]."
