"""Graph retrieval: link entities, walk typed edges, return the evidence behind them."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from backend.app.indexing.chunkers import indexed_text
from backend.app.models.contracts import (
    EntityRef,
    Evidence,
    GraphPath,
    RetrievalRequest,
    RetrievalResult,
)
from backend.app.retrieval.base import Unsupported
from backend.app.retrieval.keyword import tokenize
from backend.app.storage.graph import GraphEdge, GraphEntity
from backend.app.storage.search import StoredChunk

MAX_PATHS = 10
MAX_SUPPORTS = 3
REFUTED_WEIGHT = 0.3
# Keeps a directly connected chunk rankable even when it shares no word with the question.
BASE_RELEVANCE = 0.2

NO_ENTITY_MESSAGE = (
    "No known entity name or ID was found in the question, so there is no place to start."
)


class GraphSource(Protocol):
    def curated_version(self, dataset: str) -> str | None: ...

    def alias_matches(self, version: str, text_norm: str) -> list[tuple[str, GraphEntity]]: ...

    def walks(self, version: str, seeds: Sequence[str], hops: int) -> list[tuple[int, ...]]: ...

    def edges(self, relation_ids: Sequence[int]) -> dict[int, GraphEdge]: ...

    def evidence_chunks(
        self, profile_id: str, relation_ids: Sequence[int]
    ) -> list[tuple[int, StoredChunk]]: ...


@dataclass(frozen=True)
class EntityLink:
    entity: GraphEntity
    mention: str


def link_entities(text: str, matches: list[tuple[str, GraphEntity]]) -> list[EntityLink]:
    """Longest aliases win their span; an ambiguous alias keeps every entity it names."""
    norm = text.casefold()
    taken: list[tuple[int, int]] = []
    span_of: dict[str, tuple[int, int]] = {}
    links: list[EntityLink] = []
    seen: set[str] = set()
    for alias, entity in sorted(matches, key=lambda m: (-len(m[0]), m[0], m[1].key)):
        found = span_of.get(alias)
        if found is None:
            pattern = rf"(?<![\w-]){re.escape(alias)}(?![\w-])"
            for match in re.finditer(pattern, norm):
                span = match.span()
                if not any(span[0] < end and start < span[1] for start, end in taken):
                    found = span
                    taken.append(span)
                    span_of[alias] = span
                    break
        if found is not None and entity.key not in seen:
            seen.add(entity.key)
            links.append(EntityLink(entity, alias))
    return links


def _relevance(terms: set[str], chunk: StoredChunk) -> float:
    if not terms:
        return 0.0
    found = set(tokenize(indexed_text(chunk.title, chunk.section_path, chunk.text)))
    return len(terms & found) / len(terms)


def _reliability(edge: GraphEdge) -> float:
    return edge.confidence * (REFUTED_WEIGHT if edge.verified_status == "refuted" else 1.0)


class GraphRetriever:
    label = "Graph"
    description = "Starts from entities named in the question and follows their relationships."

    def __init__(self, store: GraphSource) -> None:
        self.store = store

    def _version(self, dataset: str) -> str:
        version = self.store.curated_version(dataset)
        if version is None:
            raise Unsupported(f"No curated graph is loaded for {dataset}.")
        return version

    def resolve(self, dataset: str, text: str) -> list[EntityLink]:
        matches = self.store.alias_matches(self._version(dataset), text.casefold())
        return link_entities(text, matches)

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        links = self.resolve(request.index.dataset_version_id, request.question)
        if not links:
            raise Unsupported(NO_ENTITY_MESSAGE)
        return self.expand(request, links)

    def expand(self, request: RetrievalRequest, links: list[EntityLink]) -> RetrievalResult:
        version = self._version(request.index.dataset_version_id)
        seeds = [link.entity.key for link in links]
        walks = self.store.walks(version, seeds, request.hop_limit)
        relation_ids = sorted({relation for walk in walks for relation in walk})
        metadata = {
            "graph_version": version,
            "hop_limit": request.hop_limit,
            "walks": len(walks),
            "edges": len(relation_ids),
        }
        entities = [
            EntityRef(
                key=link.entity.key,
                name=link.entity.name,
                entity_type=link.entity.entity_type,
                mention=link.mention,
            )
            for link in links
        ]
        if not relation_ids:
            return RetrievalResult(evidence=[], entities=entities, metadata=metadata)

        edges = self.store.edges(relation_ids)
        depth: dict[int, int] = {}
        for walk in walks:
            for relation in walk:
                depth[relation] = min(depth.get(relation, len(walk)), len(walk))

        chunks: dict[tuple[str, int], StoredChunk] = {}
        supporting: dict[tuple[str, int], list[int]] = {}
        for relation, chunk in self.store.evidence_chunks(request.index.id, relation_ids):
            key = (chunk.document_id, chunk.ordinal)
            chunks[key] = chunk
            supporting.setdefault(key, []).append(relation)

        terms = set(tokenize(request.question))
        scores = {
            key: (BASE_RELEVANCE + _relevance(terms, chunk))
            * max(_reliability(edges[r]) / depth[r] for r in supporting[key])
            for key, chunk in chunks.items()
        }
        ranked = sorted(scores, key=lambda key: (-scores[key], key))[: request.top_k]
        evidence = [
            self._evidence(chunks[key], rank, scores[key], supporting[key], edges, depth)
            for rank, key in enumerate(ranked, start=1)
        ]
        used = {relation for key in ranked for relation in supporting[key]}
        return RetrievalResult(
            evidence=evidence,
            graph_paths=self._paths(walks, edges, used),
            entities=entities,
            metadata=metadata,
        )

    @staticmethod
    def _evidence(
        chunk: StoredChunk,
        rank: int,
        score: float,
        relations: list[int],
        edges: dict[int, GraphEdge],
        depth: dict[int, int],
    ) -> Evidence:
        nearest = sorted(set(relations), key=lambda r: (depth[r], r))[:MAX_SUPPORTS]
        return Evidence(
            document_id=chunk.document_id,
            document_title=chunk.title,
            doc_type=chunk.doc_type,
            source_uri=chunk.source_uri,
            created_at=chunk.created_at,
            section_path=chunk.section_path,
            text=chunk.text,
            span_start=chunk.span_start,
            span_end=chunk.span_end,
            rank=rank,
            score=score,
            supports=[edges[r].statement for r in nearest],
        )

    @staticmethod
    def _paths(
        walks: list[tuple[int, ...]], edges: dict[int, GraphEdge], used: set[int]
    ) -> list[GraphPath]:
        """Walks fully backed by the selected evidence, longest first to show whole chains."""
        relevant = [walk for walk in walks if used.issuperset(walk)]
        relevant.sort(key=lambda walk: (-len(walk), walk))
        return [
            GraphPath(
                steps=[edges[r].statement for r in walk],
                hops=len(walk),
                refuted=any(edges[r].verified_status == "refuted" for r in walk),
            )
            for walk in relevant[:MAX_PATHS]
        ]
