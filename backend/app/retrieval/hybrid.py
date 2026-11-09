"""Reciprocal Rank Fusion over existing retrievers.

RRF uses only ranks, so BM25 scores and cosine similarities never need calibrating.
"""

from __future__ import annotations

from backend.app.models.contracts import Evidence, RetrievalRequest, RetrievalResult, Usage
from backend.app.retrieval.base import Retriever

RRF_K = 60
MIN_DEPTH = 50


def fuse(rankings: dict[str, list[Evidence]], top_k: int, k: int = RRF_K) -> list[Evidence]:
    scores: dict[str, float] = {}
    merged: dict[str, Evidence] = {}
    details: dict[str, dict[str, int]] = {}
    for component, evidence in rankings.items():
        for item in evidence:
            key = item.evidence_id
            scores[key] = scores.get(key, 0.0) + 1 / (k + item.rank)
            details.setdefault(key, {})[component] = item.rank
            known = merged.get(key)
            if known is None or (item.matched_terms and not known.matched_terms):
                merged[key] = item
    ordered = sorted(scores, key=lambda key: (-scores[key], key))
    return [
        merged[key].model_copy(
            update={"rank": rank, "score": scores[key], "rank_details": details[key]}
        )
        for rank, key in enumerate(ordered[:top_k], start=1)
    ]


class HybridRetriever:
    label = "Hybrid"
    description = "Merges the BM25 and vector rankings with reciprocal rank fusion."

    def __init__(self, components: dict[str, Retriever]) -> None:
        self.components = components

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        # Each side looks deeper than top_k: a chunk ranked mid-list by both can win the fusion.
        depth = max(request.top_k * 4, MIN_DEPTH)
        deeper = request.model_copy(update={"top_k": depth})
        results = {name: r.retrieve(deeper) for name, r in self.components.items()}
        return RetrievalResult(
            evidence=fuse({name: r.evidence for name, r in results.items()}, request.top_k),
            usage=Usage(embedding_tokens=sum(r.usage.embedding_tokens for r in results.values())),
            metadata={
                "rrf_k": RRF_K,
                "depth": depth,
                "components": {name: r.metadata for name, r in results.items()},
            },
        )
