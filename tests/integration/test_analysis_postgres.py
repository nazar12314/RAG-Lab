import pytest

from backend.app.config import get_settings
from backend.app.models.analysis import FilterSet, RecordType
from backend.app.services.analysis_service import AnalysisService
from backend.app.storage.analysis import PostgresAnalysisSource
from backend.app.storage.postgres import create_db_engine
from tests.support import SeedFileAnalysisSource

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def postgres_service():
    source = PostgresAnalysisSource(create_db_engine(get_settings().database_url))
    if not source.dataset_versions():
        pytest.skip("no dataset loaded; run `make seed`")
    return AnalysisService(source)


def test_postgres_and_seed_files_give_the_same_analysis(postgres_service):
    seed_service = AnalysisService(SeedFileAnalysisSource())
    pg_ref = postgres_service.resolve("engineering-ops-v1")
    seed_ref = seed_service.resolve("engineering-ops-v1")

    pg = postgres_service.overview(pg_ref, FilterSet())
    seed = seed_service.overview(seed_ref, FilterSet())
    assert [(c.id, c.value) for c in pg.cards] == [(c.id, c.value) for c in seed.cards]
    assert [c.rows for c in pg.charts] == [c.rows for c in seed.charts]

    f = FilterSet(service="SVC-PAYMENTS-API", q="pool")
    for rt in RecordType:
        assert (
            postgres_service.records(pg_ref, rt, f).total
            == seed_service.records(seed_ref, rt, f).total
        )


def test_document_detail_from_postgres(postgres_service):
    ref = postgres_service.resolve("engineering-ops-v1")
    doc = postgres_service.document(ref, "DOC-PM-INC-104")
    assert doc.highlights and doc.chunks == []
    assert "Not indexed" in doc.chunk_status
