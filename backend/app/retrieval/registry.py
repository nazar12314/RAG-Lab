"""The one place retrieval strategies are registered."""

from __future__ import annotations

from collections.abc import Callable

from langchain_core.language_models import BaseChatModel

from backend.app.agent.runner import AgentRetriever
from backend.app.agent.tools import AgentData, BusinessRecords, DocumentSource
from backend.app.indexing.embeddings import Embedder
from backend.app.retrieval.base import Retriever
from backend.app.retrieval.graph import GraphRetriever, GraphSource
from backend.app.retrieval.hybrid import HybridRetriever
from backend.app.retrieval.keyword import BM25Retriever
from backend.app.retrieval.vector import VectorRetriever
from backend.app.storage.search import PostgresSearchStore


def build_retrievers(
    store: PostgresSearchStore,
    graph: GraphSource,
    embedder_for: Callable[[str], Embedder],
    records: BusinessRecords | None = None,
    documents: DocumentSource | None = None,
    agent_model: BaseChatModel | None = None,
    agent_model_name: str = "",
) -> dict[str, Retriever]:
    bm25 = BM25Retriever(store)
    vector = VectorRetriever(store, embedder_for)
    graph_retriever = GraphRetriever(graph)
    retrievers: dict[str, Retriever] = {
        "bm25": bm25,
        "vector": vector,
        "hybrid": HybridRetriever({"bm25": bm25, "vector": vector}),
        "graph": graph_retriever,
    }
    if records is not None and documents is not None:
        # The agent's tools are these same retriever instances, so the modes cannot drift apart.
        retrievers["agent"] = AgentRetriever(
            AgentData(bm25, vector, graph_retriever, records, documents),
            agent_model,
            agent_model_name,
        )
    return retrievers
