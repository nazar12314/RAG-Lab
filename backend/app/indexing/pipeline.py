"""Builds an index profile: load documents, chunk, embed, persist.

Usage: python -m backend.app.indexing.pipeline [--max-chars N] [--force]
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass

from backend.app.config import get_settings
from backend.app.indexing import index_manifest
from backend.app.indexing.chunkers import Chunker, SectionChunker, indexed_text
from backend.app.indexing.embeddings import Embedder, OpenAIEmbedder
from backend.app.storage.documents import PostgresDocumentStore, SourceDocument
from backend.app.storage.postgres import create_db_engine
from backend.app.storage.search import NewChunk, PostgresSearchStore
from backend.app.storage.tables.search import EMBEDDING_DIM


@dataclass(frozen=True)
class BuildReport:
    profile_id: str
    skipped: bool
    documents: int = 0
    chunks: int = 0
    embedding_tokens: int = 0


def build_chunks(
    documents: Sequence[SourceDocument], chunker: Chunker, embedder: Embedder
) -> tuple[list[NewChunk], int]:
    located = [
        (document, ordinal, chunk)
        for document in documents
        for ordinal, chunk in enumerate(chunker.split(document.content))
    ]
    texts = [indexed_text(d.title, c.section_path, c.text) for d, _, c in located]
    embeddings = embedder.embed(texts)
    if len(embeddings.vectors) != len(texts):
        raise RuntimeError(f"expected {len(texts)} embeddings, got {len(embeddings.vectors)}")
    if embeddings.vectors and len(embeddings.vectors[0]) != EMBEDDING_DIM:
        raise RuntimeError(
            f"{embedder.model} returned {len(embeddings.vectors[0])} dimensions; "
            f"the column holds {EMBEDDING_DIM}"
        )
    chunks = [
        NewChunk(
            document_id=document.id,
            ordinal=ordinal,
            text=chunk.text,
            span_start=chunk.span_start,
            span_end=chunk.span_end,
            section_path=chunk.section_path,
            token_count=embedder.count_tokens(text),
            embedding=vector,
        )
        for (document, ordinal, chunk), text, vector in zip(
            located, texts, embeddings.vectors, strict=True
        )
    ]
    return chunks, embeddings.tokens


def build_index(
    dataset: str,
    documents: PostgresDocumentStore,
    search: PostgresSearchStore,
    chunker: Chunker,
    embedder: Embedder,
    force: bool = False,
) -> BuildReport:
    corpus_hash = documents.corpus_hash(dataset)
    if corpus_hash is None:
        raise RuntimeError(f"dataset {dataset} is not loaded; run `make seed` first")
    profile_id = index_manifest.profile_id(dataset, chunker.name, chunker.config, embedder.model)
    content_hash = index_manifest.content_hash(
        corpus_hash, chunker.name, chunker.config, embedder.model, EMBEDDING_DIM
    )
    existing = search.profile(profile_id)
    if (
        not force
        and existing is not None
        and existing.status == "ready"
        and existing.content_hash == content_hash
    ):
        return BuildReport(profile_id, skipped=True)

    source = documents.documents()
    chunks, tokens = build_chunks(source, chunker, embedder)
    search.replace_index(
        {
            "id": profile_id,
            "dataset_version_id": dataset,
            "chunker": chunker.name,
            "chunker_config": chunker.config,
            "embedding_model": embedder.model,
            "embedding_dim": EMBEDDING_DIM,
            "content_hash": content_hash,
        },
        chunks,
    )
    return BuildReport(profile_id, False, len(source), len(chunks), tokens)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-chars", type=int, default=SectionChunker.max_chars)
    parser.add_argument("--force", action="store_true", help="rebuild even if up to date")
    args = parser.parse_args()

    settings = get_settings()
    if settings.openai_api_key is None:
        raise SystemExit("OPENAI_API_KEY is required to build embeddings")
    engine = create_db_engine(settings.database_url)
    report = build_index(
        settings.dataset_version,
        PostgresDocumentStore(engine),
        PostgresSearchStore(engine),
        SectionChunker(max_chars=args.max_chars),
        OpenAIEmbedder(settings.openai_api_key.get_secret_value(), settings.openai_embedding_model),
        force=args.force,
    )
    if report.skipped:
        print(f"{report.profile_id}: already up to date")
    else:
        print(
            f"{report.profile_id}: {report.chunks} chunks from {report.documents} documents, "
            f"{report.embedding_tokens} embedding tokens"
        )


if __name__ == "__main__":
    main()
