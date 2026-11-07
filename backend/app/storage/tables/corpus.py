"""Retriever-facing business records and source documents (schema `corpus`)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.storage.postgres import Base

SCHEMA = "corpus"


class DatasetVersion(Base):
    """The corpus snapshot currently loaded. V1 holds one dataset version per database."""

    __tablename__ = "dataset_versions"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    company: Mapped[str] = mapped_column(Text)
    as_of: Mapped[date] = mapped_column(Date)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    corpus_hash: Mapped[str] = mapped_column(Text)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Subsystem(Base):
    __tablename__ = "subsystems"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    slack_channel: Mapped[str] = mapped_column(Text)
    lead: Mapped[str] = mapped_column(Text)


class ExternalSystem(Base):
    __tablename__ = "external_systems"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    kind: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("tier BETWEEN 1 AND 3", name="tier_range"),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    subsystem_id: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.subsystems.id"))
    team_id: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.teams.id"), index=True)
    tier: Mapped[int] = mapped_column(SmallInteger)
    runtime: Mapped[str] = mapped_column(Text)
    environment: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)


class ServiceDependency(Base):
    """`service_id` DEPENDS_ON the target; valid_to is exclusive, NULL bounds are open-ended."""

    __tablename__ = "service_dependencies"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(depends_on_service_id, depends_on_external_id) = 1",
            name="exactly_one_target",
        ),
        CheckConstraint(
            "valid_from IS NULL OR valid_to IS NULL OR valid_from < valid_to",
            name="valid_interval",
        ),
        CheckConstraint(
            "dependency_type IN ('sync_http', 'async_queue', 'database', 'cache', 'webhook', "
            "'external_api')",
            name="dependency_type_values",
        ),
        CheckConstraint("criticality IN ('hard', 'soft')", name="criticality_values"),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    service_id: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.services.id"), index=True)
    depends_on_service_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.services.id"), index=True
    )
    depends_on_external_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.external_systems.id")
    )
    dependency_type: Mapped[str] = mapped_column(Text)
    criticality: Mapped[str] = mapped_column(Text)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)


class Deployment(Base):
    __tablename__ = "deployments"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('release', 'hotfix', 'rollback', 'config_change', 'infra_upgrade')",
            name="kind_values",
        ),
        CheckConstraint("status IN ('succeeded', 'rolled_back')", name="status_values"),
        CheckConstraint(
            "(kind = 'rollback') = (rolls_back_deployment_id IS NOT NULL)",
            name="rollback_has_target",
        ),
        Index("ix_deployments_service_time", "service_id", "deployed_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    service_id: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.services.id"))
    version: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deployed_by: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    rolls_back_deployment_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.deployments.id")
    )
    change_summary: Mapped[str] = mapped_column(Text)


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint("severity BETWEEN 1 AND 4", name="severity_range"),
        CheckConstraint("status IN ('resolved', 'monitoring')", name="status_values"),
        CheckConstraint(
            "started_at <= detected_at AND detected_at <= mitigated_at "
            "AND (resolved_at IS NULL OR mitigated_at <= resolved_at)",
            name="timeline_order",
        ),
        Index("ix_incidents_started_at", "started_at"),
        Index("ix_incidents_severity", "severity"),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    primary_service_id: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.services.id"), index=True)
    severity: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(Text)
    cause_category: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mitigated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[str] = mapped_column(Text)


class IncidentService(Base):
    __tablename__ = "incident_services"
    __table_args__ = (
        CheckConstraint(
            "impact_type IN ('primary', 'degraded', 'downstream')", name="impact_type_values"
        ),
        {"schema": SCHEMA},
    )

    incident_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.incidents.id", ondelete="CASCADE"), primary_key=True
    )
    service_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.services.id"), primary_key=True, index=True
    )
    impact_type: Mapped[str] = mapped_column(Text)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_type_created", "doc_type", "created_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    doc_type: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    author: Mapped[str] = mapped_column(Text)
    source_uri: Mapped[str] = mapped_column(Text, unique=True)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class IncidentDeployment(Base):
    """How the incident tracker links deployments to incidents; may disagree with postmortems."""

    __tablename__ = "incident_deployments"
    __table_args__ = (
        CheckConstraint(
            "association_type IN ('caused', 'suspected', 'ruled_out', 'remediation', 'follow_up')",
            name="association_type_values",
        ),
        {"schema": SCHEMA},
    )

    incident_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.incidents.id", ondelete="CASCADE"), primary_key=True
    )
    deployment_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.deployments.id"), primary_key=True, index=True
    )
    association_type: Mapped[str] = mapped_column(Text)
    verified_source_document_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.documents.id")
    )
