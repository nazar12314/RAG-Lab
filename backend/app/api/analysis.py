"""Read-only /analysis endpoints for the Data Analysis module."""

from __future__ import annotations

import csv
import io
import json
from datetime import date
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.app.analysis.details import NotFound
from backend.app.config import get_settings
from backend.app.models.analysis import (
    DatasetInfo,
    DatasetRef,
    DocumentDetail,
    EvidenceFilter,
    Facets,
    FilterSet,
    Overview,
    RecordDetail,
    RecordPage,
    RecordType,
)
from backend.app.services.analysis_service import (
    MAX_PAGE_SIZE,
    AnalysisService,
    IncompatibleSnapshot,
)
from backend.app.storage.analysis import PostgresAnalysisSource
from backend.app.storage.postgres import create_db_engine

router = APIRouter(prefix="/analysis", tags=["analysis"])


@lru_cache
def get_analysis_service() -> AnalysisService:
    return AnalysisService(PostgresAnalysisSource(create_db_engine(get_settings().database_url)))


Service = Annotated[AnalysisService, Depends(get_analysis_service)]


def get_filters(
    service: str | None = None,
    doc_type: Annotated[list[str], Query()] = [],  # noqa: B006 - FastAPI query list default
    severity: Annotated[list[int], Query()] = [],  # noqa: B006
    entity_type: Annotated[list[str], Query()] = [],  # noqa: B006
    relation_type: Annotated[list[str], Query()] = [],  # noqa: B006
    date_from: date | None = None,
    date_to: date | None = None,
    length_min: Annotated[int | None, Query(ge=0)] = None,
    length_max: Annotated[int | None, Query(ge=0)] = None,
    evidence: EvidenceFilter | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> FilterSet:
    return FilterSet(
        service=service,
        doc_types=doc_type,
        severities=severity,
        entity_types=entity_type,
        relation_types=relation_type,
        date_from=date_from,
        date_to=date_to,
        length_min=length_min,
        length_max=length_max,
        evidence=evidence,
        q=q,
    )


Filters = Annotated[FilterSet, Depends(get_filters)]


def get_ref(
    service: Service,
    dataset: Annotated[str | None, Query(description="Dataset version")] = None,
    graph: Annotated[str | None, Query(description="Graph version (default: curated)")] = None,
) -> DatasetRef:
    try:
        return service.resolve(dataset or get_settings().dataset_version, graph)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IncompatibleSnapshot as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


Ref = Annotated[DatasetRef, Depends(get_ref)]


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail=f"record not found: {exc}")


@router.get("/datasets", response_model=list[DatasetInfo])
def datasets(service: Service) -> list[DatasetInfo]:
    return service.datasets()


@router.get("/facets", response_model=Facets)
def facets(service: Service, ref: Ref) -> Facets:
    return service.facets(ref)


@router.get("/overview", response_model=Overview)
def overview(service: Service, ref: Ref, filters: Filters) -> Overview:
    return service.overview(ref, filters)


@router.get("/records", response_model=RecordPage)
def records(
    service: Service,
    ref: Ref,
    filters: Filters,
    record_type: RecordType,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    sort: str | None = None,
    descending: bool | None = None,
) -> RecordPage:
    return service.records(ref, record_type, filters, offset, limit, sort, descending)


@router.get("/records/{record_type}/{record_id}", response_model=RecordDetail)
def record(service: Service, ref: Ref, record_type: RecordType, record_id: str) -> RecordDetail:
    try:
        return service.record(ref, record_type, record_id)
    except NotFound as exc:
        raise _not_found(exc) from exc


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def document(
    service: Service, ref: Ref, document_id: str, index_profile: str | None = None
) -> DocumentDetail:
    try:
        return service.document(ref, document_id, index_profile)
    except NotFound as exc:
        raise _not_found(exc) from exc
    except IncompatibleSnapshot as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/export")
def export(
    service: Service,
    ref: Ref,
    filters: Filters,
    record_type: RecordType,
    format: Literal["csv", "json"] = "csv",
    sort: str | None = None,
    descending: bool | None = None,
) -> Response:
    columns, items, total = service.export(ref, record_type, filters, sort, descending)
    headers = {
        "Content-Disposition": f'attachment; filename="{ref.dataset}-{record_type.value}.{format}"',
        "X-Total-Count": str(total),
        "X-Truncated": str(total > len(items)).lower(),
    }
    if format == "json":
        body = json.dumps(
            {
                "ref": ref.model_dump(),
                "filters": filters.model_dump(mode="json"),
                "total": total,
                "items": items,
            },
            indent=2,
        )
        return Response(body, media_type="application/json", headers=headers)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    for item in items:
        writer.writerow(
            {k: "; ".join(map(str, v)) if isinstance(v, list) else v for k, v in item.items()}
        )
    return Response(buffer.getvalue(), media_type="text/csv", headers=headers)
