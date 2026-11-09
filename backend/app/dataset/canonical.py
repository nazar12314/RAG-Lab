"""Typed view over the hand-authored canonical fact model (gold side)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml


def parse_ts(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


@dataclass(frozen=True)
class Team:
    id: str
    name: str
    channel: str
    lead: str


@dataclass(frozen=True)
class Subsystem:
    id: str
    name: str


@dataclass(frozen=True)
class ExternalSystem:
    id: str
    name: str
    kind: str
    aliases: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class Service:
    id: str
    slug: str
    name: str
    subsystem: str
    team: str
    tier: int
    runtime: str
    aliases: tuple[str, ...]
    legacy_aliases: tuple[str, ...]
    description: str

    def surface_forms(self) -> list[str]:
        forms = [self.name, self.slug, *self.aliases]
        return list(dict.fromkeys(forms))


@dataclass(frozen=True)
class Dependency:
    id: str
    service: str
    depends_on: str
    type: str
    criticality: str
    valid_from: date | None
    valid_to: date | None
    change_ref: str | None


@dataclass(frozen=True)
class Deployment:
    id: str
    service: str
    version: str
    kind: str
    at: datetime
    by: str
    status: str
    rolls_back: str | None
    changes: tuple[str, ...]


@dataclass(frozen=True)
class TimelineEntry:
    at: datetime
    text: str


@dataclass(frozen=True)
class AffectedService:
    service: str
    impact: str


@dataclass(frozen=True)
class Incident:
    id: str
    title: str
    severity: int
    primary_service: str
    affected: tuple[AffectedService, ...]
    started_at: datetime
    detected_at: datetime
    mitigated_at: datetime
    resolved_at: datetime | None
    status: str
    cause_category: str
    trigger: str | None
    root_cause_in: str | None
    ruled_out: tuple[str, ...]
    resolved_by: tuple[str, ...]
    follow_up: tuple[str, ...]
    summary: str
    impact: str
    detection: str
    preliminary: str
    root_cause: str
    trigger_text: str | None
    ruled_out_text: str | None
    resolution: str
    action_items: tuple[str, ...]
    timeline: tuple[TimelineEntry, ...]
    record: dict[str, Any] = field(default_factory=dict)

    @property
    def is_severe(self) -> bool:
        return self.severity <= 2


@dataclass(frozen=True)
class AuthoredDocument:
    id: str
    title: str
    doc_type: str
    created_at: datetime
    author: str
    services: tuple[str, ...]
    body: str
    source_path: str


@dataclass
class Canonical:
    dataset_version: str
    company: str
    as_of: date
    period_start: date
    period_end: date
    subsystems: dict[str, Subsystem]
    teams: dict[str, Team]
    externals: dict[str, ExternalSystem]
    services: dict[str, Service]  # keyed by slug
    dependencies: list[Dependency]
    deployments: dict[str, Deployment]
    incidents: dict[str, Incident]
    authored_documents: list[AuthoredDocument]

    def service_by_id(self, service_id: str) -> Service:
        return next(s for s in self.services.values() if s.id == service_id)

    def node_ref(self, ref: str) -> str:
        """Resolve a service slug or external id to its stable entity key."""
        if ref in self.services:
            return self.services[ref].id
        if ref in self.externals:
            return ref
        raise KeyError(f"unknown service or external system: {ref}")

    def node_name(self, ref: str) -> str:
        if ref in self.services:
            return self.services[ref].name
        return self.externals[ref].name


def _resolve_time(base: datetime, value: str) -> datetime:
    """Timeline times are "HH:MM" on the incident start date or "YYYY-MM-DD HH:MM"."""
    if len(value) <= 5:
        hour, minute = (int(p) for p in value.split(":"))
        return base.replace(hour=hour, minute=minute, second=0)
    return datetime.fromisoformat(value.replace(" ", "T") + ":00+00:00")


def _load_incident(raw: dict[str, Any]) -> Incident:
    started = parse_ts(raw["started_at"])
    assert started is not None
    return Incident(
        id=raw["id"],
        title=raw["title"],
        severity=int(raw["severity"]),
        primary_service=raw["primary_service"],
        affected=tuple(AffectedService(a["service"], a["impact"]) for a in raw["affected"]),
        started_at=started,
        detected_at=parse_ts(raw["detected_at"]),  # type: ignore[arg-type]
        mitigated_at=parse_ts(raw["mitigated_at"]),  # type: ignore[arg-type]
        resolved_at=parse_ts(raw.get("resolved_at")),
        status=raw.get("status", "resolved"),
        cause_category=raw["cause_category"],
        trigger=raw.get("trigger"),
        root_cause_in=raw.get("root_cause_in"),
        ruled_out=tuple(raw.get("ruled_out", [])),
        resolved_by=tuple(raw.get("resolved_by", [])),
        follow_up=tuple(raw.get("follow_up", [])),
        summary=raw["summary"],
        impact=raw["impact"],
        detection=raw["detection"],
        preliminary=raw["preliminary"],
        root_cause=raw["root_cause"],
        trigger_text=raw.get("trigger_text"),
        ruled_out_text=raw.get("ruled_out_text"),
        resolution=raw["resolution"],
        action_items=tuple(raw.get("action_items", [])),
        timeline=tuple(
            TimelineEntry(_resolve_time(started, str(t["at"])), t["text"])
            for t in raw.get("timeline", [])
        ),
        record=raw.get("record", {}),
    )


def _split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        raise ValueError("authored document is missing YAML front matter")
    _, meta, body = text.split("---\n", 2)
    return yaml.safe_load(meta), body.lstrip("\n")


def load_canonical(canonical_dir: Path) -> Canonical:
    org = yaml.safe_load((canonical_dir / "organization.yaml").read_text())
    deps = yaml.safe_load((canonical_dir / "dependencies.yaml").read_text())["dependencies"]
    dpls = yaml.safe_load((canonical_dir / "deployments.yaml").read_text())["deployments"]
    incs = yaml.safe_load((canonical_dir / "incidents.yaml").read_text())["incidents"]

    authored = []
    for path in sorted((canonical_dir / "documents").rglob("*.md")):
        meta, body = _split_front_matter(path.read_text())
        authored.append(
            AuthoredDocument(
                id=meta["id"],
                title=meta["title"],
                doc_type=meta["doc_type"],
                created_at=parse_ts(meta["created_at"]),  # type: ignore[arg-type]
                author=meta["author"],
                services=tuple(meta.get("services", [])),
                body=body,
                source_path=str(path.relative_to(canonical_dir)),
            )
        )

    return Canonical(
        dataset_version=org["dataset_version"],
        company=org["company"],
        as_of=date.fromisoformat(org["as_of"]),
        period_start=date.fromisoformat(org["period"]["start"]),
        period_end=date.fromisoformat(org["period"]["end"]),
        subsystems={s["id"]: Subsystem(**s) for s in org["subsystems"]},
        teams={t["id"]: Team(**t) for t in org["teams"]},
        externals={
            e["id"]: ExternalSystem(
                id=e["id"],
                name=e["name"],
                kind=e["kind"],
                aliases=tuple(e.get("aliases", [])),
                description=e["description"],
            )
            for e in org["external_systems"]
        },
        services={
            s["slug"]: Service(
                id=s["id"],
                slug=s["slug"],
                name=s["name"],
                subsystem=s["subsystem"],
                team=s["team"],
                tier=s["tier"],
                runtime=s["runtime"],
                aliases=tuple(s.get("aliases", [])),
                legacy_aliases=tuple(s.get("legacy_aliases", [])),
                description=s["description"],
            )
            for s in org["services"]
        },
        dependencies=[
            Dependency(
                id=d["id"],
                service=d["service"],
                depends_on=d["depends_on"],
                type=d["type"],
                criticality=d["criticality"],
                valid_from=parse_date(d.get("valid_from")),
                valid_to=parse_date(d.get("valid_to")),
                change_ref=d.get("change_ref"),
            )
            for d in deps
        ],
        deployments={
            d["id"]: Deployment(
                id=d["id"],
                service=d["service"],
                version=d["version"],
                kind=d["kind"],
                at=parse_ts(d["at"]),  # type: ignore[arg-type]
                by=d["by"],
                status=d.get("status", "succeeded"),
                rolls_back=d.get("rolls_back"),
                changes=tuple(d.get("changes", [])),
            )
            for d in dpls
        },
        incidents={i["id"]: _load_incident(i) for i in incs},
        authored_documents=authored,
    )
