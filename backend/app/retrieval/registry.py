"""The one place retrieval strategies are registered."""

from __future__ import annotations

from collections.abc import Callable

from backend.app.indexing.embeddings import Embedder
from backend.app.retrieval.base import Retriever
from backend.app.retrieval.hybrid import HybridRetriever
from backend.app.retrieval.keyword import BM25Retriever
from backend.app.retrieval.vector import VectorRetriever
from backend.app.storage.search import PostgresSearchStore


def build_retrievers(
    store: PostgresSearchStore, embedder_for: Callable[[str], Embedder]
) -> dict[str, Retriever]:
    bm25 = BM25Retriever(store)
    vector = VectorRetriever(store, embedder_for)
    return {
        "bm25": bm25,
        "vector": vector,
        "hybrid": HybridRetriever({"bm25": bm25, "vector": vector}),
    }
