"""Contracts shared by the retrievers, the query API and the playground."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field

Status = Literal["ok", "unsupported", "error"]

MAX_TOP_K = 20
MAX_HOPS = 3
MAX_QUESTION_CHARS = 2000


class IndexProfile(BaseModel):
    id: str
    dataset_version_id: str
    chunker: str
    chunker_config: dict[str, Any]
    embedding_model: str | None
    embedding_dim: int | None
    status: str
    chunk_count: int | None
    content_hash: str | None
    built_at: datetime | None


class RetrievalRequest(BaseModel):
    question: str
    index: IndexProfile
    top_k: int = 5
    hop_limit: int = 2


class Usage(BaseModel):
    embedding_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


class Evidence(BaseModel):
    document_id: str
    document_title: str
    doc_type: str
    source_uri: str
    created_at: datetime
    section_path: str | None
    text: str
    span_start: int
    span_end: int
    rank: int
    score: float
    matched_terms: list[str] = Field(default_factory=list)
    # For fused results: the rank each component strategy gave this evidence.
    rank_details: dict[str, int] = Field(default_factory=dict)
    # For graph results: the relationships this evidence backs.
    supports: list[str] = Field(default_factory=list)

    # Chunk row ids change on every rebuild; document spans do not.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def evidence_id(self) -> str:
        return f"{self.document_id}:{self.span_start}-{self.span_end}"


class GraphPath(BaseModel):
    steps: list[str]
    hops: int
    refuted: bool


class EntityRef(BaseModel):
    key: str
    name: str
    entity_type: str
    mention: str


class RetrievalResult(BaseModel):
    evidence: list[Evidence]
    graph_paths: list[GraphPath] = Field(default_factory=list)
    entities: list[EntityRef] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Answer(BaseModel):
    text: str
    abstained: bool
    citations: list[str]
    model: str | None
    prompt_version: str
    context_sources: int
    prompt_tokens: int = 0
    completion_tokens: int = 0


class QueryOptions(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    index_profile: str | None = None
    top_k: int = Field(default=5, ge=1, le=MAX_TOP_K)
    hop_limit: int = Field(default=2, ge=1, le=MAX_HOPS)
    generate: bool = False


class QueryRequest(QueryOptions):
    strategy: str


class CompareRequest(QueryOptions):
    strategies: list[str] | None = None


class Latency(BaseModel):
    retrieval_ms: float
    generation_ms: float | None = None


class QueryResponse(BaseModel):
    strategy: str
    status: Status
    message: str | None = None
    index_profile: str | None
    top_k: int
    evidence: list[Evidence] = Field(default_factory=list)
    graph_paths: list[GraphPath] = Field(default_factory=list)
    entities: list[EntityRef] = Field(default_factory=list)
    answer: Answer | None = None
    answer_error: str | None = None
    latency: Latency
    usage: Usage = Field(default_factory=Usage)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompareResponse(BaseModel):
    question: str
    index_profile: str | None
    results: list[QueryResponse]


class StrategyInfo(BaseModel):
    id: str
    label: str
    description: str


class PlaygroundOptions(BaseModel):
    dataset_version: str
    strategies: list[StrategyInfo]
    indexes: list[IndexProfile]
    generation_available: bool
    default_top_k: int
    max_top_k: int = MAX_TOP_K
    default_hop_limit: int = 2
    max_hops: int = MAX_HOPS


class ExampleQuestion(BaseModel):
    id: str
    category: str
    question: str
