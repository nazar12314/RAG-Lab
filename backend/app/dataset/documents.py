"""Generates the retriever-facing document corpus from the canonical model."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from backend.app.dataset.canonical import Canonical, Deployment, Incident
from backend.app.dataset.facts import fact_ids as F
from backend.app.dataset.text import EntityMention, FactMention, Renderer, TextBuilder

SEED = "engineering-ops-v1"
DIGEST_START = date(2026, 4, 1)
DIGEST_DAYS = 14

DIGEST_NOTES = [
    "On-call handovers happened on time for all rotations.",
    "Reminder: the Friday afternoon change freeze applies to all tier 1 services.",
    "The status page template was updated with clearer wording.",
    "Two new engineers joined the payments-primary rotation.",
    "Alert noise review: 14 alerts were tuned or deleted.",
    "Game day planned for the next period; volunteers welcome.",
    "Synthetic checkout probes were extended to the mobile API.",
    "Runbook review: please confirm the owner field on your team's runbooks.",
]


@dataclass
class GeneratedDocument:
    id: str
    title: str
    doc_type: str
    created_at: datetime
    author: str
    source_uri: str
    content: str
    metadata: dict
    facts: list[FactMention] = field(default_factory=list)
    entities: list[EntityMention] = field(default_factory=list)


def fmt_day(value: datetime | date) -> str:
    return f"{value.day} {value.strftime('%B %Y')}"


def fmt_ts(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC")


def fmt_duration(start: datetime, end: datetime) -> str:
    minutes = int((end - start).total_seconds() // 60)
    hours, minutes = divmod(minutes, 60)
    if hours >= 24:
        days, hours = divmod(hours, 24)
        return f"{days} d {hours} h {minutes} min"
    return f"{hours} h {minutes} min" if hours else f"{minutes} min"


class DocumentFactory:
    def __init__(self, canonical: Canonical) -> None:
        self.c = canonical

    def builder(self, doc_id: str) -> TextBuilder:
        return TextBuilder(Renderer(self.c, f"{SEED}:{doc_id}"))

    def finish(self, tb: TextBuilder, **kwargs) -> GeneratedDocument:
        return GeneratedDocument(content=tb.text, facts=tb.facts, entities=tb.entities, **kwargs)

    def ticket_id(self, inc: Incident) -> str:
        return f"DOC-TKT-{inc.id}"

    def postmortem_id(self, inc: Incident) -> str:
        return f"DOC-PM-{inc.id}"

    def all_documents(self) -> list[GeneratedDocument]:
        docs = [self.authored(d) for d in self.c.authored_documents]
        for inc in self.c.incidents.values():
            docs.append(self.ticket(inc))
            if inc.is_severe:
                docs.append(self.postmortem(inc))
        docs.extend(self.release_notes())
        docs.extend(self.digests())
        return sorted(docs, key=lambda d: d.id)

    def authored(self, doc) -> GeneratedDocument:
        tb = self.builder(doc.id)
        tb.authored(doc.body)
        return self.finish(
            tb,
            id=doc.id,
            title=doc.title,
            doc_type=doc.doc_type,
            created_at=doc.created_at,
            author=doc.author,
            source_uri=f"kestrel://wiki/{doc.source_path.removesuffix('.md').lower()}",
            metadata={"services": [self.c.services[s].id for s in doc.services]},
        )

    def _affected_line(self, tb: TextBuilder, inc: Incident) -> None:
        tb.add("Affected services: ")
        for i, a in enumerate(inc.affected):
            if i:
                tb.add(", ")
            tb.add(f"{{svc:{a.service}}} ({a.impact})", facts=(F.affects(inc.id, a.service),))
        tb.raw("\n")

    def ticket(self, inc: Incident) -> GeneratedDocument:
        doc_id = self.ticket_id(inc)
        tb = self.builder(doc_id)
        tb.line(f"# {inc.id}: {inc.title}")
        tb.line()
        tb.line(
            f"Severity: SEV{inc.severity} | Status: {inc.status.capitalize()} | "
            f"Primary service: {{svc:{inc.primary_service}}}",
            facts=(F.overview(inc.id),),
        )
        tb.line(
            f"Opened: {fmt_ts(inc.detected_at)} (impact started {inc.started_at:%H:%M} UTC)",
            facts=(F.duration(inc.id),),
        )
        self._affected_line(tb, inc)
        tb.line()
        tb.line("## Description")
        tb.line(inc.summary, facts=(F.summary(inc.id),))
        tb.line()
        tb.line("## Impact")
        tb.line(inc.impact, facts=(F.impact(inc.id),))
        tb.line()
        tb.line("## Detection")
        tb.line(inc.detection)
        tb.line()
        tb.line("## Initial notes from the incident channel")
        tb.line(inc.preliminary, facts=(F.cause(inc.id),), stance="preliminary")
        tb.line()
        tb.line("## Resolution note")
        if inc.is_severe:
            tb.line(inc.resolution, facts=(F.resolution(inc.id),))
            tb.line(f"Full analysis in the postmortem {self.postmortem_id(inc)}.")
        else:
            cause_facts = [F.cause(inc.id)]
            if inc.trigger:
                cause_facts.append(F.trigger(inc.id))
            tb.line(f"Cause: {inc.root_cause}", facts=cause_facts)
            tb.line(inc.resolution, facts=(F.resolution(inc.id),))
            if inc.ruled_out_text:
                tb.line(inc.ruled_out_text, facts=[F.ruled_out(inc.id, d) for d in inc.ruled_out])
        if inc.resolved_at:
            tb.line(f"Resolved: {fmt_ts(inc.resolved_at)}", facts=(F.duration(inc.id),))
        else:
            tb.line(f"Mitigated: {fmt_ts(inc.mitigated_at)}; still being monitored.")
        return self.finish(
            tb,
            id=doc_id,
            title=f"{inc.id}: {inc.title}",
            doc_type="incident_ticket",
            created_at=inc.detected_at,
            author=self.c.teams[self.c.services[inc.primary_service].team].lead,
            source_uri=f"kestrel://incidents/{inc.id}",
            metadata={"incident_id": inc.id, "severity": inc.severity},
        )

    def postmortem(self, inc: Incident) -> GeneratedDocument:
        doc_id = self.postmortem_id(inc)
        tb = self.builder(doc_id)
        team = self.c.teams[self.c.services[inc.primary_service].team]
        end = inc.resolved_at or inc.mitigated_at
        tb.line(f"# Postmortem: {inc.id} - {inc.title}")
        tb.line()
        tb.line(f"Date: {fmt_day(inc.started_at)} | Authors: {team.name} | Status: Final")
        tb.line()
        tb.line("## Summary")
        tb.line(inc.summary, facts=(F.summary(inc.id),))
        tb.add(
            f"{inc.id} was a SEV{inc.severity} incident with {{svc:{inc.primary_service}|name}} "
            "as the primary service. ",
            facts=(F.overview(inc.id),),
        )
        tb.line(
            f"Impact started at {inc.started_at:%H:%M} UTC on {fmt_day(inc.started_at)}, was "
            f"mitigated at {inc.mitigated_at:%H:%M} UTC and the incident was resolved at "
            f"{end:%H:%M} UTC on {fmt_day(end)} (total {fmt_duration(inc.started_at, end)}).",
            facts=(F.duration(inc.id),),
        )
        tb.line()
        tb.line("## Customer impact")
        tb.line(inc.impact, facts=(F.impact(inc.id),))
        self._affected_line(tb, inc)
        tb.line()
        tb.line("## Timeline (UTC)")
        for entry in inc.timeline:
            day = "" if entry.at.date() == inc.started_at.date() else f"{entry.at:%m-%d} "
            tb.line(f"- {day}{entry.at:%H:%M} - {entry.text}")
        tb.line()
        tb.line("## Root cause")
        cause_facts = [F.cause(inc.id)]
        if inc.trigger:
            cause_facts.append(F.trigger(inc.id))
        tb.line(inc.root_cause, facts=cause_facts)
        if inc.trigger_text:
            tb.line(inc.trigger_text, facts=(F.trigger(inc.id),))
        elif inc.trigger:
            tb.line(f"Trigger: {{dpl:{inc.trigger}}}.", facts=(F.trigger(inc.id),))
        else:
            tb.line("No deployment triggered this incident.")
        if inc.ruled_out_text:
            tb.line()
            tb.line("## Ruled out")
            tb.line(inc.ruled_out_text, facts=[F.ruled_out(inc.id, d) for d in inc.ruled_out])
        tb.line()
        tb.line("## Resolution")
        tb.line(inc.resolution, facts=(F.resolution(inc.id),))
        if inc.action_items:
            tb.line()
            tb.line("## Action items")
            for item in inc.action_items:
                tb.line(f"- [ ] {item}")
        return self.finish(
            tb,
            id=doc_id,
            title=f"Postmortem: {inc.id} - {inc.title}",
            doc_type="postmortem",
            created_at=end + timedelta(days=3),
            author=team.lead,
            source_uri=f"kestrel://postmortems/{inc.id}",
            metadata={"incident_id": inc.id, "severity": inc.severity},
        )

    def _release_entry(self, tb: TextBuilder, dpl: Deployment) -> None:
        heading = {
            "rollback": f"### Rollback: {{svc:{dpl.service}}} to {dpl.version}",
            "config_change": f"### Config: {{svc:{dpl.service}}} {dpl.version}",
            "infra_upgrade": f"### Platform upgrade: {{svc:{dpl.service}}} {dpl.version}",
        }.get(dpl.kind, f"### {{svc:{dpl.service}}} {dpl.version} ({dpl.kind})")
        lines = [heading, f"Deployed {fmt_ts(dpl.at)} by {dpl.by}."]
        lines += [f"- {change}" for change in dpl.changes]
        if dpl.status == "rolled_back":
            undo = next(d for d in self.c.deployments.values() if d.rolls_back == dpl.id)
            lines.append(f"Status: rolled back on {fmt_day(undo.at)} (to {undo.version}).")
        tb.line("\n".join(lines), facts=(F.deployment(dpl.id),))
        tb.line()

    def release_notes(self) -> list[GeneratedDocument]:
        groups: dict[tuple[str, str], list[Deployment]] = defaultdict(list)
        for dpl in self.c.deployments.values():
            subsystem = self.c.services[dpl.service].subsystem
            groups[(subsystem, dpl.at.strftime("%Y-%m"))].append(dpl)
        docs = []
        for (subsystem, month), dpls in sorted(groups.items()):
            name = self.c.subsystems[subsystem].name
            month_label = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
            doc_id = f"DOC-RN-{subsystem.upper()}-{month}"
            tb = self.builder(doc_id)
            tb.line(f"# {name} release notes - {month_label}")
            tb.line()
            tb.line(f"Production changes shipped by {name} services in {month_label}.")
            tb.line()
            for dpl in sorted(dpls, key=lambda d: d.at):
                self._release_entry(tb, dpl)
            last = max(d.at for d in dpls)
            docs.append(
                self.finish(
                    tb,
                    id=doc_id,
                    title=f"{name} release notes - {month_label}",
                    doc_type="release_notes",
                    created_at=last + timedelta(hours=2),
                    author=self.c.teams[self.c.services[dpls[0].service].team].lead,
                    source_uri=f"kestrel://releases/{subsystem}/{month}",
                    metadata={
                        "subsystem": subsystem,
                        "month": month,
                        "deployment_ids": [d.id for d in dpls],
                    },
                )
            )
        return docs

    def digests(self) -> list[GeneratedDocument]:
        docs = []
        start = DIGEST_START
        index = 0
        while start <= self.c.period_end:
            end = min(start + timedelta(days=DIGEST_DAYS - 1), self.c.period_end)
            docs.append(self.digest(start, end, index))
            start += timedelta(days=DIGEST_DAYS)
            index += 1
        return docs

    def digest(self, start: date, end: date, index: int) -> GeneratedDocument:
        doc_id = f"DOC-DIGEST-{start.isoformat()}"
        tb = self.builder(doc_id)
        label = f"{fmt_day(start)} to {fmt_day(end)}"
        tb.line(f"# Ops review - {label}")
        tb.line()
        tb.line("Prepared by Platform SRE for the fortnightly operations review.")
        tb.line()
        tb.line("## Incidents")
        incidents = [i for i in self.c.incidents.values() if start <= i.started_at.date() <= end]
        if not incidents:
            tb.line("No incidents this period.")
        for inc in sorted(incidents, key=lambda i: i.started_at):
            tb.add(
                f"- **{inc.id}** (SEV{inc.severity}, {{svc:{inc.primary_service}}}) - ",
                facts=(F.overview(inc.id),),
            )
            tb.line(inc.summary, facts=(F.summary(inc.id),))
            if inc.is_severe:
                tb.add("  Postmortem pending. Working theory: ")
                tb.line(inc.preliminary, facts=(F.cause(inc.id),), stance="preliminary")
            else:
                facts = [F.cause(inc.id)] + ([F.trigger(inc.id)] if inc.trigger else [])
                tb.line(f"  Cause: {inc.root_cause}", facts=facts)
        tb.line()
        tb.line("## Deployments")
        dpls = [d for d in self.c.deployments.values() if start <= d.at.date() <= end]
        rollbacks = [d for d in dpls if d.kind == "rollback"]
        tb.line(
            f"{len(dpls)} production deployments this period, including {len(rollbacks)} "
            f"rollback{'s' if len(rollbacks) != 1 else ''}."
        )
        for dpl in rollbacks:
            target = self.c.deployments[dpl.rolls_back]  # type: ignore[index]
            tb.line(
                f"- {{svc:{dpl.service}}} {target.version} was rolled back to {dpl.version} "
                f"on {fmt_day(dpl.at)}.",
                facts=(F.deployment(dpl.id),),
            )
        tb.line()
        tb.line("## Notes")
        tb.line(f"- {DIGEST_NOTES[index % len(DIGEST_NOTES)]}")
        tb.line(f"- {DIGEST_NOTES[(index * 3 + 1) % len(DIGEST_NOTES)]}")
        return self.finish(
            tb,
            id=doc_id,
            title=f"Ops review - {label}",
            doc_type="ops_review",
            created_at=datetime.fromisoformat(f"{end.isoformat()}T17:00:00+00:00"),
            author="Hannah Becker",
            source_uri=f"kestrel://ops-reviews/{start.isoformat()}",
            metadata={"window_start": start.isoformat(), "window_end": end.isoformat()},
        )
