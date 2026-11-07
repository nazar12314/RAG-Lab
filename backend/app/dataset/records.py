"""Projection of the canonical model into the retriever-facing business tables.

The projection is intentionally imperfect, like a real incident tracker: incidents can
carry `record` overrides that misattribute a primary service, leave a suspicion that was
later disproven, or omit a deployment link that only the documents mention.
"""

from __future__ import annotations

from typing import Any

from backend.app.dataset.canonical import Canonical
from backend.app.dataset.facts import F

Row = dict[str, Any]


def iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def build_records(c: Canonical) -> dict[str, list[Row]]:
    teams = [
        {"id": t.id, "name": t.name, "slack_channel": t.channel, "lead": t.lead}
        for t in c.teams.values()
    ]
    subsystems = [{"id": s.id, "name": s.name} for s in c.subsystems.values()]
    externals = [
        {"id": e.id, "name": e.name, "kind": e.kind, "description": e.description}
        for e in c.externals.values()
    ]
    services = [
        {
            "id": s.id,
            "slug": s.slug,
            "name": s.name,
            "subsystem_id": s.subsystem,
            "team_id": s.team,
            "tier": s.tier,
            "runtime": s.runtime,
            "environment": "production",
            "description": s.description,
        }
        for s in c.services.values()
    ]
    dependencies = []
    for d in c.dependencies:
        target_is_service = d.depends_on in c.services
        dependencies.append(
            {
                "id": d.id,
                "service_id": c.services[d.service].id,
                "depends_on_service_id": c.services[d.depends_on].id if target_is_service else None,
                "depends_on_external_id": None if target_is_service else d.depends_on,
                "dependency_type": d.type,
                "criticality": d.criticality,
                "valid_from": iso(d.valid_from),
                "valid_to": iso(d.valid_to),
            }
        )
    deployments = [
        {
            "id": d.id,
            "service_id": c.services[d.service].id,
            "version": d.version,
            "kind": d.kind,
            "deployed_at": iso(d.at),
            "deployed_by": d.by,
            "status": d.status,
            "rolls_back_deployment_id": d.rolls_back,
            "change_summary": "; ".join(d.changes),
        }
        for d in sorted(c.deployments.values(), key=lambda d: d.id)
    ]

    incidents, incident_services, incident_deployments = [], [], []
    for inc in c.incidents.values():
        record = inc.record
        primary = record.get("primary_service", inc.primary_service)
        incidents.append(
            {
                "id": inc.id,
                "title": inc.title,
                "primary_service_id": c.services[primary].id,
                "severity": inc.severity,
                "status": inc.status,
                "cause_category": inc.cause_category,
                "started_at": iso(inc.started_at),
                "detected_at": iso(inc.detected_at),
                "mitigated_at": iso(inc.mitigated_at),
                "resolved_at": iso(inc.resolved_at),
                "summary": inc.summary,
            }
        )
        for a in inc.affected:
            incident_services.append(
                {
                    "incident_id": inc.id,
                    "service_id": c.services[a.service].id,
                    "impact_type": a.impact,
                }
            )
        verified_doc = f"DOC-PM-{inc.id}" if inc.is_severe else f"DOC-TKT-{inc.id}"
        links: list[tuple[str, str]] = []
        if inc.trigger:
            links.append((inc.trigger, "caused"))
        links += [(d, "ruled_out") for d in inc.ruled_out]
        links += [(d, "remediation") for d in inc.resolved_by]
        links += [(d, "follow_up") for d in inc.follow_up]
        omitted = set(record.get("omit_deployment_links", []))
        overrides = record.get("association_overrides", {})
        for dpl_id, association in links:
            if dpl_id in omitted:
                continue
            association = overrides.get(dpl_id, association)
            incident_deployments.append(
                {
                    "incident_id": inc.id,
                    "deployment_id": dpl_id,
                    "association_type": association,
                    "verified_source_document_id": None
                    if association == "suspected"
                    else verified_doc,
                }
            )

    return {
        "subsystems": subsystems,
        "teams": teams,
        "external_systems": externals,
        "services": services,
        "service_dependencies": dependencies,
        "deployments": deployments,
        "incidents": incidents,
        "incident_services": incident_services,
        "incident_deployments": incident_deployments,
    }


def record_fact_sources(c: Canonical, records: dict[str, list[Row]]) -> list[Row]:
    """Which business records support (or contradict) each fact."""
    out: list[Row] = []

    def add(fact_id: str, table: str, record_id: str, stance: str = "supports") -> None:
        out.append(
            {
                "fact_id": fact_id,
                "source_kind": "record",
                "record_table": table,
                "record_id": record_id,
                "stance": stance,
            }
        )

    for s in c.services.values():
        add(F.owner(s.slug), "services", s.id)
    for d in c.dependencies:
        add(F.link(d.id), "service_dependencies", d.id)
    for d in c.deployments.values():
        add(F.deployment(d.id), "deployments", d.id)
    primaries = {r["id"]: r["primary_service_id"] for r in records["incidents"]}
    for inc in c.incidents.values():
        correct = primaries[inc.id] == c.services[inc.primary_service].id
        add(F.overview(inc.id), "incidents", inc.id, "supports" if correct else "contradicts")
        add(F.duration(inc.id), "incidents", inc.id)
        add(F.summary(inc.id), "incidents", inc.id)
        for a in inc.affected:
            add(
                F.affects(inc.id, a.service),
                "incident_services",
                f"{inc.id}/{c.services[a.service].id}",
            )
    for link in records["incident_deployments"]:
        inc_id, dpl_id, assoc = link["incident_id"], link["deployment_id"], link["association_type"]
        inc = c.incidents[inc_id]
        record_id = f"{inc_id}/{dpl_id}"
        if dpl_id == inc.trigger:
            add(
                F.trigger(inc_id),
                "incident_deployments",
                record_id,
                "supports" if assoc == "caused" else "preliminary",
            )
        elif dpl_id in inc.ruled_out:
            add(
                F.ruled_out(inc_id, dpl_id),
                "incident_deployments",
                record_id,
                "supports" if assoc == "ruled_out" else "contradicts",
            )
        elif dpl_id in inc.resolved_by:
            add(F.resolution(inc_id), "incident_deployments", record_id)
    return out
