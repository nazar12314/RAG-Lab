from fastapi import FastAPI

from backend.app.api.analysis import router as analysis_router
from backend.app.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="GraphRAG Lab API", version="0.1.0")
    app.include_router(health_router)
    app.include_router(analysis_router)
    return app


app = create_app()
