"""Read-only analysis over one dataset snapshot: summaries, records, details, export."""

from __future__ import annotations

import threading
from typing import Any, Protocol

from backend.app.analysis import details
from backend.app.analysis.details import NotFound
from backend.app.analysis.graph import DEFAULT_MAX_EDGES, DEFAULT_MAX_NODES, graph_index
from backend.app.analysis.overview import SEVERITY_LABEL, build_overview
from backend.app.analysis.records import COLUMNS, apply_filters, base_frame, sort_page, to_items
from backend.app.analysis.snapshot import Snapshot, build_snapshot
from backend.app.models.analysis import (
    DatasetInfo,
    DatasetRef,
    DocumentDetail,
    FacetOption,
    Facets,
    FilterSet,
    GraphInfo,
    GraphView,
    IndexInfo,
    NodeMatch,
    Overview,
    PathResult,
    RecordDetail,
    RecordPage,
    RecordType,
    TraversalFilter,
)

MAX_PAGE_SIZE = 200
EXPORT_LIMIT = 10_000


class IncompatibleSnapshot(ValueError):
    """Raised when a graph or index profile does not belong to the requested dataset."""


class AnalysisSource(Protocol):
    def dataset_versions(self) -> list[dict[str, Any]]: ...
    def graph_versions(self, dataset: str) -> list[dict[str, Any]]: ...
    def index_profiles(self, dataset: str) -> list[dict[str, Any]]: ...
    def snapshot_rows(self, graph: str) -> dict[str, list[dict[str, Any]]]: ...
    def search_document_ids(self, query: str) -> set[str]: ...
    def chunks(self, index_profile: str, document_id: str) -> list[dict[str, Any]]: ...


class AnalysisService:
    def __init__(self, source: AnalysisSource) -> None:
        self.source = source
        self._cache: dict[tuple[str, str, str], Snapshot] = {}
        self._lock = threading.Lock()

    def datasets(self) -> list[DatasetInfo]:
        out = []
        for d in self.source.dataset_versions():
            out.append(
                DatasetInfo(
                    **{
                        k: d[k]
                        for k in (
                            "id",
                            "company",
                            "as_of",
                            "period_start",
                            "period_end",
                            "corpus_hash",
                            "loaded_at",
                        )
                    },
                    graphs=[GraphInfo(**g) for g in self.source.graph_versions(d["id"])],
                    index_profiles=[IndexInfo(**p) for p in self.source.index_profiles(d["id"])],
                )
            )
        return out

    def resolve(self, dataset: str, graph: str | None = None) -> DatasetRef:
        """Validates the dataset/graph pair; defaults to the curated graph."""
        versions = {d["id"] for d in self.source.dataset_versions()}
        if dataset not in versions:
            raise NotFound(f"dataset {dataset} is not loaded")
        graphs = self.source.graph_versions(dataset)
        if not graphs:
            raise NotFound(f"dataset {dataset} has no graph version")
        if graph is None:
            graph = next((g["id"] for g in graphs if g["kind"] == "curated"), graphs[0]["id"])
        elif graph not in {g["id"] for g in graphs}:
            raise IncompatibleSnapshot(f"graph {graph} does not belong to dataset {dataset}")
        return DatasetRef(dataset=dataset, graph=graph)

    def snapshot(self, ref: DatasetRef) -> Snapshot:
        dataset = next(d for d in self.source.dataset_versions() if d["id"] == ref.dataset)
        # loaded_at changes on every reseed, which invalidates the cached snapshot.
        key = (ref.dataset, ref.graph, str(dataset["loaded_at"]))
        with self._lock:
            if key not in self._cache:
                self._cache = {k: v for k, v in self._cache.items() if k[:2] != key[:2]}
                graph = next(
                    g for g in self.source.graph_versions(ref.dataset) if g["id"] == ref.graph
                )
                self._cache[key] = build_snapshot(
                    dataset,
                    graph,
                    self.source.index_profiles(ref.dataset),
                    self.source.snapshot_rows(ref.graph),
                )
            return self._cache[key]

    def _document_matches(self, f: FilterSet) -> set[str] | None:
        return self.source.search_document_ids(f.q.strip()) if f.q and f.q.strip() else None

    def facets(self, ref: DatasetRef) -> Facets:
        s = self.snapshot(ref)

        def options(series, labels=None) -> list[FacetOption]:
            counts = series.value_counts()
            return [
                FacetOption(value=str(v), label=(labels or {}).get(v, str(v)), count=int(c))
                for v, c in sorted(counts.items(), key=lambda kv: str(kv[0]))
            ]

        dates = [
            s.documents["created_at"].min(),
            s.incidents["started_at"].min(),
            s.deployments["deployed_at"].min(),
        ]
        ends = [
            s.documents["created_at"].max(),
            s.incidents["started_at"].max(),
            s.deployments["deployed_at"].max(),
        ]
        return Facets(
            services=sorted(
                (
                    FacetOption(value=r.id, label=r.name, count=int(r.incidents))
                    for r in base_frame(s, RecordType.services).itertuples()
                ),
                key=lambda o: o.label,
            ),
            doc_types=options(s.documents["doc_type"]),
            severities=[
                FacetOption(value=str(k), label=SEVERITY_LABEL[int(k)], count=int(v))
                for k, v in s.incidents["severity"].value_counts().sort_index().items()
            ],
            entity_types=options(s.entities["entity_type"]),
            relation_types=options(s.relations["relation_type"]),
            date_min=min(dates).date(),
            date_max=max(ends).date(),
        )

    def overview(self, ref: DatasetRef, f: FilterSet) -> Overview:
        return build_overview(self.snapshot(ref), ref, f, self._document_matches(f))

    def records(
        self,
        ref: DatasetRef,
        rt: RecordType,
        f: FilterSet,
        offset: int = 0,
        limit: int = 50,
        sort: str | None = None,
        descending: bool | None = None,
    ) -> RecordPage:
        s = self.snapshot(ref)
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        df, applied, ignored = apply_filters(s, rt, f, self._document_matches(f))
        page, column, desc = sort_page(df, rt, sort, descending, max(0, offset), limit)
        columns = COLUMNS[rt]
        return RecordPage(
            ref=ref,
            record_type=rt,
            filters=f,
            applied_filters=applied,
            ignored_filters=ignored,
            total=len(df),
            unfiltered_total=len(base_frame(s, rt)),
            offset=max(0, offset),
            limit=limit,
            sort=column,
            descending=desc,
            columns=columns,
            items=to_items(page, columns),
        )

    def export(
        self,
        ref: DatasetRef,
        rt: RecordType,
        f: FilterSet,
        sort: str | None = None,
        descending: bool | None = None,
    ) -> tuple[list[str], list[dict[str, Any]], int]:
        s = self.snapshot(ref)
        df, _, _ = apply_filters(s, rt, f, self._document_matches(f))
        page, _, _ = sort_page(df, rt, sort, descending, 0, EXPORT_LIMIT)
        return COLUMNS[rt], to_items(page, COLUMNS[rt]), len(df)

    def record(self, ref: DatasetRef, rt: RecordType, record_id: str) -> RecordDetail:
        return details.record_detail(self.snapshot(ref), ref, rt, record_id)

    def document(
        self, ref: DatasetRef, document_id: str, index_profile: str | None = None
    ) -> DocumentDetail:
        s = self.snapshot(ref)
        chunks: list[dict[str, Any]] = []
        if index_profile is not None:
            if index_profile not in {p["id"] for p in s.index_profiles}:
                raise IncompatibleSnapshot(
                    f"index profile {index_profile} does not belong to dataset {ref.dataset}"
                )
            chunks = self.source.chunks(index_profile, document_id)
        return details.document_detail(s, ref, document_id, index_profile, chunks)

    def graph_search(self, ref: DatasetRef, query: str, limit: int = 20) -> list[NodeMatch]:
        return graph_index(self.snapshot(ref)).search(query, limit)

    def graph_neighborhood(
        self,
        ref: DatasetRef,
        node: str,
        depth: int,
        f: TraversalFilter,
        expand: list[str] | None = None,
        max_nodes: int = DEFAULT_MAX_NODES,
        max_edges: int = DEFAULT_MAX_EDGES,
    ) -> GraphView:
        return graph_index(self.snapshot(ref)).neighborhood(
            ref, node, depth, f, expand, max_nodes, max_edges
        )

    def graph_path(
        self,
        ref: DatasetRef,
        source: str,
        target: str,
        f: TraversalFilter,
        directed: bool,
        limit: int = 5,
    ) -> PathResult:
        return graph_index(self.snapshot(ref)).paths(ref, source, target, f, directed, limit)
