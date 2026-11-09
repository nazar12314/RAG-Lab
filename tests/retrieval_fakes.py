"""In-memory stand-ins for the search store and model providers."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.app.generation.answer import Completion
from backend.app.indexing.embeddings import Embeddings
from backend.app.models.contracts import IndexProfile
from backend.app.storage.graph import GraphEdge, GraphEntity
from backend.app.storage.search import StoredChunk

BUILT_AT = datetime(2026, 11, 1, tzinfo=UTC)


def make_profile(profile_id: str = "test-index", built_at: datetime = BUILT_AT) -> IndexProfile:
    return IndexProfile(
        id=profile_id,
        dataset_version_id="engineering-ops-v1",
        chunker="section",
        chunker_config={"max_chars": 800},
        embedding_model="fake-embedding",
        embedding_dim=2,
        status="ready",
        chunk_count=3,
        content_hash="hash",
        built_at=built_at,
    )


def make_chunk(
    document_id: str, text: str, title: str = "A title", ordinal: int = 0
) -> StoredChunk:
    return StoredChunk(
        document_id=document_id,
        ordinal=ordinal,
        text=text,
        span_start=0,
        span_end=len(text),
        section_path="Section",
        title=title,
        doc_type="runbook",
        source_uri=f"docs/{document_id}.md",
        created_at=BUILT_AT,
    )


SAMPLE_CHUNKS = [
    make_chunk("DOC-1", "INC-104 was caused by connection pool exhaustion in payments."),
    make_chunk("DOC-2", "The hotel pool was closed for maintenance during the offsite."),
    make_chunk("DOC-3", "Customers could not finish purchases because requests timed out."),
]


class FakeStore:
    def __init__(self, chunks: list[StoredChunk] | None = None, ready: bool = True) -> None:
        self.stored = SAMPLE_CHUNKS if chunks is None else chunks
        self.ready = ready
        self.chunk_loads = 0

    def ready_profiles(self, dataset: str) -> list[IndexProfile]:
        return [make_profile()] if self.ready else []

    def chunks(self, profile_id: str) -> list[StoredChunk]:
        self.chunk_loads += 1
        return self.stored

    def nearest(
        self, profile_id: str, vector: list[float], top_k: int
    ) -> list[tuple[StoredChunk, float]]:
        return [(c, 0.9 - i / 10) for i, c in enumerate(self.stored[:top_k])]


POOL_ENTITY = GraphEntity("SVC-POOL", "Pool Service", "service")


def make_edge(edge_id: int, status: str = "verified", confidence: float = 1.0) -> GraphEdge:
    return GraphEdge(
        edge_id,
        f"A{edge_id}",
        f"B{edge_id}",
        "DEPENDS_ON",
        confidence,
        status,
        None,
        None,
        f"REL-{edge_id}",
        f"KEY-A{edge_id}",
        f"KEY-B{edge_id}",
        "service",
        "service",
    )


class FakeGraphStore:
    def __init__(
        self,
        version: str | None = "curated",
        walks: list[tuple[int, ...]] | None = None,
        edges: dict[int, GraphEdge] | None = None,
        evidence: list[tuple[int, StoredChunk]] | None = None,
    ) -> None:
        self.version = version
        self.walk_rows = [(1,), (2,), (1, 3)] if walks is None else walks
        self.edge_rows = edges or {i: make_edge(i) for i in (1, 2, 3)}
        self.evidence = (
            evidence
            if evidence is not None
            else [(1, SAMPLE_CHUNKS[0]), (2, SAMPLE_CHUNKS[1]), (3, SAMPLE_CHUNKS[2])]
        )
        self.walk_calls: list[tuple[list[str], int]] = []

    def curated_version(self, dataset: str) -> str | None:
        return self.version

    def alias_matches(self, version: str, text_norm: str) -> list[tuple[str, GraphEntity]]:
        return [("pool", POOL_ENTITY)] if "pool" in text_norm else []

    def walks(self, version: str, seeds, hops: int) -> list[tuple[int, ...]]:
        self.walk_calls.append((list(seeds), hops))
        return self.walk_rows

    def edges(self, relation_ids) -> dict[int, GraphEdge]:
        return self.edge_rows

    def evidence_chunks(self, profile_id: str, relation_ids) -> list[tuple[int, StoredChunk]]:
        return self.evidence


class FakeEmbedder:
    model = "fake-embedding"

    def embed(self, texts: list[str]) -> Embeddings:
        return Embeddings([[1.0, 0.0] for _ in texts], tokens=len(texts))

    def count_tokens(self, text: str) -> int:
        return len(text.split())


class FakeChat:
    model = "fake-chat"

    def __init__(self, reply: str = "It was the pool [1].") -> None:
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> Completion:
        self.calls.append((system, user))
        return Completion(self.reply, prompt_tokens=10, completion_tokens=5)
