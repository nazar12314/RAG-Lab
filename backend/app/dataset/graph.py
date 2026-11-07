"""Curated knowledge graph: the upper-bound baseline derived from canonical data.

Never present scores on this graph as evidence that automated extraction works.
"""

from __future__ import annotations

from typing import Any

from backend.app.dataset.canonical import Canonical
from backend.app.dataset.facts import F

Row = dict[str, Any]


def build_curated_graph(
    c: Canonical, fact_doc_spans: dict[str, list[Row]]
) -> tuple[dict[str, list[Row]], list[Row]]:
    """Returns graph tables plus a gold-side relation -> fact mapping."""
    entities: list[Row] = []
    aliases: list[Row] = []
    relations: list[Row] = []
    evidence: list[Row] = []
    relation_facts: list[Row] = []

    def entity(key: str, etype: str, name: str, external_ref: str | None, names: list[str]) -> None:
        entities.append(
            {"key": key, "entity_type": etype, "canonical_name": name, "external_ref": external_ref}
        )
        for alias in dict.fromkeys([name, *names]):
            aliases.append({"entity_key": key, "alias": alias})

    for s in c.subsystems.values():
        entity(f"SUB-{s.id}", "subsystem", s.name, None, [s.id])
    for t in c.teams.values():
        entity(t.id, "team", t.name, f"teams/{t.id}", [t.channel])
    for e in c.externals.values():
        entity(e.id, "external_system", e.name, f"external_systems/{e.id}", list(e.aliases))
    for s in c.services.values():
        entity(s.id, "service", s.name, f"services/{s.id}", s.surface_forms())
    for d in c.deployments.values():
        svc = c.services[d.service]
        bare = d.version.removeprefix("v")
        entity(
            d.id,
            "deployment",
            f"{svc.name} {d.version}",
            f"deployments/{d.id}",
            [f"{svc.slug} {d.version}", f"{svc.slug} {bare}", d.id],
        )
    for i in c.incidents.values():
        entity(i.id, "incident", i.id, f"incidents/{i.id}", [i.title])

    def relation(
        src: str,
        rtype: str,
        dst: str,
        fact_id: str | None,
        *,
        status: str = "verified",
        valid_from=None,
        valid_to=None,
        record: str | None = None,
    ) -> None:
        rel_id = f"REL-{len(relations) + 1:04d}"
        relations.append(
            {
                "id": rel_id,
                "source_key": src,
                "target_key": dst,
                "relation_type": rtype,
                "confidence": 1.0,
                "verified_status": status,
                "valid_from": str(valid_from) if valid_from else None,
                "valid_to": str(valid_to) if valid_to else None,
            }
        )
        if record:
            table, record_id = record.split(":", 1)
            evidence.append(
                {
                    "relation_id": rel_id,
                    "evidence_kind": "record",
                    "record_table": table,
                    "record_id": record_id,
                }
            )
        if fact_id:
            relation_facts.append({"relation_id": rel_id, "fact_id": fact_id})
            for span in fact_doc_spans.get(fact_id, []):
                evidence.append(
                    {
                        "relation_id": rel_id,
                        "evidence_kind": "document",
                        "document_id": span["document_id"],
                        "span_start": span["span_start"],
                        "span_end": span["span_end"],
                    }
                )

    for s in c.services.values():
        relation(s.id, "PART_OF", f"SUB-{s.subsystem}", None, record=f"services:{s.id}")
        relation(s.id, "OWNED_BY", s.team, F.owner(s.slug), record=f"services:{s.id}")
    for d in c.dependencies:
        relation(
            c.node_ref(d.service),
            "DEPENDS_ON",
            c.node_ref(d.depends_on),
            F.link(d.id),
            valid_from=d.valid_from,
            valid_to=d.valid_to,
            record=f"service_dependencies:{d.id}",
        )
    for d in sorted(c.deployments.values(), key=lambda d: d.id):
        relation(
            d.id,
            "DEPLOYED_TO",
            c.services[d.service].id,
            F.deployment(d.id),
            record=f"deployments:{d.id}",
        )
        if d.rolls_back:
            relation(
                d.id, "ROLLS_BACK", d.rolls_back, F.deployment(d.id), record=f"deployments:{d.id}"
            )
    for i in c.incidents.values():
        for a in i.affected:
            svc_id = c.services[a.service].id
            relation(
                svc_id,
                "AFFECTED_BY",
                i.id,
                F.affects(i.id, a.service),
                record=f"incident_services:{i.id}/{svc_id}",
            )
        if i.trigger:
            relation(i.id, "TRIGGERED_BY", i.trigger, F.trigger(i.id))
        if i.root_cause_in:
            relation(i.id, "ROOT_CAUSE_IN", c.node_ref(i.root_cause_in), F.cause(i.id))
        for dpl_id in i.resolved_by:
            relation(i.id, "RESOLVED_BY", dpl_id, F.resolution(i.id))
        # Kept so students can see a traversal that ignores verified_status go wrong.
        for dpl_id in i.ruled_out:
            relation(i.id, "SUSPECTED_TRIGGER", dpl_id, F.ruled_out(i.id, dpl_id), status="refuted")

    tables = {
        "entities": entities,
        "entity_aliases": aliases,
        "relations": relations,
        "relation_evidence": evidence,
    }
    return tables, relation_facts
