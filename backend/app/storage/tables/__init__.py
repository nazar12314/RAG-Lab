"""ORM table definitions, grouped by PostgreSQL schema.

corpus  - business records and source documents (retriever-facing)
search  - index profiles, chunks, embeddings, full-text vectors (retriever-facing)
graph   - versioned knowledge graphs with provenance (retriever-facing)
eval    - gold labels and experiment history (evaluation only)
"""

from backend.app.storage.tables import corpus, eval, graph, search

SCHEMAS = ("corpus", "search", "graph", "eval")
RETRIEVER_SCHEMAS = ("corpus", "search", "graph")
RETRIEVER_ROLE = "raglab_retriever"

__all__ = ["corpus", "eval", "graph", "search", "SCHEMAS", "RETRIEVER_SCHEMAS", "RETRIEVER_ROLE"]
