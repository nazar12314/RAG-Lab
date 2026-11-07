import pytest
from sqlalchemy import text

from backend.app.config import get_settings
from backend.app.storage.postgres import create_db_engine

pytestmark = pytest.mark.integration


def test_pgvector_extension_installed():
    engine = create_db_engine(get_settings().database_url)
    with engine.connect() as conn:
        installed = conn.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).scalar()

    assert installed == 1
