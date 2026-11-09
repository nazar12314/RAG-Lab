"""Cosine similarity over pgvector embeddings of an index profile."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from backend.app.indexing.embeddings import Embedder
from backend.app.models.contracts import Evidence, RetrievalRequest, RetrievalResult, Usage
from backend.app.retrieval.base import Unsupported
from backend.app.storage.search import StoredChunk


class VectorSource(Protocol):
    def nearest(
        self, profile_id: str, vector: list[float], top_k: int
    ) -> list[tuple[StoredChunk, float]]: ...


class VectorRetriever:
    label = "Vector"
    description = "Ranks chunks by embedding similarity, so paraphrases can match."

    def __init__(self, store: VectorSource, embedder_for: Callable[[str], Embedder]) -> None:
        self.store = store
        self.embedder_for = embedder_for

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        model = request.index.embedding_model
        if model is None:
            raise Unsupported(f"Index {request.index.id} was built without embeddings.")
        # The question must be embedded by the model the index was built with.
        embeddings = self.embedder_for(model).embed([request.question])
        found = self.store.nearest(request.index.id, embeddings.vectors[0], request.top_k)
        evidence = [
            Evidence(
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
                score=similarity,
            )
            for rank, (chunk, similarity) in enumerate(found, start=1)
        ]
        return RetrievalResult(
            evidence=evidence,
            usage=Usage(embedding_tokens=embeddings.tokens),
            metadata={"embedding_model": model, "distance": "cosine", "search": "exact"},
        )
