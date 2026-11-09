"""Parameterized reads over the business records. Callers never supply SQL or column names."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from sqlalchemy import Connection, Engine, func, or_, select

from backend.app.storage.search import retriever_connection
from backend.app.storage.tables.corpus import (
    Deployment,
    ExternalSystem,
    Incident,
    IncidentDeployment,
    IncidentService,
    Service,
    ServiceDependency,
    Subsystem,
    Team,
)

RecordType = Literal["incident", "deployment", "service", "team"]
AggregateEntity = Literal["incidents", "deployments"]
GroupBy = Literal["severity", "status", "cause_category", "kind", "month", "service", "deployed_by"]

MAX_RECORDS = 25
MAX_REFS = 200
_TABLE_TO_TYPE: dict[str, RecordType] = {
    "incidents": "incident",
    "deployments": "deployment",
    "services": "service",
    "teams": "team",
}


@dataclass(frozen=True)
class RecordFilter:
    record_id: str | None = None
    service_id: str | None = None
    primary_service_only: bool = False
    severity: tuple[int, ...] = ()
    status: str | None = None
    kind: str | None = None
    date_from: date | None = None
    date_to: date | None = None


@dataclass(frozen=True)
class Record:
    ref: str
    title: str
    text: str
    created_at: datetime | None
    refs: tuple[str, ...]


@dataclass(frozen=True)
class AggregateResult:
    rows: list[dict[str, Any]]
    total: int
    refs: list[str]


def _month(column: Any) -> Any:
    return func.to_char(func.timezone("UTC", column), "YYYY-MM")


def _lines(pairs: Sequence[tuple[str, Any]]) -> str:
    return "\n".join(f"{label}: {value}" for label, value in pairs if value not in (None, ""))


def _incident_conditions(f: RecordFilter) -> list[Any]:
    conditions: list[Any] = []
    if f.record_id:
        conditions.append(Incident.id == f.record_id)
    if f.service_id and f.primary_service_only:
        conditions.append(Incident.primary_service_id == f.service_id)
    elif f.service_id:
        affected = select(IncidentService.incident_id).where(
            IncidentService.service_id == f.service_id
        )
        conditions.append(
            or_(Incident.primary_service_id == f.service_id, Incident.id.in_(affected))
        )
    if f.severity:
        conditions.append(Incident.severity.in_(f.severity))
    if f.status:
        conditions.append(Incident.status == f.status)
    if f.date_from:
        conditions.append(Incident.started_at >= f.date_from)
    if f.date_to:
        conditions.append(Incident.started_at < f.date_to)
    return conditions


def _deployment_conditions(f: RecordFilter) -> list[Any]:
    conditions: list[Any] = []
    if f.record_id:
        conditions.append(Deployment.id == f.record_id)
    if f.service_id:
        conditions.append(Deployment.service_id == f.service_id)
    if f.status:
        conditions.append(Deployment.status == f.status)
    if f.kind:
        conditions.append(Deployment.kind == f.kind)
    if f.date_from:
        conditions.append(Deployment.deployed_at >= f.date_from)
    if f.date_to:
        conditions.append(Deployment.deployed_at < f.date_to)
    return conditions


class PostgresBusinessRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def lookup(
        self, record_type: RecordType, filters: RecordFilter, limit: int = MAX_RECORDS
    ) -> list[Record]:
        reader = {
            "incident": self._incidents,
            "deployment": self._deployments,
            "service": self._services,
            "team": self._teams,
        }[record_type]
        with retriever_connection(self.engine) as conn:
            return reader(conn, filters, min(limit, MAX_RECORDS))

    def record(self, ref: str) -> Record | None:
        table, _, record_id = ref.partition("/")
        record_type = _TABLE_TO_TYPE.get(table)
        if record_type is None or not record_id:
            return None
        found = self.lookup(record_type, RecordFilter(record_id=record_id), 1)
        return found[0] if found else None

    def _incidents(self, conn: Connection, f: RecordFilter, limit: int) -> list[Record]:
        query = (
            select(Incident, Service.name.label("primary_service"))
            .join(Service, Service.id == Incident.primary_service_id)
            .where(*_incident_conditions(f))
            .order_by(Incident.started_at.desc(), Incident.id)
            .limit(limit)
        )
        rows = conn.execute(query).all()
        records = []
        for row in rows:
            m = row._mapping
            affected = conn.execute(
                select(IncidentService.service_id, IncidentService.impact_type, Service.name)
                .join(Service, Service.id == IncidentService.service_id)
                .where(IncidentService.incident_id == m["id"])
                .order_by(IncidentService.service_id)
            ).all()
            linked = conn.execute(
                select(IncidentDeployment.deployment_id, IncidentDeployment.association_type)
                .where(IncidentDeployment.incident_id == m["id"])
                .order_by(IncidentDeployment.deployment_id)
            ).all()
            text = _lines(
                [
                    ("Incident", m["id"]),
                    ("Title", m["title"]),
                    ("Severity", f"SEV{m['severity']}"),
                    ("Status", m["status"]),
                    ("Cause category", m["cause_category"]),
                    ("Primary service", m["primary_service"]),
                    ("Started", m["started_at"]),
                    ("Detected", m["detected_at"]),
                    ("Mitigated", m["mitigated_at"]),
                    ("Resolved", m["resolved_at"]),
                    ("Summary", m["summary"]),
                    ("Affected services", ", ".join(f"{a[2]} ({a[1]})" for a in affected)),
                    ("Linked deployments", ", ".join(f"{d[0]} ({d[1]})" for d in linked)),
                ]
            )
            refs = (
                f"incidents/{m['id']}",
                *(f"incident_services/{m['id']}/{a[0]}" for a in affected),
                *(f"incident_deployments/{m['id']}/{d[0]}" for d in linked),
            )
            records.append(
                Record(f"incidents/{m['id']}", f"Incident {m['id']}", text, m["started_at"], refs)
            )
        return records

    def _deployments(self, conn: Connection, f: RecordFilter, limit: int) -> list[Record]:
        query = (
            select(Deployment, Service.name.label("service_name"))
            .join(Service, Service.id == Deployment.service_id)
            .where(*_deployment_conditions(f))
            .order_by(Deployment.deployed_at.desc(), Deployment.id)
            .limit(limit)
        )
        records = []
        for row in conn.execute(query).all():
            m = row._mapping
            text = _lines(
                [
                    ("Deployment", m["id"]),
                    ("Service", m["service_name"]),
                    ("Version", m["version"]),
                    ("Kind", m["kind"]),
                    ("Status", m["status"]),
                    ("Deployed at", m["deployed_at"]),
                    ("Deployed by", m["deployed_by"]),
                    ("Rolls back", m["rolls_back_deployment_id"]),
                    ("Change", m["change_summary"]),
                ]
            )
            ref = f"deployments/{m['id']}"
            records.append(Record(ref, f"Deployment {m['id']}", text, m["deployed_at"], (ref,)))
        return records

    def _services(self, conn: Connection, f: RecordFilter, limit: int) -> list[Record]:
        conditions = []
        if f.record_id:
            conditions.append(Service.id == f.record_id)
        if f.service_id:
            conditions.append(Service.id == f.service_id)
        query = (
            select(Service, Team.name.label("team_name"), Subsystem.name.label("subsystem_name"))
            .join(Team, Team.id == Service.team_id)
            .join(Subsystem, Subsystem.id == Service.subsystem_id)
            .where(*conditions)
            .order_by(Service.id)
            .limit(limit)
        )
        records = []
        for row in conn.execute(query).all():
            m = row._mapping
            target = Service.__table__.alias("target")
            links = conn.execute(
                select(
                    ServiceDependency.id,
                    target.c.name,
                    ExternalSystem.name,
                    ServiceDependency.dependency_type,
                    ServiceDependency.criticality,
                    ServiceDependency.valid_from,
                    ServiceDependency.valid_to,
                )
                .join(target, target.c.id == ServiceDependency.depends_on_service_id, isouter=True)
                .join(
                    ExternalSystem,
                    ExternalSystem.id == ServiceDependency.depends_on_external_id,
                    isouter=True,
                )
                .where(ServiceDependency.service_id == m["id"])
                .order_by(ServiceDependency.id)
            ).all()
            depends = "; ".join(
                f"{d[1] or d[2]} ({d[3]}, {d[4]}, from {d[5] or 'start'} until {d[6] or 'now'})"
                for d in links
            )
            text = _lines(
                [
                    ("Service", m["id"]),
                    ("Name", m["name"]),
                    ("Slug", m["slug"]),
                    ("Team", m["team_name"]),
                    ("Subsystem", m["subsystem_name"]),
                    ("Tier", m["tier"]),
                    ("Runtime", m["runtime"]),
                    ("Description", m["description"]),
                    ("Depends on", depends),
                ]
            )
            ref = f"services/{m['id']}"
            refs = (ref, *(f"service_dependencies/{d[0]}" for d in links))
            records.append(Record(ref, f"Service {m['name']}", text, None, refs))
        return records

    def _teams(self, conn: Connection, f: RecordFilter, limit: int) -> list[Record]:
        conditions = [Team.id == f.record_id] if f.record_id else []
        query = select(Team).where(*conditions).order_by(Team.id).limit(limit)
        records = []
        for row in conn.execute(query).all():
            m = row._mapping
            owned = conn.scalars(
                select(Service.name).where(Service.team_id == m["id"]).order_by(Service.name)
            ).all()
            text = _lines(
                [
                    ("Team", m["id"]),
                    ("Name", m["name"]),
                    ("Lead", m["lead"]),
                    ("Slack", m["slack_channel"]),
                    ("Services", ", ".join(owned)),
                ]
            )
            ref = f"teams/{m['id']}"
            records.append(Record(ref, f"Team {m['name']}", text, None, (ref,)))
        return records

    def aggregate(
        self, entity: AggregateEntity, group_by: Sequence[GroupBy], filters: RecordFilter
    ) -> AggregateResult:
        if entity == "incidents":
            table, service_key, ref_table = Incident, Incident.primary_service_id, "incidents"
            conditions = _incident_conditions(filters)
            groups: dict[str, Any] = {
                "severity": Incident.severity,
                "status": Incident.status,
                "cause_category": Incident.cause_category,
                "month": _month(Incident.started_at),
                "service": Service.name,
            }
        else:
            table, service_key, ref_table = Deployment, Deployment.service_id, "deployments"
            conditions = _deployment_conditions(filters)
            groups = {
                "status": Deployment.status,
                "kind": Deployment.kind,
                "month": _month(Deployment.deployed_at),
                "service": Service.name,
                "deployed_by": Deployment.deployed_by,
            }
        unknown = [g for g in group_by if g not in groups]
        if unknown:
            raise ValueError(f"{entity} cannot be grouped by {', '.join(unknown)}")

        columns = [groups[g].label(g) for g in group_by]
        counted = (
            select(*columns, func.count().label("count"))
            .select_from(table)
            .join(Service, Service.id == service_key)
            .where(*conditions)
        )
        if columns:
            counted = counted.group_by(*columns).order_by(*columns)
        ids = select(table.id).where(*conditions).order_by(table.id).limit(MAX_REFS)
        with retriever_connection(self.engine) as conn:
            rows = [dict(row._mapping) for row in conn.execute(counted)]
            matched = conn.scalars(ids).all()
            total = conn.scalar(select(func.count()).select_from(table).where(*conditions))
        return AggregateResult(rows, total or 0, [f"{ref_table}/{i}" for i in matched])
