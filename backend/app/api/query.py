"""Retrieval playground endpoints. New strategies need registration, not new routes."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.app.config import get_settings
from backend.app.generation.answer import AnswerGenerator, OpenAIChat
from backend.app.indexing.embeddings import Embedder, OpenAIEmbedder
from backend.app.models.contracts import (
    CompareRequest,
    CompareResponse,
    ExampleQuestion,
    PlaygroundOptions,
    QueryRequest,
    QueryResponse,
)
from backend.app.retrieval.base import Unsupported
from backend.app.retrieval.registry import build_retrievers
from backend.app.services.query_service import QueryService, UnknownStrategy
from backend.app.storage.examples import PostgresExampleStore
from backend.app.storage.postgres import create_db_engine
from backend.app.storage.search import PostgresSearchStore

router = APIRouter(tags=["query"])


@lru_cache
def get_query_service() -> QueryService:
    settings = get_settings()
    store = PostgresSearchStore(create_db_engine(settings.database_url))
    key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None

    @lru_cache
    def embedder_for(model: str) -> Embedder:
        if key is None:
            raise Unsupported("OPENAI_API_KEY is not set, so questions cannot be embedded.")
        return OpenAIEmbedder(key, model)

    return QueryService(
        build_retrievers(store, embedder_for),
        store,
        AnswerGenerator(OpenAIChat(key, settings.openai_chat_model)) if key else None,
        settings.dataset_version,
        settings.default_top_k,
    )


@lru_cache
def get_example_store() -> PostgresExampleStore:
    return PostgresExampleStore(create_db_engine(get_settings().database_url))


Service = Annotated[QueryService, Depends(get_query_service)]
Examples = Annotated[PostgresExampleStore, Depends(get_example_store)]


@router.get("/query/options")
def options(service: Service) -> PlaygroundOptions:
    return service.options()


@router.get("/examples")
def examples(store: Examples) -> list[ExampleQuestion]:
    return store.showcase()


@router.post("/query")
def query(request: QueryRequest, service: Service) -> QueryResponse:
    try:
        return service.query(request)
    except UnknownStrategy as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/query/compare")
def compare(request: CompareRequest, service: Service) -> CompareResponse:
    try:
        return service.compare(request)
    except UnknownStrategy as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
