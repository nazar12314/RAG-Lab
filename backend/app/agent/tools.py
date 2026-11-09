"""Typed read-only tools for the agent: thin wrappers over the shared retrieval services."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from time import monotonic, perf_counter
from typing import Any, Literal, Protocol

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from backend.app.models.contracts import (
    MAX_HOPS,
    Evidence,
    GraphPath,
    RetrievalRequest,
    RetrievalResult,
    ToolCall,
)
from backend.app.retrieval.base import ProviderError, Retriever, Unsupported
from backend.app.retrieval.graph import GraphRetriever
from backend.app.storage.business import (
    AggregateEntity,
    AggregateResult,
    GroupBy,
    Record,
    RecordFilter,
    RecordType,
)
from backend.app.storage.documents import FullDocument

MAX_ITEM_CHARS = 900
MAX_DOCUMENT_CHARS = 4000
MAX_OUTPUT_CHARS = 7000
BUDGET_MESSAGE = "Tool budget exhausted. Do not call more tools; answer from what you have."


class BusinessRecords(Protocol):
    def lookup(
        self, record_type: RecordType, filters: RecordFilter, limit: int = ...
    ) -> list[Record]: ...

    def record(self, ref: str) -> Record | None: ...

    def aggregate(
        self, entity: AggregateEntity, group_by: list[GroupBy], filters: RecordFilter
    ) -> AggregateResult: ...


class DocumentSource(Protocol):
    def document(self, document_id: str) -> FullDocument | None: ...


@dataclass(frozen=True)
class AgentData:
    keyword: Retriever
    semantic: Retriever
    graph: GraphRetriever
    records: BusinessRecords
    documents: DocumentSource


class _Reasoned(BaseModel):
    reason: str = Field(description="One short sentence: why this tool fits this step.")


class SearchArgs(_Reasoned):
    query: str = Field(description="What to search for.", min_length=1, max_length=500)


class _FilterArgs(_Reasoned):
    service: str | None = Field(default=None, description="Service name, alias or ID.")
    primary_service_only: bool = Field(
        default=False,
        description="For incidents: match only the primary service, not any affected service.",
    )
    severity: list[int] = Field(default_factory=list, description="Severity levels, 1 is worst.")
    status: str | None = Field(default=None, description="Exact status value.")
    kind: str | None = Field(
        default=None, description="Deployment kind: release, hotfix, rollback, config_change..."
    )
    date_from: date | None = Field(default=None, description="Inclusive start date.")
    date_to: date | None = Field(default=None, description="Exclusive end date.")


class LookupArgs(_FilterArgs):
    record_type: RecordType
    record_id: str | None = Field(default=None, description="Exact ID such as INC-104 or DPL-012.")


class AggregateArgs(_FilterArgs):
    entity: AggregateEntity
    group_by: list[GroupBy] = Field(
        default_factory=list, description="Grouping columns. Empty returns one total."
    )


class TraverseArgs(_Reasoned):
    entity: str = Field(description="Entity name, alias or ID to start from.")
    hops: int = Field(default=2, ge=1, le=MAX_HOPS, description="How many edges to follow.")


class FetchArgs(_Reasoned):
    evidence_id: str = Field(description="An evidence ID or record reference returned earlier.")


def _record_evidence(record: Record) -> Evidence:
    return Evidence(
        document_id=record.ref,
        document_title=record.title,
        doc_type="record",
        source_uri=record.ref,
        created_at=record.created_at,
        section_path=None,
        text=record.text,
        span_start=0,
        span_end=max(len(record.text), 1),
        rank=0,
        score=0.0,
        source_kind="record",
        record_refs=list(record.refs),
    )


def _aggregate_evidence(args: dict[str, Any], result: AggregateResult) -> Evidence:
    digest = hashlib.sha256(json.dumps(args, sort_keys=True, default=str).encode()).hexdigest()
    ref = f"aggregate:{digest[:10]}"
    table = "\n".join(
        ", ".join(f"{key}={value}" for key, value in row.items()) for row in result.rows
    )
    text = f"Query: {json.dumps(args, sort_keys=True, default=str)}\nTotal: {result.total}\n{table}"
    return Evidence(
        document_id=ref,
        document_title=f"Aggregate over {args['entity']}",
        doc_type="aggregate",
        source_uri=ref,
        created_at=None,
        section_path=None,
        text=text,
        span_start=0,
        span_end=len(text),
        rank=0,
        score=0.0,
        source_kind="record",
        record_refs=result.refs,
    )


def _document_evidence(document: FullDocument) -> Evidence:
    text = document.content[:MAX_DOCUMENT_CHARS]
    return Evidence(
        document_id=document.id,
        document_title=document.title,
        doc_type=document.doc_type,
        source_uri=document.source_uri,
        created_at=document.created_at,
        section_path=None,
        text=text,
        span_start=0,
        span_end=len(text),
        rank=0,
        score=0.0,
    )


def _render(evidence: list[Evidence], paths: list[GraphPath] | None = None) -> str:
    parts: list[str] = []
    if paths:
        parts.append("Graph paths:\n" + "\n".join(" | ".join(path.steps) for path in paths))
    for item in evidence:
        section = f" > {item.section_path}" if item.section_path else ""
        created = f", {item.created_at.date()}" if item.created_at else ""
        supports = f"\nBacks: {'; '.join(item.supports)}" if item.supports else ""
        parts.append(
            f"[{item.evidence_id}] {item.document_title}{section} ({item.doc_type}{created})"
            f"{supports}\n{item.text[:MAX_ITEM_CHARS]}"
        )
    rendered = "\n\n".join(parts) if parts else "No results."
    return rendered[:MAX_OUTPUT_CHARS]


@dataclass
class AgentToolbox:
    """State for one agent run: the budget, the trace and everything retrieved so far."""

    data: AgentData
    request: RetrievalRequest
    max_calls: int
    deadline: float
    evidence: dict[str, Evidence] = field(default_factory=dict)
    trace: list[ToolCall] = field(default_factory=list)
    graph_paths: list[GraphPath] = field(default_factory=list)

    def _run(
        self,
        name: str,
        reason: str,
        args: dict[str, Any],
        action: Callable[[], tuple[list[Evidence], str, int]],
    ) -> str:
        safe_args = {k: v for k, v in args.items() if v not in (None, [], "", False)}
        if len(self.trace) >= self.max_calls or monotonic() >= self.deadline:
            self.trace.append(
                ToolCall(
                    tool=name,
                    args=safe_args,
                    reason=reason,
                    duration_ms=0.0,
                    status="budget",
                    message=BUDGET_MESSAGE,
                )
            )
            return BUDGET_MESSAGE
        started = perf_counter()
        status: Literal["ok", "error"] = "ok"
        message = None
        evidence: list[Evidence] = []
        tokens = 0
        try:
            evidence, output, tokens = action()
        except (Unsupported, ProviderError, ValueError) as exc:
            status, message, output = "error", str(exc), f"Tool failed: {exc}"
        for item in evidence:
            self.evidence.setdefault(item.evidence_id, item)
        self.trace.append(
            ToolCall(
                tool=name,
                args=safe_args,
                reason=reason,
                evidence_ids=[item.evidence_id for item in evidence],
                duration_ms=round((perf_counter() - started) * 1000, 1),
                embedding_tokens=tokens,
                status=status,
                message=message,
            )
        )
        return output

    def _service_id(self, name: str | None) -> str | None:
        if not name:
            return None
        links = self.data.graph.resolve(self.request.index.dataset_version_id, name)
        for link in links:
            if link.entity.entity_type == "service":
                return link.entity.key
        raise ValueError(f"Unknown service: {name}")

    def _filters(self, args: _FilterArgs, record_id: str | None = None) -> RecordFilter:
        return RecordFilter(
            record_id=record_id,
            service_id=self._service_id(args.service),
            primary_service_only=args.primary_service_only,
            severity=tuple(args.severity),
            status=args.status,
            kind=args.kind,
            date_from=args.date_from,
            date_to=args.date_to,
        )

    def _search(self, retriever: Retriever, query: str) -> tuple[list[Evidence], str, int]:
        result: RetrievalResult = retriever.retrieve(
            self.request.model_copy(update={"question": query})
        )
        return result.evidence, _render(result.evidence), result.usage.embedding_tokens

    def keyword_search(self, reason: str, query: str) -> str:
        return self._run(
            "keyword_search",
            reason,
            {"query": query},
            lambda: self._search(self.data.keyword, query),
        )

    def semantic_search(self, reason: str, query: str) -> str:
        return self._run(
            "semantic_search",
            reason,
            {"query": query},
            lambda: self._search(self.data.semantic, query),
        )

    def graph_traverse(self, reason: str, entity: str, hops: int = 2) -> str:
        def action() -> tuple[list[Evidence], str, int]:
            links = self.data.graph.resolve(self.request.index.dataset_version_id, entity)
            if not links:
                raise ValueError(f"No entity found for: {entity}")
            result = self.data.graph.expand(
                self.request.model_copy(update={"hop_limit": hops}), links
            )
            self.graph_paths.extend(p for p in result.graph_paths if p not in self.graph_paths)
            return result.evidence, _render(result.evidence, result.graph_paths), 0

        return self._run("graph_traverse", reason, {"entity": entity, "hops": hops}, action)

    def exact_lookup(self, reason: str, record_type: RecordType, **kwargs: Any) -> str:
        args = LookupArgs(reason=reason, record_type=record_type, **kwargs)

        def action() -> tuple[list[Evidence], str, int]:
            records = self.data.records.lookup(
                record_type, self._filters(args, args.record_id), self.request.top_k
            )
            evidence = [_record_evidence(record) for record in records]
            return evidence, _render(evidence), 0

        return self._run(
            "exact_lookup", reason, args.model_dump(exclude={"reason"}, mode="json"), action
        )

    def aggregate_records(self, reason: str, entity: AggregateEntity, **kwargs: Any) -> str:
        args = AggregateArgs(reason=reason, entity=entity, **kwargs)
        safe = args.model_dump(exclude={"reason"}, mode="json")

        def action() -> tuple[list[Evidence], str, int]:
            result = self.data.records.aggregate(entity, args.group_by, self._filters(args))
            evidence = [_aggregate_evidence(safe, result)]
            return evidence, _render(evidence), 0

        return self._run("aggregate_records", reason, safe, action)

    def fetch_evidence(self, reason: str, evidence_id: str) -> str:
        def action() -> tuple[list[Evidence], str, int]:
            known = self.evidence.get(evidence_id)
            if known is not None and known.doc_type == "aggregate":
                return [known], _render([known]), 0
            target = evidence_id.partition(":")[0]
            record = self.data.records.record(target) if "/" in target else None
            if record is not None:
                evidence = [_record_evidence(record)]
                return evidence, _render(evidence), 0
            document = self.data.documents.document(target)
            if document is None:
                raise ValueError(f"No evidence found for: {evidence_id}")
            evidence = [_document_evidence(document)]
            # A whole document is requested on purpose, so its text is not clipped to a snippet.
            header = f"[{evidence[0].evidence_id}] {document.title} ({document.doc_type})"
            return evidence, f"{header}\n{evidence[0].text}", 0

        return self._run("fetch_evidence", reason, {"evidence_id": evidence_id}, action)

    def tools(self) -> list[BaseTool]:
        definitions: list[tuple[Callable[..., str], type[BaseModel], str]] = [
            (
                self.exact_lookup,
                LookupArgs,
                "Fetch incident, deployment, service or team records by exact ID or filters. "
                "Newest first. Best for known IDs and attributes.",
            ),
            (
                self.aggregate_records,
                AggregateArgs,
                "Count incidents or deployments, optionally grouped and filtered. "
                "Use for how many / which most questions.",
            ),
            (
                self.keyword_search,
                SearchArgs,
                "BM25 search over document passages. Best for error codes, config names and "
                "exact terminology.",
            ),
            (
                self.semantic_search,
                SearchArgs,
                "Embedding search over document passages. Best for paraphrased or conceptual "
                "questions.",
            ),
            (
                self.graph_traverse,
                TraverseArgs,
                "Follow relationships from one named entity: dependencies, owners, affected "
                "services, triggering deployments, fixes. Returns paths and supporting passages.",
            ),
            (
                self.fetch_evidence,
                FetchArgs,
                "Read the full document or record behind an evidence ID to verify a claim.",
            ),
        ]
        return [
            StructuredTool.from_function(
                func=function,
                name=function.__name__,
                description=description,
                args_schema=schema,
            )
            for function, schema, description in definitions
        ]
