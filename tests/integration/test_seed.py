import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from backend.app.config import get_settings
from backend.app.dataset.load import load
from backend.app.storage.postgres import create_db_engine
from backend.app.storage.tables import RETRIEVER_ROLE

pytestmark = pytest.mark.integration


@pytest.fixture
def seeded():
    """Seeds inside a transaction that is rolled back, so the developer database is untouched."""
    engine = create_db_engine(get_settings().database_url)
    with engine.connect() as conn:
        trans = conn.begin()
        manifest = load(conn)
        yield conn, manifest
        trans.rollback()


def scalar(conn, sql: str):
    return conn.execute(text(sql)).scalar()


def test_counts_match_manifest(seeded):
    conn, manifest = seeded
    counts = manifest["counts"]
    for table in ("services", "deployments", "incidents", "documents"):
        assert scalar(conn, f"SELECT count(*) FROM corpus.{table}") == counts[table]
    assert scalar(conn, "SELECT count(*) FROM graph.relations") == counts["graph_curated.relations"]
    assert scalar(conn, "SELECT count(*) FROM eval.questions") == 80


def test_multi_hop_path_is_traversable(seeded):
    conn, _ = seeded
    path = (
        conn.execute(
            text("""
        SELECT t3.key
        FROM graph.entities s
        JOIN graph.relations r1 ON r1.source_entity_id = s.id AND r1.relation_type = 'DEPENDS_ON'
        JOIN graph.entities t1 ON t1.id = r1.target_entity_id AND t1.key = 'SVC-PAYMENTS-API'
        JOIN graph.relations r2 ON r2.source_entity_id = t1.id AND r2.relation_type = 'AFFECTED_BY'
        JOIN graph.entities t2 ON t2.id = r2.target_entity_id AND t2.key = 'INC-104'
        JOIN graph.relations r3 ON r3.source_entity_id = t2.id AND r3.relation_type = 'TRIGGERED_BY'
            AND r3.verified_status = 'verified'
        JOIN graph.entities t3 ON t3.id = r3.target_entity_id
        WHERE s.key = 'SVC-CHECKOUT-API'
    """)
        )
        .scalars()
        .all()
    )
    assert path == ["DPL-010"]


def test_retriever_role_cannot_read_gold_labels(seeded):
    conn, _ = seeded
    conn.execute(text("SAVEPOINT leak_check"))
    conn.execute(text(f"SET LOCAL ROLE {RETRIEVER_ROLE}"))
    assert scalar(conn, "SELECT count(*) FROM corpus.documents") > 0
    with pytest.raises(ProgrammingError, match="permission denied"):
        conn.execute(text("SELECT 1 FROM eval.questions LIMIT 1"))
    conn.execute(text("ROLLBACK TO SAVEPOINT leak_check"))
