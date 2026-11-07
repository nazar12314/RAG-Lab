"""Overview: summary cards, drill-down charts and data observations."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from backend.app.analysis.records import apply_filters
from backend.app.analysis.snapshot import Snapshot
from backend.app.models.analysis import (
    ChartSpec,
    DatasetRef,
    FilterSet,
    Observation,
    Overview,
    RecordType,
    SummaryCard,
)

LENGTH_BIN = 1000
SEVERITY_LABEL = {1: "SEV1", 2: "SEV2", 3: "SEV3", 4: "SEV4"}


def _without(f: FilterSet, *fields: str) -> FilterSet:
    """Cross-filtering: a chart ignores its own dimension so other values stay visible."""
    defaults = {
        name: FilterSet.model_fields[name].get_default(call_default_factory=True) for name in fields
    }
    return f.model_copy(update=defaults)


def _counts(series: pd.Series, name: str) -> list[dict]:
    counts = series.value_counts().rename_axis(name).reset_index(name="count")
    return counts.sort_values(["count", name], ascending=[False, True]).to_dict("records")


def build_overview(
    s: Snapshot, ref: DatasetRef, f: FilterSet, document_matches: set[str] | None
) -> Overview:
    def frame(rt: RecordType, flt: FilterSet) -> tuple[pd.DataFrame, list[str]]:
        df, applied, _ = apply_filters(s, rt, flt, document_matches)
        return df, applied

    docs, _ = frame(RecordType.documents, f)
    incidents, _ = frame(RecordType.incidents, f)
    relations, _ = frame(RecordType.relations, f)
    entities, _ = frame(RecordType.entities, f)
    deployments, _ = frame(RecordType.deployments, f)
    services, _ = frame(RecordType.services, f)

    charts: list[ChartSpec] = []

    df, applied = frame(RecordType.documents, _without(f, "doc_types"))
    charts.append(
        ChartSpec(
            id="doc_types",
            title="Documents by type",
            description="Number of source documents per document type.",
            kind="bar",
            record_type=RecordType.documents,
            x="doc_type",
            y="count",
            click={"doc_type": "doc_types"},
            applied_filters=applied,
            rows=_counts(df["doc_type"], "doc_type"),
        )
    )

    df, applied = frame(RecordType.documents, _without(f, "service"))
    per_service = df.explode("service_ids").dropna(subset=["service_ids"])
    rows = (
        per_service.groupby("service_ids")
        .size()
        .rename("count")
        .reset_index()
        .rename(columns={"service_ids": "service_id"})
    )
    team_of = dict(zip(s.services["id"], s.services["team"], strict=True))
    rows["service"] = rows["service_id"].map(s.names)
    rows["team"] = rows["service_id"].map(team_of)
    charts.append(
        ChartSpec(
            id="docs_by_service",
            title="Documents by service",
            description=(
                "Documents linked to each service through metadata, the incident or deployment "
                "they describe, IDs they mention, or graph edges they support. A document can "
                "count for several services."
            ),
            kind="bar",
            record_type=RecordType.documents,
            x="service",
            y="count",
            color="team",
            click={"service_id": "service"},
            applied_filters=applied,
            rows=rows.sort_values(["count", "service"], ascending=[False, True]).to_dict("records"),
        )
    )

    df, applied = frame(RecordType.documents, _without(f, "length_min", "length_max"))
    bins = (df["length_chars"] // LENGTH_BIN * LENGTH_BIN).astype(int)
    hist = bins.value_counts().sort_index()
    charts.append(
        ChartSpec(
            id="doc_length",
            title="Document length (characters)",
            description=f"Histogram of document length in {LENGTH_BIN}-character bins.",
            kind="histogram",
            record_type=RecordType.documents,
            x="bin_start",
            y="count",
            click={"bin_start": "length_min", "bin_end": "length_max"},
            applied_filters=applied,
            rows=[
                {
                    "bin_start": int(b),
                    "bin_end": int(b) + LENGTH_BIN,
                    "label": f"{b:,}-{b + LENGTH_BIN:,}",
                    "count": int(c),
                }
                for b, c in hist.items()
            ],
        )
    )

    df, applied = frame(RecordType.incidents, _without(f, "severities"))
    sev = df["severity"].value_counts().sort_index()
    charts.append(
        ChartSpec(
            id="incident_severity",
            title="Incidents by severity",
            description="SEV1 is the most severe. SEV1 and SEV2 incidents require a postmortem.",
            kind="bar",
            record_type=RecordType.incidents,
            x="label",
            y="count",
            click={"severity": "severities"},
            applied_filters=applied,
            rows=[
                {"severity": int(k), "label": SEVERITY_LABEL[int(k)], "count": int(v)}
                for k, v in sev.items()
            ],
        )
    )

    df, applied = frame(RecordType.incidents, _without(f, "date_from", "date_to"))
    weeks = df["started_at"].dt.tz_convert(None).dt.to_period("W-SUN").dt.start_time
    timeline = (
        pd.DataFrame({"week": weeks.dt.date, "severity": df["severity"]})
        .groupby(["week", "severity"])
        .size()
        .rename("count")
        .reset_index()
    )
    timeline["severity_label"] = timeline["severity"].map(SEVERITY_LABEL)
    charts.append(
        ChartSpec(
            id="incident_timeline",
            title="Incidents over time",
            description="Incidents per week (by start date), stacked by severity. Drag to select a "
            "time window.",
            kind="timeline",
            record_type=RecordType.incidents,
            x="week",
            y="count",
            color="severity_label",
            click={"week": "date_range"},
            applied_filters=applied,
            rows=[{**r, "week": r["week"].isoformat()} for r in timeline.to_dict("records")],
        )
    )

    df, applied = frame(RecordType.incidents, _without(f, "service", "severities"))
    exploded = df.explode("affected_service_ids")
    heat = (
        exploded.groupby(["affected_service_ids", "severity"])
        .size()
        .rename("count")
        .reset_index()
        .rename(columns={"affected_service_ids": "service_id"})
    )
    heat["service"] = heat["service_id"].map(s.names)
    heat["severity_label"] = heat["severity"].map(SEVERITY_LABEL)
    charts.append(
        ChartSpec(
            id="service_severity",
            title="Affected services by incident severity",
            description="How many incidents of each severity affected each service (primary, "
            "degraded or downstream impact).",
            kind="heatmap",
            record_type=RecordType.incidents,
            x="severity_label",
            y="service",
            color="count",
            click={"service_id": "service", "severity": "severities"},
            applied_filters=applied,
            rows=heat.to_dict("records"),
        )
    )

    df, applied = frame(RecordType.entities, _without(f, "entity_types"))
    charts.append(
        ChartSpec(
            id="entity_types",
            title="Graph entities by type",
            description="Nodes in the selected graph version, by entity type.",
            kind="bar",
            record_type=RecordType.entities,
            x="entity_type",
            y="count",
            click={"entity_type": "entity_types"},
            applied_filters=applied,
            rows=_counts(df["entity_type"], "entity_type"),
        )
    )

    df, applied = frame(RecordType.relations, _without(f, "relation_types"))
    charts.append(
        ChartSpec(
            id="relation_types",
            title="Graph relations by type",
            description="Directed, typed edges in the selected graph version.",
            kind="bar",
            record_type=RecordType.relations,
            x="relation_type",
            y="count",
            click={"relation_type": "relation_types"},
            applied_filters=applied,
            rows=_counts(df["relation_type"], "relation_type"),
        )
    )

    df, applied = frame(RecordType.relations, _without(f, "relation_types", "evidence"))
    coverage = df.groupby(["relation_type", "evidence"]).size().rename("count").reset_index()
    charts.append(
        ChartSpec(
            id="evidence_coverage",
            title="Source evidence per relation type",
            description=(
                "document: at least one supporting document passage; record_only: backed only by a "
                "business record; none: no supporting source."
            ),
            kind="stacked_bar",
            record_type=RecordType.relations,
            x="relation_type",
            y="count",
            color="evidence",
            click={"relation_type": "relation_types", "evidence": "evidence"},
            applied_filters=applied,
            rows=coverage.to_dict("records"),
        )
    )

    with_source = int((relations["evidence"] != "none").sum())
    with_docs = int((relations["evidence"] == "document").sum())
    ready = [p for p in s.index_profiles if p.get("status") == "ready"]
    cards = [
        SummaryCard(
            id="documents",
            label="Documents",
            value=len(docs),
            total=len(s.documents),
            help="Source documents matching the filters.",
        ),
        SummaryCard(
            id="postmortems",
            label="Postmortems",
            value=int((docs["doc_type"] == "postmortem").sum()),
            help="Authoritative incident write-ups (SEV1/SEV2).",
        ),
        SummaryCard(
            id="runbooks",
            label="Runbooks",
            value=int((docs["doc_type"] == "runbook").sum()),
            help="Operational how-to documents.",
        ),
        SummaryCard(
            id="services",
            label="Services",
            value=len(services),
            total=len(s.services),
            help="Production services.",
        ),
        SummaryCard(
            id="deployments",
            label="Deployments",
            value=len(deployments),
            total=len(s.deployments),
            help="Releases, hotfixes, rollbacks, config changes.",
        ),
        SummaryCard(
            id="incidents",
            label="Incidents",
            value=len(incidents),
            total=len(s.incidents),
            help="Incidents matching the filters.",
        ),
        SummaryCard(
            id="entities",
            label="Entities",
            value=len(entities),
            total=len(s.entities),
            help="Graph nodes in the selected graph version.",
        ),
        SummaryCard(
            id="relations",
            label="Relations",
            value=len(relations),
            total=len(s.relations),
            help="Directed graph edges.",
        ),
        SummaryCard(
            id="edges_with_source",
            label="Edges with a source",
            value=_pct(with_source, len(relations)),
            help=f"{with_source} of {len(relations)} edges have at least one supporting "
            "document passage or business record.",
        ),
        SummaryCard(
            id="edges_with_document",
            label="Edges with a document",
            value=_pct(with_docs, len(relations)),
            help=f"{with_docs} of {len(relations)} edges link to a supporting passage.",
        ),
        SummaryCard(
            id="chunks",
            label="Chunks",
            value=sum(p.get("chunk_count") or 0 for p in ready) if ready else "not indexed",
            help="Chunks in ready index profiles. Indexing is a later phase.",
        ),
    ]

    return Overview(
        ref=ref,
        filters=f,
        computed_at=datetime.now().astimezone(),
        cards=cards,
        charts=charts,
        observations=_observations(s, incidents, relations, docs),
    )


def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f}%" if whole else "n/a"


def _observations(
    s: Snapshot, incidents: pd.DataFrame, relations: pd.DataFrame, docs: pd.DataFrame
) -> list[Observation]:
    out: list[Observation] = []
    if len(incidents):
        severe = incidents[incidents["severity"] <= 2]
        missing = severe[~severe["has_postmortem"]]
        with_pm = int(incidents["has_postmortem"].sum())
        out.append(
            Observation(
                level="warning" if len(missing) else "info",
                message=(
                    f"{with_pm} of {len(incidents)} incidents have a postmortem. The other "
                    f"{len(incidents) - with_pm} only have a ticket, so cause and resolution "
                    "evidence for them is thinner."
                    + (
                        f" {len(missing)} severe incident(s) lack a postmortem."
                        if len(missing)
                        else ""
                    )
                ),
                record_type=RecordType.incidents,
                filters=FilterSet(severities=[3, 4]),
            )
        )
        hub = incidents.explode("affected_service_ids")["affected_service_ids"].value_counts()
        if len(hub):
            top, count = hub.index[0], int(hub.iloc[0])
            out.append(
                Observation(
                    level="info",
                    message=(
                        f"{s.label(top)} is affected by {count} of {len(incidents)} incidents. "
                        "Check whether it is a genuine shared dependency or just the place where "
                        "failures surface."
                    ),
                    record_type=RecordType.incidents,
                    filters=FilterSet(service=top),
                )
            )
    if len(relations):
        record_only = relations[relations["evidence"] == "record_only"]
        if len(record_only):
            types = ", ".join(sorted(record_only["relation_type"].unique()))
            out.append(
                Observation(
                    level="info",
                    message=(
                        f"{len(record_only)} edges are backed only by business records, not by "
                        f"any document passage ({types}). Document retrievers cannot find text "
                        "for them."
                    ),
                    record_type=RecordType.relations,
                    filters=FilterSet(evidence="record_only"),
                )
            )
        none = relations[relations["evidence"] == "none"]
        if len(none):
            out.append(
                Observation(
                    level="warning",
                    message=f"{len(none)} edges have no supporting source at all.",
                    record_type=RecordType.relations,
                    filters=FilterSet(evidence="none"),
                )
            )
        refuted = relations[relations["verified_status"] == "refuted"]
        if len(refuted):
            out.append(
                Observation(
                    level="warning",
                    message=(
                        f"{len(refuted)} edges are marked refuted (suspects that were ruled "
                        "out). A traversal that ignores verified_status will follow them."
                    ),
                    record_type=RecordType.relations,
                    filters=FilterSet(relation_types=sorted(refuted["relation_type"].unique())),
                )
            )
    unlinked = docs[docs["service_count"] == 0]
    if len(unlinked):
        out.append(
            Observation(
                level="info",
                message=(
                    f"{len(unlinked)} documents are not linked to any service "
                    f"({', '.join(sorted(unlinked['doc_type'].unique()))}). "
                    "Service filters hide them."
                ),
                record_type=RecordType.documents,
                filters=FilterSet(doc_types=sorted(unlinked["doc_type"].unique())),
            )
        )
    stale = s.dependencies[~s.dependencies["current"]]
    if len(stale):
        out.append(
            Observation(
                level="info",
                message=(
                    f"{len(stale)} dependencies are historical (no longer valid on {s.as_of}). "
                    "Documents written earlier may still describe them as current."
                ),
                record_type=RecordType.dependencies,
                filters=FilterSet(),
            )
        )
    return out
