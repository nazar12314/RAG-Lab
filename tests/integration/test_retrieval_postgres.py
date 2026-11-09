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
from backend.app.retrieval.graph import GraphRetriever
from backend.app.retrieval.keyword import BM25Retriever
from backend.app.retrieval.vector import VectorRetriever
from backend.app.storage.business import PostgresBusinessRepository, RecordFilter
from backend.app.storage.documents import PostgresDocumentStore
from backend.app.storage.examples import PostgresExampleStore
from backend.app.storage.graph import PostgresGraphStore
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


def graph_retriever(engine):
    return GraphRetriever(PostgresGraphStore(engine))


def test_entities_resolve_from_names_and_aliases(built):
    engine, *_ = built
    links = graph_retriever(engine).resolve(DATASET, "Did payment-service break INC-104?")
    assert {"SVC-PAYMENTS-API", "INC-104"} <= {link.entity.key for link in links}


def test_walks_respect_the_hop_limit_and_never_repeat_a_node(built):
    engine, *_ = built
    store = PostgresGraphStore(engine)
    version = store.curated_version(DATASET)
    for hops in (1, 2):
        walks = store.walks(version, ["SVC-CHECKOUT-API"], hops)
        assert walks and max(len(walk) for walk in walks) == hops
    assert all(len(set(walk)) == len(walk) for walk in walks)


def test_walks_do_not_pass_through_a_shared_team(built):
    engine, *_ = built
    store = PostgresGraphStore(engine)
    version = store.curated_version(DATASET)
    walks = store.walks(version, ["SVC-CHECKOUT-API"], 2)
    edges = store.edges(sorted({r for walk in walks for r in walk}))
    middle_owned = [
        walk
        for walk in walks
        if len(walk) == 2
        and edges[walk[0]].relation_type == edges[walk[1]].relation_type == "OWNED_BY"
    ]
    assert middle_owned == []


def test_graph_retriever_follows_a_dependency_chain_to_its_evidence(built):
    engine, _, store, _, report = built
    result = graph_retriever(engine).retrieve(
        request_for(store, report, "What does the Checkout API depend on?", top_k=10)
    )
    assert result.entities[0].key == "SVC-CHECKOUT-API"
    assert any("DEPENDS_ON" in s for item in result.evidence for s in item.supports)
    assert result.graph_paths
    for path in result.graph_paths:
        assert path.nodes[0] == "SVC-CHECKOUT-API" and len(path.nodes) == path.hops + 1
        for step, edge in enumerate(path.edges):
            assert {edge.source, edge.target} == {path.nodes[step], path.nodes[step + 1]}
    assert result.metadata["hop_limit"] == 2


def test_graph_evidence_overlaps_the_span_behind_each_edge(built):
    engine, _, store, _, report = built
    result = graph_retriever(engine).retrieve(request_for(store, report, "INC-104", top_k=20))
    assert any(e.document_id == "DOC-PM-INC-104" for e in result.evidence)
    assert all(e.text and e.supports for e in result.evidence)


def test_incident_lookup_includes_affected_services_and_deployments(built):
    engine, *_ = built
    records = PostgresBusinessRepository(engine).lookup(
        "incident", RecordFilter(record_id="INC-104")
    )
    assert len(records) == 1
    assert records[0].ref == "incidents/INC-104"
    assert "Affected services" in records[0].text and "Severity: SEV" in records[0].text
    assert any(ref.startswith("incident_services/INC-104/") for ref in records[0].refs)


def test_deployments_for_a_service_are_newest_first(built):
    engine, *_ = built
    records = PostgresBusinessRepository(engine).lookup(
        "deployment", RecordFilter(service_id="SVC-PAYMENTS-API")
    )
    dates = [record.created_at for record in records]
    assert dates and dates == sorted(dates, reverse=True)


def test_service_record_lists_its_dependencies(built):
    engine, *_ = built
    records = PostgresBusinessRepository(engine).lookup(
        "service", RecordFilter(record_id="SVC-CHECKOUT-API")
    )
    assert "Depends on" in records[0].text
    assert any(ref.startswith("service_dependencies/") for ref in records[0].refs)


def test_ids_are_parameters_not_sql(built):
    engine, *_ = built
    repo = PostgresBusinessRepository(engine)
    assert repo.lookup("incident", RecordFilter(record_id="' OR 1=1 --")) == []


def test_aggregate_counts_match_the_loaded_records(built):
    engine, *_ = built
    result = PostgresBusinessRepository(engine).aggregate("incidents", ["severity"], RecordFilter())
    assert result.total == 38
    assert sum(row["count"] for row in result.rows) == 38
    assert {row["severity"] for row in result.rows} == {1, 2, 3, 4}


def test_aggregate_filters_and_groups_by_month(built):
    engine, *_ = built
    repo = PostgresBusinessRepository(engine)
    severe = repo.aggregate("incidents", ["month"], RecordFilter(severity=(1,)))
    assert severe.total == 4 and len(severe.refs) == 4
    assert all(len(row["month"]) == 7 for row in severe.rows)


def test_primary_service_filter_is_narrower_than_affected(built):
    engine, *_ = built
    repo = PostgresBusinessRepository(engine)
    service = "SVC-PAYMENTS-API"
    affected = repo.aggregate("incidents", [], RecordFilter(service_id=service))
    primary = repo.aggregate(
        "incidents", [], RecordFilter(service_id=service, primary_service_only=True)
    )
    # 5 includes INC-131, which the dataset deliberately records under the wrong primary service.
    assert primary.total == 5 and affected.total > primary.total


def test_aggregate_rejects_columns_outside_the_template(built):
    engine, *_ = built
    with pytest.raises(ValueError, match="cannot be grouped"):
        PostgresBusinessRepository(engine).aggregate("incidents", ["kind"], RecordFilter())


def test_full_document_is_readable_by_id(built):
    _, documents, *_ = built
    assert documents.document("DOC-PM-INC-104").title.startswith("Postmortem")
    assert documents.document("nope") is None


def test_showcase_examples_come_from_the_benchmark(built):
    engine, *_ = built
    examples = PostgresExampleStore(engine).showcase()
    assert len(examples) == 20
    assert examples[0].id == "Q-001"
