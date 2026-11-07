"""In-memory analysis snapshot of one dataset version + graph version.

The corpus is small, so the snapshot is built once from PostgreSQL per (dataset, graph,
load time) and every distribution, filter and detail view is derived from it.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import pandas as pd

ID_PATTERN = re.compile(r"\b(INC-\d{3}|DPL-\d{3})\b")


@dataclass
class Snapshot:
    dataset: dict[str, Any]
    graph: dict[str, Any]
    index_profiles: list[dict[str, Any]]
    built_at: datetime
    services: pd.DataFrame
    dependencies: pd.DataFrame
    deployments: pd.DataFrame
    incidents: pd.DataFrame
    documents: pd.DataFrame
    entities: pd.DataFrame
    relations: pd.DataFrame
    evidence: pd.DataFrame
    incident_services: pd.DataFrame
    incident_deployments: pd.DataFrame
    content: dict[str, str]
    doc_service_reasons: dict[str, dict[str, set[str]]]
    names: dict[str, str]
    teams: dict[str, str]
    subsystems: dict[str, str]
    aliases: dict[str, list[str]] = field(default_factory=dict)

    @property
    def as_of(self) -> date:
        value = self.dataset["as_of"]
        return value if isinstance(value, date) else date.fromisoformat(str(value))

    def label(self, key: str | None) -> str:
        return self.names.get(key, key) if key else ""


def _frame(rows: list[dict[str, Any]], columns: list[str] | None = None) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty and columns:
        df = pd.DataFrame(columns=columns)
    return df


def _ts(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True)


def _date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series).dt.date.where(series.notna(), None)


def build_snapshot(
    dataset: dict[str, Any],
    graph: dict[str, Any],
    index_profiles: list[dict[str, Any]],
    rows: dict[str, list[dict[str, Any]]],
) -> Snapshot:
    teams = {t["id"]: t["name"] for t in rows["teams"]}
    subsystems = {s["id"]: s["name"] for s in rows["subsystems"]}
    names: dict[str, str] = {**teams, **subsystems}
    names.update({e["id"]: e["name"] for e in rows["external_systems"]})
    names.update({s["id"]: s["name"] for s in rows["services"]})
    names.update({f"SUB-{k}": v for k, v in subsystems.items()})

    services = _frame(rows["services"])
    services["team"] = services["team_id"].map(teams)
    services["subsystem"] = services["subsystem_id"].map(subsystems)

    deployments = _frame(rows["deployments"])
    deployments["deployed_at"] = _ts(deployments["deployed_at"])
    deployments["service"] = deployments["service_id"].map(names)
    names.update({d.id: f"{names[d.service_id]} {d.version}" for d in deployments.itertuples()})

    incidents = _frame(rows["incidents"])
    for col in ("started_at", "detected_at", "mitigated_at", "resolved_at"):
        incidents[col] = _ts(incidents[col])
    names.update({i.id: f"{i.id} {i.title}" for i in incidents.itertuples()})

    inc_services = _frame(rows["incident_services"], ["incident_id", "service_id", "impact_type"])
    inc_deps = _frame(
        rows["incident_deployments"],
        ["incident_id", "deployment_id", "association_type", "verified_source_document_id"],
    )
    affected = inc_services.groupby("incident_id")["service_id"].apply(list)
    links_per_incident = inc_deps.groupby("incident_id").size()
    links_per_deployment = inc_deps.groupby("deployment_id").size()

    documents = _frame(rows["documents"])
    documents["created_at"] = _ts(documents["created_at"])
    content = dict(zip(documents["id"], documents["content"], strict=True))
    documents["length_chars"] = documents["content"].str.len()
    documents["word_count"] = documents["content"].str.split().str.len()
    names.update(dict(zip(documents["id"], documents["title"], strict=True)))
    postmortems = {
        (m or {}).get("incident_id")
        for m, t in zip(documents["metadata"], documents["doc_type"], strict=True)
        if t == "postmortem"
    }

    incidents["primary_service"] = incidents["primary_service_id"].map(names)
    incidents["affected_service_ids"] = (
        incidents["id"].map(affected).apply(lambda v: v if isinstance(v, list) else [])
    )
    incidents["affected_count"] = incidents["affected_service_ids"].str.len()
    incidents["deployment_links"] = incidents["id"].map(links_per_incident).fillna(0).astype(int)
    incidents["has_postmortem"] = incidents["id"].isin(postmortems)
    end = incidents["resolved_at"].fillna(incidents["mitigated_at"])
    incidents["duration_min"] = ((end - incidents["started_at"]).dt.total_seconds() // 60).astype(
        int
    )
    deployments["incident_links"] = (
        deployments["id"].map(links_per_deployment).fillna(0).astype(int)
    )

    as_of = dataset["as_of"]
    as_of = as_of if isinstance(as_of, date) else date.fromisoformat(str(as_of))
    deps = _frame(rows["service_dependencies"])
    deps["valid_from"] = _date(deps["valid_from"])
    deps["valid_to"] = _date(deps["valid_to"])
    deps["depends_on_id"] = deps["depends_on_service_id"].fillna(deps["depends_on_external_id"])
    deps["target_kind"] = (
        deps["depends_on_service_id"].notna().map({True: "service", False: "external"})
    )
    deps["service"] = deps["service_id"].map(names)
    deps["depends_on"] = deps["depends_on_id"].map(names)
    deps["current"] = [
        (vf is None or vf <= as_of) and (vt is None or as_of < vt)
        for vf, vt in zip(deps["valid_from"], deps["valid_to"], strict=True)
    ]

    entities = _frame(rows["entities"])
    names.update(
        {
            k: v
            for k, v in zip(entities["key"], entities["canonical_name"], strict=True)
            if k not in names
        }
    )
    aliases: dict[str, list[str]] = defaultdict(list)
    for a in rows["entity_aliases"]:
        aliases[a["entity_key"]].append(a["alias"])
    entity_types = dict(zip(entities["key"], entities["entity_type"], strict=True))

    evidence = _frame(
        rows["relation_evidence"],
        [
            "relation_id",
            "evidence_kind",
            "document_id",
            "span_start",
            "span_end",
            "record_table",
            "record_id",
        ],
    )
    relations = _frame(rows["relations"])
    relations["valid_from"] = _date(relations["valid_from"])
    relations["valid_to"] = _date(relations["valid_to"])
    for side in ("source", "target"):
        relations[f"{side}_name"] = relations[f"{side}_key"].map(names)
        relations[f"{side}_type"] = relations[f"{side}_key"].map(entity_types)
    kinds = evidence.groupby(["relation_id", "evidence_kind"]).size().unstack(fill_value=0)
    relations["doc_evidence"] = (
        relations["id"].map(kinds.get("document", pd.Series(dtype=int))).fillna(0).astype(int)
    )
    relations["record_evidence"] = (
        relations["id"].map(kinds.get("record", pd.Series(dtype=int))).fillna(0).astype(int)
    )
    relations["evidence"] = [
        "document" if d else ("record_only" if r else "none")
        for d, r in zip(relations["doc_evidence"], relations["record_evidence"], strict=True)
    ]

    entities["alias_count"] = entities["key"].map(lambda k: len(aliases.get(k, [])))
    entities["out_degree"] = (
        entities["key"].map(relations.groupby("source_key").size()).fillna(0).astype(int)
    )
    entities["in_degree"] = (
        entities["key"].map(relations.groupby("target_key").size()).fillna(0).astype(int)
    )

    reasons = _document_services(
        set(services["id"]), documents, incidents, deployments, relations, evidence, content
    )
    documents["service_ids"] = documents["id"].map(lambda d: sorted(reasons.get(d, {})))
    documents["service_count"] = documents["service_ids"].str.len()
    documents["evidence_spans"] = (
        documents["id"]
        .map(evidence[evidence["evidence_kind"] == "document"].groupby("document_id").size())
        .fillna(0)
        .astype(int)
    )
    documents = documents.drop(columns=["content"])

    return Snapshot(
        dataset=dataset,
        graph=graph,
        index_profiles=index_profiles,
        built_at=datetime.now().astimezone(),
        services=services,
        dependencies=deps,
        deployments=deployments,
        incidents=incidents,
        documents=documents,
        entities=entities,
        relations=relations,
        evidence=evidence,
        incident_services=inc_services,
        incident_deployments=inc_deps,
        content=content,
        doc_service_reasons=reasons,
        names=names,
        teams=teams,
        subsystems=subsystems,
        aliases=dict(aliases),
    )


def _document_services(
    service_ids: set[str],
    documents: pd.DataFrame,
    incidents: pd.DataFrame,
    deployments: pd.DataFrame,
    relations: pd.DataFrame,
    evidence: pd.DataFrame,
    content: dict[str, str],
) -> dict[str, dict[str, set[str]]]:
    """Which services a document is about, and why (shown to users as provenance)."""
    inc_services = {
        inc.id: {inc.primary_service_id, *inc.affected_service_ids}
        for inc in incidents.itertuples()
    }
    dpl_service = dict(zip(deployments["id"], deployments["service_id"], strict=True))

    reasons: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    def add(doc_id: str, services, reason: str) -> None:
        for s in services:
            if s:
                reasons[doc_id][s].add(reason)

    for doc in documents.itertuples():
        meta = doc.metadata or {}
        add(doc.id, meta.get("services", []), "document metadata")
        if meta.get("incident_id") in inc_services:
            add(doc.id, inc_services[meta["incident_id"]], f"about {meta['incident_id']}")
        add(
            doc.id,
            [dpl_service.get(d) for d in meta.get("deployment_ids", [])],
            "lists the deployment",
        )
        for ref in set(ID_PATTERN.findall(content[doc.id])):
            if ref in inc_services:
                add(doc.id, inc_services[ref], f"mentions {ref}")
            elif ref in dpl_service:
                add(doc.id, [dpl_service[ref]], f"mentions {ref}")

    endpoints = relations.set_index("id")[["source_key", "target_key"]]
    for ev in evidence[evidence["evidence_kind"] == "document"].itertuples():
        src, dst = endpoints.loc[ev.relation_id]
        add(ev.document_id, [k for k in (src, dst) if k in service_ids], "supports a graph edge")
    return {d: dict(s) for d, s in reasons.items()}
