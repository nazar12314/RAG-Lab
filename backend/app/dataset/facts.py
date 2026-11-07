"""Stable fact ids and the gold fact catalog derived from the canonical model.

Fact ids are the unit of evaluation: gold labels reference facts, and facts point at
document spans and business records, so labels survive any change of chunking.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.dataset.canonical import Canonical
from backend.app.dataset.text import PLACEHOLDER


class fact_ids:  # noqa: N801 - used as a namespace: F.cause(...)
    @staticmethod
    def owner(slug: str) -> str:
        return f"F-OWNER-{slug}"

    @staticmethod
    def link(link_id: str) -> str:
        return f"F-{link_id}"

    @staticmethod
    def deployment(dpl_id: str) -> str:
        return f"F-{dpl_id}"

    @staticmethod
    def overview(inc_id: str) -> str:
        return f"F-{inc_id}-OVERVIEW"

    @staticmethod
    def duration(inc_id: str) -> str:
        return f"F-{inc_id}-DURATION"

    @staticmethod
    def summary(inc_id: str) -> str:
        return f"F-{inc_id}-SUMMARY"

    @staticmethod
    def impact(inc_id: str) -> str:
        return f"F-{inc_id}-IMPACT"

    @staticmethod
    def affects(inc_id: str, slug: str) -> str:
        return f"F-{inc_id}-AFFECTS-{slug}"

    @staticmethod
    def cause(inc_id: str) -> str:
        return f"F-{inc_id}-CAUSE"

    @staticmethod
    def trigger(inc_id: str) -> str:
        return f"F-{inc_id}-TRIGGER"

    @staticmethod
    def ruled_out(inc_id: str, dpl_id: str) -> str:
        return f"F-{inc_id}-RULEDOUT-{dpl_id}"

    @staticmethod
    def resolution(inc_id: str) -> str:
        return f"F-{inc_id}-RESOLUTION"


F = fact_ids


@dataclass(frozen=True)
class Fact:
    id: str
    kind: str
    subject: str
    predicate: str
    object: str | None
    statement: str
    valid_from: str | None = None
    valid_to: str | None = None


def _dpl_label(c: Canonical, dpl_id: str) -> str:
    d = c.deployments[dpl_id]
    return f"{c.services[d.service].name} {d.version}"


def build_facts(c: Canonical) -> list[Fact]:
    facts: list[Fact] = []
    for svc in c.services.values():
        facts.append(
            Fact(
                F.owner(svc.slug),
                "ownership",
                svc.id,
                "OWNED_BY",
                svc.team,
                f"{svc.name} is owned by the {c.teams[svc.team].name}.",
            )
        )
    for dep in c.dependencies:
        period = ""
        if dep.valid_from:
            period += f" from {dep.valid_from}"
        if dep.valid_to:
            period += f" until {dep.valid_to}"
        facts.append(
            Fact(
                F.link(dep.id),
                "dependency",
                c.node_ref(dep.service),
                "DEPENDS_ON",
                c.node_ref(dep.depends_on),
                f"{c.node_name(dep.service)} depends on {c.node_name(dep.depends_on)} "
                f"({dep.type}, {dep.criticality}){period}.",
                str(dep.valid_from) if dep.valid_from else None,
                str(dep.valid_to) if dep.valid_to else None,
            )
        )
    for dpl in c.deployments.values():
        statement = (
            f"{c.services[dpl.service].name} {dpl.version} ({dpl.kind}) was deployed at "
            f"{dpl.at:%Y-%m-%d %H:%M} UTC by {dpl.by}; status {dpl.status}."
        )
        if dpl.rolls_back:
            statement += f" It rolled back {_dpl_label(c, dpl.rolls_back)}."
        if dpl.changes:
            statement += " Changes: " + "; ".join(dpl.changes) + "."
        facts.append(
            Fact(
                F.deployment(dpl.id),
                "deployment",
                dpl.id,
                "DEPLOYED_TO",
                c.services[dpl.service].id,
                statement,
            )
        )
    for inc in c.incidents.values():
        primary = c.services[inc.primary_service]
        end = inc.resolved_at or inc.mitigated_at
        facts += [
            Fact(
                F.overview(inc.id),
                "incident_overview",
                inc.id,
                "PRIMARY_SERVICE",
                primary.id,
                f"{inc.id} ({inc.title}) was a SEV{inc.severity} incident with {primary.name} as "
                f"primary service; status {inc.status}.",
            ),
            Fact(
                F.duration(inc.id),
                "incident_timing",
                inc.id,
                "TIMING",
                None,
                f"{inc.id} started {inc.started_at:%Y-%m-%d %H:%M} UTC, was mitigated "
                f"{inc.mitigated_at:%Y-%m-%d %H:%M} UTC and "
                + (
                    f"resolved {end:%Y-%m-%d %H:%M} UTC."
                    if inc.resolved_at
                    else "is still being monitored."
                ),
            ),
            Fact(F.summary(inc.id), "incident_summary", inc.id, "SUMMARY", None, inc.summary),
            Fact(F.impact(inc.id), "incident_impact", inc.id, "IMPACT", None, inc.impact),
            Fact(
                F.cause(inc.id),
                "incident_cause",
                inc.id,
                "ROOT_CAUSE",
                c.node_ref(inc.root_cause_in) if inc.root_cause_in else inc.trigger,
                _plain(c, inc.root_cause),
            ),
            Fact(
                F.resolution(inc.id),
                "incident_resolution",
                inc.id,
                "RESOLVED_BY",
                ",".join(inc.resolved_by) or None,
                _plain(c, inc.resolution),
            ),
        ]
        for a in inc.affected:
            facts.append(
                Fact(
                    F.affects(inc.id, a.service),
                    "incident_affects",
                    c.services[a.service].id,
                    "AFFECTED_BY",
                    inc.id,
                    f"{c.services[a.service].name} was affected by {inc.id} ({a.impact}).",
                )
            )
        if inc.trigger:
            facts.append(
                Fact(
                    F.trigger(inc.id),
                    "incident_trigger",
                    inc.id,
                    "TRIGGERED_BY",
                    inc.trigger,
                    f"{inc.id} was triggered by {_dpl_label(c, inc.trigger)} ({inc.trigger}).",
                )
            )
        for dpl_id in inc.ruled_out:
            facts.append(
                Fact(
                    F.ruled_out(inc.id, dpl_id),
                    "incident_ruled_out",
                    inc.id,
                    "RULED_OUT",
                    dpl_id,
                    f"{_dpl_label(c, dpl_id)} ({dpl_id}) was suspected but ruled out as the "
                    f"cause of {inc.id}.",
                )
            )
    return facts


def _plain(c: Canonical, template: str) -> str:
    """Canonical statements use canonical names, not per-document aliases."""

    def repl(match) -> str:
        kind, ref = match.group(1), match.group(2)
        if kind == "svc":
            return c.services[ref].name
        if kind == "dpl":
            return _dpl_label(c, ref)
        return c.externals[ref].name

    return PLACEHOLDER.sub(repl, template)
