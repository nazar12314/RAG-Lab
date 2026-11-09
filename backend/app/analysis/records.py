"""Filtering and tabular views of snapshot records."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import pandas as pd

from backend.app.analysis.snapshot import Snapshot
from backend.app.models.analysis import FilterSet, RecordType

# Filters that make sense per record type; anything else is reported back as ignored.
APPLICABLE: dict[RecordType, set[str]] = {
    RecordType.documents: {
        "service",
        "doc_types",
        "date_from",
        "date_to",
        "length_min",
        "length_max",
        "q",
    },
    RecordType.services: {"service", "q"},
    RecordType.dependencies: {"service", "date_from", "date_to", "q"},
    RecordType.deployments: {"service", "date_from", "date_to", "q"},
    RecordType.incidents: {"service", "severities", "date_from", "date_to", "q"},
    RecordType.entities: {"service", "entity_types", "q"},
    RecordType.relations: {
        "service",
        "relation_types",
        "entity_types",
        "date_from",
        "date_to",
        "evidence",
        "q",
    },
}

COLUMNS: dict[RecordType, list[str]] = {
    RecordType.documents: [
        "id",
        "title",
        "doc_type",
        "created_at",
        "author",
        "length_chars",
        "word_count",
        "service_count",
        "evidence_spans",
    ],
    RecordType.services: [
        "id",
        "name",
        "slug",
        "subsystem",
        "team",
        "tier",
        "runtime",
        "incidents",
        "deployments",
        "documents",
        "depends_on",
        "dependents",
    ],
    RecordType.dependencies: [
        "id",
        "service",
        "depends_on",
        "target_kind",
        "dependency_type",
        "criticality",
        "valid_from",
        "valid_to",
        "current",
    ],
    RecordType.deployments: [
        "id",
        "service",
        "version",
        "kind",
        "status",
        "deployed_at",
        "deployed_by",
        "rolls_back_deployment_id",
        "incident_links",
        "change_summary",
    ],
    RecordType.incidents: [
        "id",
        "title",
        "severity",
        "status",
        "primary_service",
        "started_at",
        "resolved_at",
        "duration_min",
        "cause_category",
        "affected_count",
        "deployment_links",
        "has_postmortem",
    ],
    RecordType.entities: [
        "id",
        "entity_type",
        "canonical_name",
        "alias_count",
        "out_degree",
        "in_degree",
        "external_ref",
    ],
    RecordType.relations: [
        "id",
        "source_name",
        "relation_type",
        "target_name",
        "source_key",
        "target_key",
        "verified_status",
        "valid_from",
        "valid_to",
        "doc_evidence",
        "record_evidence",
        "evidence",
    ],
}

DEFAULT_SORT: dict[RecordType, tuple[str, bool]] = {
    RecordType.documents: ("id", False),
    RecordType.services: ("id", False),
    RecordType.dependencies: ("id", False),
    RecordType.deployments: ("deployed_at", False),
    RecordType.incidents: ("started_at", False),
    RecordType.entities: ("id", False),
    RecordType.relations: ("id", False),
}

SEARCH_COLUMNS: dict[RecordType, list[str]] = {
    RecordType.documents: ["id", "title"],
    RecordType.services: ["id", "name", "slug"],
    RecordType.dependencies: ["id", "service", "depends_on"],
    RecordType.deployments: ["id", "service", "version", "change_summary"],
    RecordType.incidents: ["id", "title", "summary"],
    RecordType.entities: ["id", "canonical_name", "aliases_text"],
    RecordType.relations: ["id", "source_name", "target_name", "relation_type"],
}


def base_frame(s: Snapshot, record_type: RecordType) -> pd.DataFrame:
    if record_type is RecordType.services:
        df = s.services.copy()
        involved = s.incident_services.groupby("service_id")["incident_id"].nunique()
        df["incidents"] = df["id"].map(involved).fillna(0).astype(int)
        df["deployments"] = df["id"].map(s.deployments.groupby("service_id").size())
        df["deployments"] = df["deployments"].fillna(0).astype(int)
        doc_counts = s.documents.explode("service_ids").groupby("service_ids").size()
        df["documents"] = df["id"].map(doc_counts).fillna(0).astype(int)
        df["depends_on"] = df["id"].map(s.dependencies.groupby("service_id").size())
        df["dependents"] = df["id"].map(s.dependencies.groupby("depends_on_id").size())
        df[["depends_on", "dependents"]] = df[["depends_on", "dependents"]].fillna(0).astype(int)
        return df
    if record_type is RecordType.entities:
        df = s.entities.rename(columns={"key": "id"})
        df["aliases_text"] = df["id"].map(lambda k: " ".join(s.aliases.get(k, [])))
        return df
    return {
        RecordType.documents: s.documents,
        RecordType.dependencies: s.dependencies,
        RecordType.deployments: s.deployments,
        RecordType.incidents: s.incidents,
        RecordType.relations: s.relations,
    }[record_type].copy()


def _date_mask(values: pd.Series, f: FilterSet) -> pd.Series:
    days = values.dt.date
    mask = pd.Series(True, index=values.index)
    if f.date_from:
        mask &= days >= f.date_from
    if f.date_to:
        mask &= days <= f.date_to
    return mask


def _validity_mask(df: pd.DataFrame, f: FilterSet) -> pd.Series:
    """Validity interval [valid_from, valid_to) overlaps the selected date range."""
    starts = df["valid_from"].map(lambda v: v or date.min)
    ends = df["valid_to"].map(lambda v: v or date.max)
    mask = pd.Series(True, index=df.index)
    if f.date_from:
        mask &= ends > f.date_from
    if f.date_to:
        mask &= starts <= f.date_to
    return mask


def apply_filters(
    s: Snapshot,
    record_type: RecordType,
    f: FilterSet,
    document_matches: set[str] | None = None,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    df = base_frame(s, record_type)
    active = f.active()
    applicable = APPLICABLE[record_type]
    applied = sorted(active & applicable)
    ignored = sorted(active - applicable)
    mask = pd.Series(True, index=df.index)
    use = set(applied)

    if "service" in use:
        svc = f.service
        if record_type is RecordType.documents:
            mask &= df["service_ids"].map(lambda ids: svc in ids)
        elif record_type is RecordType.services:
            mask &= df["id"] == svc
        elif record_type is RecordType.dependencies:
            mask &= (df["service_id"] == svc) | (df["depends_on_id"] == svc)
        elif record_type is RecordType.deployments:
            mask &= df["service_id"] == svc
        elif record_type is RecordType.incidents:
            mask &= df["affected_service_ids"].map(lambda ids: svc in ids) | (
                df["primary_service_id"] == svc
            )
        elif record_type is RecordType.entities:
            rel = s.relations
            neighbours = set(rel.loc[rel["source_key"] == svc, "target_key"]) | set(
                rel.loc[rel["target_key"] == svc, "source_key"]
            )
            mask &= df["id"].isin(neighbours | {svc})
        elif record_type is RecordType.relations:
            mask &= (df["source_key"] == svc) | (df["target_key"] == svc)
    if "doc_types" in use:
        mask &= df["doc_type"].isin(f.doc_types)
    if "severities" in use:
        mask &= df["severity"].isin(f.severities)
    if "entity_types" in use:
        if record_type is RecordType.entities:
            mask &= df["entity_type"].isin(f.entity_types)
        else:
            mask &= df["source_type"].isin(f.entity_types) | df["target_type"].isin(f.entity_types)
    if "relation_types" in use:
        mask &= df["relation_type"].isin(f.relation_types)
    if "evidence" in use:
        mask &= df["evidence"] == f.evidence
    if "length_min" in use:
        mask &= df["length_chars"] >= f.length_min
    if "length_max" in use:
        mask &= df["length_chars"] < f.length_max
    if use & {"date_from", "date_to"}:
        if record_type in (RecordType.dependencies, RecordType.relations):
            mask &= _validity_mask(df, f)
        else:
            column = {
                RecordType.documents: "created_at",
                RecordType.deployments: "deployed_at",
                RecordType.incidents: "started_at",
            }[record_type]
            mask &= _date_mask(df[column], f)
    if "q" in use:
        needle = f.q.strip().lower()  # type: ignore[union-attr]
        hit = pd.Series(False, index=df.index)
        for col in SEARCH_COLUMNS[record_type]:
            hit |= df[col].astype(str).str.lower().str.contains(needle, regex=False)
        if record_type is RecordType.documents and document_matches is not None:
            hit |= df["id"].isin(document_matches)
        mask &= hit
    return df[mask], applied, ignored


def sort_page(
    df: pd.DataFrame,
    record_type: RecordType,
    sort: str | None,
    descending: bool | None,
    offset: int,
    limit: int,
) -> tuple[pd.DataFrame, str, bool]:
    default_col, default_desc = DEFAULT_SORT[record_type]
    column = sort if sort in COLUMNS[record_type] else default_col
    desc = default_desc if descending is None else descending
    ordered = df.sort_values(column, ascending=not desc, na_position="last", kind="stable")
    return ordered.iloc[offset : offset + limit], column, desc


def jsonable(value: Any) -> Any:
    if value is None or value is pd.NaT:
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in value]
    if hasattr(value, "item"):  # numpy scalars
        return value.item()
    return value


def to_items(df: pd.DataFrame, columns: list[str]) -> list[dict[str, Any]]:
    return [
        {c: jsonable(v) for c, v in zip(columns, row, strict=True)}
        for row in df[columns].itertuples(index=False, name=None)
    ]
