"""Exercises real SQL against a temporary index profile, removed afterwards."""

import hashlib

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from backend.app.config import get_settings
from backend.app.indexing.chunkers import SectionChunker, indexed_text
from backend.app.indexing.embeddings import Embeddings
from backend.app.indexing.pipeline import build_index
from backend.app.models.contracts import RetrievalRequest
from backend.app.retrieval.keyword import BM25Retriever
from backend.app.retrieval.vector import VectorRetriever
from backend.app.storage.documents import PostgresDocumentStore
from backend.app.storage.examples import PostgresExampleStore
from backend.app.storage.postgres import create_db_engine
from backend.app.storage.search import PostgresSearchStore
from backend.app.storage.tables.search import EMBEDDING_DIM

pytestmark = pytest.mark.integration

DATASET = "engineering-ops-v1"


def vector_for(text_: str) -> list[float]:
    digest = hashlib.sha256(text_.encode()).digest()
    return [digest[i % len(digest)] / 255 + 0.01 for i in range(EMBEDDING_DIM)]


class HashEmbedder:
    # Sorts after real models, so a running app keeps its default index during the test.
    model = "zz-test-hash"

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        return Embeddings([vector_for(t) for t in texts], tokens=len(texts))

    def count_tokens(self, text_):
        return len(text_.split())


@pytest.fixture(scope="module")
def built():
    engine = create_db_engine(get_settings().database_url)
    documents = PostgresDocumentStore(engine)
    if documents.corpus_hash(DATASET) is None:
        pytest.skip("no dataset loaded; run `make seed`")
    store = PostgresSearchStore(engine)
    embedder = HashEmbedder()
    report = build_index(DATASET, documents, store, SectionChunker(max_chars=900), embedder)
    yield engine, documents, store, embedder, report
    store.delete_profile(report.profile_id)


def request_for(store, report, question, top_k=5):
    return RetrievalRequest(question=question, index=store.profile(report.profile_id), top_k=top_k)


def test_build_covers_every_document_and_stores_exact_spans(built):
    engine, _, store, _, report = built
    profile = store.profile(report.profile_id)
    assert profile.status == "ready" and profile.chunk_count == report.chunks > 0
    assert report.documents == 138
    with engine.connect() as conn:
        mismatched = conn.scalar(
            text(
                "SELECT count(*) FROM search.document_chunks c "
                "JOIN corpus.documents d ON d.id = c.document_id "
                "WHERE c.index_profile_id = :p "
                "AND substr(d.content, c.span_start + 1, c.span_end - c.span_start) <> c.text"
            ),
            {"p": report.profile_id},
        )
    assert mismatched == 0


def test_rebuilding_an_unchanged_index_is_a_no_op(built):
    _, documents, store, embedder, report = built
    calls = embedder.calls
    again = build_index(DATASET, documents, store, SectionChunker(max_chars=900), embedder)
    assert again.skipped and again.profile_id == report.profile_id
    assert embedder.calls == calls


def test_nearest_finds_the_chunk_with_the_identical_vector(built):
    _, _, store, _, report = built
    chunk = store.chunks(report.profile_id)[0]
    vector = vector_for(indexed_text(chunk.title, chunk.section_path, chunk.text))
    found = store.nearest(report.profile_id, vector, 3)
    assert found[0][0] == chunk
    assert found[0][1] == pytest.approx(1.0)
    assert len(found) == 3


def test_vector_retriever_reads_postgres(built):
    _, _, store, embedder, report = built
    result = VectorRetriever(store, lambda model: embedder).retrieve(
        request_for(store, report, "checkout timeouts", top_k=4)
    )
    assert [e.rank for e in result.evidence] == [1, 2, 3, 4]


def test_bm25_finds_an_incident_by_its_identifier(built):
    _, _, store, _, report = built
    result = BM25Retriever(store).retrieve(request_for(store, report, "INC-104"))
    assert "INC-104" in result.evidence[0].document_title
    assert "inc-104" in result.evidence[0].matched_terms


def test_retriever_connection_cannot_read_gold_labels(built):
    _, _, store, _, _ = built
    with pytest.raises(ProgrammingError), store._retriever_connection() as conn:
        conn.execute(text("SELECT count(*) FROM eval.questions"))


def test_showcase_examples_come_from_the_benchmark(built):
    engine, *_ = built
    examples = PostgresExampleStore(engine).showcase()
    assert len(examples) == 20
    assert examples[0].id == "Q-001"
