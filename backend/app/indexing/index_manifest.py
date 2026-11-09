"""Identity of an index: which corpus, chunking and embedding model produced it."""

from __future__ import annotations

import hashlib
import json
from typing import Any

# Bump when the text handed to BM25 and the embedder changes shape.
INDEXED_TEXT_VERSION = 1


def profile_id(dataset: str, chunker: str, config: dict[str, Any], embedding_model: str) -> str:
    return f"{dataset}-{chunker}-{config['max_chars']}-{embedding_model}"


def content_hash(
    corpus_hash: str, chunker: str, config: dict[str, Any], embedding_model: str, dim: int
) -> str:
    identity = {
        "corpus_hash": corpus_hash,
        "chunker": chunker,
        "config": config,
        "embedding_model": embedding_model,
        "embedding_dim": dim,
        "indexed_text_version": INDEXED_TEXT_VERSION,
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
