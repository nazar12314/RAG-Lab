"""Contracts for the read-only Data Analysis module."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RecordType(StrEnum):
    documents = "documents"
    services = "services"
    dependencies = "dependencies"
    deployments = "deployments"
    incidents = "incidents"
    entities = "entities"
    relations = "relations"


EvidenceFilter = Literal["document", "record_only", "none"]


class DatasetRef(BaseModel):
    dataset: str
    graph: str


class FilterSet(BaseModel):
    """Filters are applied only where meaningful; responses report which ones were used."""

    service: str | None = None
    doc_types: list[str] = Field(default_factory=list)
    severities: list[int] = Field(default_factory=list)
    entity_types: list[str] = Field(default_factory=list)
    relation_types: list[str] = Field(default_factory=list)
    date_from: date | None = None
    date_to: date | None = None
    length_min: int | None = None
    length_max: int | None = None
    evidence: EvidenceFilter | None = None
    q: str | None = None

    def active(self) -> set[str]:
        return {name for name, value in self if value not in (None, [], "")}


class GraphInfo(BaseModel):
    id: str
    kind: str
    created_at: datetime | None


class IndexInfo(BaseModel):
    id: str
    status: str
    chunker: str
    chunk_count: int | None


class DatasetInfo(BaseModel):
    id: str
    company: str
    as_of: date
    period_start: date
    period_end: date
    corpus_hash: str
    loaded_at: datetime
    graphs: list[GraphInfo]
    index_profiles: list[IndexInfo]


class FacetOption(BaseModel):
    value: str
    label: str
    count: int


class Facets(BaseModel):
    services: list[FacetOption]
    doc_types: list[FacetOption]
    severities: list[FacetOption]
    entity_types: list[FacetOption]
    relation_types: list[FacetOption]
    date_min: date
    date_max: date


class SummaryCard(BaseModel):
    id: str
    label: str
    value: int | float | str
    help: str
    total: int | None = None


class ChartSpec(BaseModel):
    """A distribution plus the drill-down contract: which filters a click sets, which records open.

    `click` maps data fields to FilterSet fields. Interval charts map a field to a
    (date_from, date_to) or (length_min, length_max) range.
    """

    id: str
    title: str
    description: str
    kind: Literal["bar", "histogram", "timeline", "heatmap", "stacked_bar"]
    record_type: RecordType
    x: str
    y: str
    color: str | None = None
    click: dict[str, str]
    applied_filters: list[str]
    rows: list[dict[str, Any]]


class Observation(BaseModel):
    level: Literal["info", "warning"]
    message: str
    record_type: RecordType
    filters: FilterSet


class Overview(BaseModel):
    ref: DatasetRef
    filters: FilterSet
    computed_at: datetime
    cards: list[SummaryCard]
    charts: list[ChartSpec]
    observations: list[Observation]


class RecordPage(BaseModel):
    ref: DatasetRef
    record_type: RecordType
    filters: FilterSet
    applied_filters: list[str]
    ignored_filters: list[str]
    total: int
    unfiltered_total: int
    offset: int
    limit: int
    sort: str | None
    descending: bool
    columns: list[str]
    items: list[dict[str, Any]]


class RecordLink(BaseModel):
    record_type: RecordType
    id: str
    label: str
    note: str | None = None


class LinkGroup(BaseModel):
    title: str
    links: list[RecordLink]


class EvidenceSnippet(BaseModel):
    document_id: str
    document_title: str
    span_start: int
    span_end: int
    text: str
    relation_key: str | None = None
    relation_type: str | None = None


class RecordSource(BaseModel):
    record_table: str
    record_id: str


class RecordDetail(BaseModel):
    ref: DatasetRef
    record_type: RecordType
    id: str
    label: str
    attributes: dict[str, Any]
    links: list[LinkGroup]
    evidence: list[EvidenceSnippet]
    record_sources: list[RecordSource]
    notes: list[str] = Field(default_factory=list)


class Highlight(BaseModel):
    span_start: int
    span_end: int
    relation_key: str
    relation_type: str
    source: RecordLink
    target: RecordLink
    verified_status: str


class ChunkSpan(BaseModel):
    id: int
    ordinal: int
    span_start: int
    span_end: int
    token_count: int | None
    has_embedding: bool


class DocumentDetail(BaseModel):
    ref: DatasetRef
    id: str
    title: str
    doc_type: str
    created_at: datetime
    author: str
    source_uri: str
    content_hash: str
    metadata: dict[str, Any]
    content: str
    length_chars: int
    word_count: int
    services: list[RecordLink]
    referenced_records: list[RecordLink]
    highlights: list[Highlight]
    index_profile: str | None
    chunks: list[ChunkSpan]
    chunk_status: str
