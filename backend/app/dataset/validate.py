"""Consistency checks for the canonical model and the generated artifacts."""

from __future__ import annotations

from collections import Counter

from backend.app.dataset.canonical import Canonical


class DatasetError(ValueError):
    pass


def validate_canonical(c: Canonical) -> list[str]:
    errors: list[str] = []
    nodes = set(c.services) | set(c.externals)

    for s in c.services.values():
        if s.team not in c.teams:
            errors.append(f"{s.id}: unknown team {s.team}")
        if s.subsystem not in c.subsystems:
            errors.append(f"{s.id}: unknown subsystem {s.subsystem}")

    for d in c.dependencies:
        if d.service not in c.services or d.depends_on not in nodes:
            errors.append(f"{d.id}: unknown endpoint")
        if d.valid_from and d.valid_to and d.valid_from >= d.valid_to:
            errors.append(f"{d.id}: empty validity interval")

    ordered = sorted(c.deployments.values(), key=lambda d: d.id)
    for prev, cur in zip(ordered, ordered[1:], strict=False):
        if cur.at < prev.at:
            errors.append(f"{cur.id}: deployment ids are not chronological")
    for d in ordered:
        if d.service not in c.services:
            errors.append(f"{d.id}: unknown service {d.service}")
        if d.kind == "rollback":
            target = c.deployments.get(d.rolls_back or "")
            if target is None or target.service != d.service or target.at >= d.at:
                errors.append(f"{d.id}: invalid rollback target {d.rolls_back}")
            elif target.kind != "config_change":
                earlier = {
                    x.version
                    for x in ordered
                    if x.service == d.service and x.at < target.at and x.status == "succeeded"
                }
                if d.version not in earlier:
                    errors.append(f"{d.id}: rollback version {d.version} never deployed before")
    rollbacks = Counter(d.rolls_back for d in ordered if d.rolls_back)
    for d in ordered:
        if d.status == "rolled_back" and rollbacks[d.id] != 1:
            errors.append(f"{d.id}: rolled_back status needs exactly one rollback")

    inc_ids = sorted(c.incidents)
    for prev, cur in zip(inc_ids, inc_ids[1:], strict=False):
        if c.incidents[cur].detected_at < c.incidents[prev].detected_at:
            errors.append(f"{cur}: incident ids are not ordered by detection time")
    for inc in c.incidents.values():
        times = [inc.started_at, inc.detected_at, inc.mitigated_at]
        if inc.resolved_at:
            times.append(inc.resolved_at)
        if times != sorted(times):
            errors.append(f"{inc.id}: timestamps out of order")
        if (inc.resolved_at is None) != (inc.status != "resolved"):
            errors.append(f"{inc.id}: status/resolved_at mismatch")
        affected = [a.service for a in inc.affected]
        if inc.primary_service not in affected or any(s not in c.services for s in affected):
            errors.append(f"{inc.id}: primary/affected services invalid")
        for dpl_id in (inc.trigger, *inc.ruled_out):
            if dpl_id and (
                dpl_id not in c.deployments or c.deployments[dpl_id].at > inc.started_at
            ):
                errors.append(f"{inc.id}: {dpl_id} missing or deployed after the incident start")
        for dpl_id in (*inc.resolved_by, *inc.follow_up):
            if dpl_id not in c.deployments or c.deployments[dpl_id].at < inc.started_at:
                errors.append(f"{inc.id}: remediation {dpl_id} missing or before the incident")
        if inc.root_cause_in and inc.root_cause_in not in nodes:
            errors.append(f"{inc.id}: unknown root_cause_in {inc.root_cause_in}")
        if inc.record.get("primary_service", inc.primary_service) not in c.services:
            errors.append(f"{inc.id}: record override names an unknown service")
    return errors


def validate_artifacts(
    fact_ids: set[str], documents, fact_sources, relations, evidence
) -> list[str]:
    errors: list[str] = []
    for doc in documents:
        for m in doc.facts:
            if m.fact_id not in fact_ids:
                errors.append(f"{doc.id}: unknown fact {m.fact_id}")
            if not doc.content[m.start : m.end].strip():
                errors.append(f"{doc.id}: empty span for {m.fact_id}")
    supported = {s["fact_id"] for s in fact_sources if s["stance"] == "supports"}
    for missing in sorted(fact_ids - supported):
        errors.append(f"{missing}: no supporting source")
    with_evidence = {e["relation_id"] for e in evidence}
    for rel in relations:
        if rel["id"] not in with_evidence:
            errors.append(f"{rel['id']} ({rel['relation_type']}): no evidence")
    return errors
