"""Record detail panels and document inspection, with links between records and sources."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

import pandas as pd

from backend.app.analysis.records import jsonable
from backend.app.analysis.snapshot import ID_PATTERN, Snapshot
from backend.app.models.analysis import (
    ChunkSpan,
    DatasetRef,
    DocumentDetail,
    EvidenceSnippet,
    Highlight,
    LinkGroup,
    RecordDetail,
    RecordLink,
    RecordSource,
    RecordType,
)

DOC_ID_PATTERN = re.compile(r"\bDOC-[A-Z0-9-]*[A-Z0-9]\b")
SNIPPET_LIMIT = 600
# Incident edges whose supporting passages explain the incident (not just "affected").
EXPLAINING_EDGES = ("TRIGGERED_BY", "RESOLVED_BY", "ROOT_CAUSE_IN", "SUSPECTED_TRIGGER")


class NotFound(LookupError):
    pass


def record_type_of(key: str) -> RecordType:
    if key.startswith("SVC-"):
        return RecordType.services
    if key.startswith("INC-"):
        return RecordType.incidents
    if key.startswith("DPL-"):
        return RecordType.deployments
    if key.startswith("DOC-"):
        return RecordType.documents
    if key.startswith("LINK-"):
        return RecordType.dependencies
    if key.startswith("REL-"):
        return RecordType.relations
    return RecordType.entities


def link(s: Snapshot, key: str, note: str | None = None) -> RecordLink:
    return RecordLink(record_type=record_type_of(key), id=key, label=s.label(key), note=note)


def relation_label(row: Any) -> str:
    return f"{row.source_name} --{row.relation_type}--> {row.target_name}"


def relation_link(row: Any) -> RecordLink:
    return RecordLink(
        record_type=RecordType.relations,
        id=row.id,
        label=relation_label(row),
        note=None if row.verified_status == "verified" else row.verified_status,
    )


def _one(df: pd.DataFrame, record_id: str, column: str = "id") -> Any:
    match = df[df[column] == record_id]
    if match.empty:
        raise NotFound(record_id)
    return next(match.itertuples())


def _snippets(s: Snapshot, relation_ids: Iterable[str]) -> list[EvidenceSnippet]:
    ids = list(relation_ids)
    ev = s.evidence[
        (s.evidence["evidence_kind"] == "document") & s.evidence["relation_id"].isin(ids)
    ]
    rel = s.relations.set_index("id")
    out = []
    for e in ev.sort_values(["document_id", "span_start"]).itertuples():
        start, end = int(e.span_start), int(e.span_end)
        text = s.content[e.document_id][start:end].strip()
        out.append(
            EvidenceSnippet(
                document_id=e.document_id,
                document_title=s.label(e.document_id),
                span_start=start,
                span_end=end,
                text=text if len(text) <= SNIPPET_LIMIT else text[:SNIPPET_LIMIT] + "...",
                relation_key=e.relation_id,
                relation_type=rel.loc[e.relation_id, "relation_type"],
            )
        )
    return out


def _record_sources(s: Snapshot, relation_ids: Iterable[str]) -> list[RecordSource]:
    ev = s.evidence[
        (s.evidence["evidence_kind"] == "record")
        & s.evidence["relation_id"].isin(list(relation_ids))
    ]
    pairs = sorted({(e.record_table, e.record_id) for e in ev.itertuples()})
    return [RecordSource(record_table=t, record_id=i) for t, i in pairs]


def _touching(s: Snapshot, key: str, types: Iterable[str] | None = None) -> pd.DataFrame:
    rel = s.relations
    df = rel[(rel["source_key"] == key) | (rel["target_key"] == key)]
    return df[df["relation_type"].isin(list(types))] if types else df


def _documents_about(s: Snapshot, key: str) -> list[RecordLink]:
    """Documents whose metadata or text refer to the record, with the reason as note."""
    links = []
    for doc in s.documents.itertuples():
        meta = doc.metadata or {}
        if meta.get("incident_id") == key or key in meta.get("deployment_ids", []):
            links.append(link(s, doc.id, f"{doc.doc_type}, about {key}"))
        elif re.search(rf"\b{re.escape(key)}\b", s.content[doc.id]):
            links.append(link(s, doc.id, f"{doc.doc_type}, mentions {key}"))
    return links


def _attrs(row: Any, columns: Iterable[str]) -> dict[str, Any]:
    return {c: jsonable(getattr(row, c)) for c in columns}


def record_detail(s: Snapshot, ref: DatasetRef, rt: RecordType, record_id: str) -> RecordDetail:
    builder = {
        RecordType.incidents: _incident,
        RecordType.services: _service,
        RecordType.deployments: _deployment,
        RecordType.dependencies: _dependency,
        RecordType.documents: _document_record,
        RecordType.entities: _entity,
        RecordType.relations: _relation,
    }[rt]
    return builder(s, ref, record_id)


def _incident(s: Snapshot, ref: DatasetRef, record_id: str) -> RecordDetail:
    row = _one(s.incidents, record_id)
    impacts = s.incident_services[s.incident_services["incident_id"] == record_id]
    links = s.incident_deployments[s.incident_deployments["incident_id"] == record_id]
    edges = _touching(s, record_id)
    notes = []
    refuted = set(edges.loc[edges["verified_status"] == "refuted", "target_key"])
    for assoc in links.itertuples():
        if assoc.association_type == "suspected" and assoc.deployment_id in refuted:
            notes.append(
                f"The incident tracker still lists {assoc.deployment_id} as 'suspected', but the "
                "graph marks it as refuted. Check the postmortem."
            )

    def tracker_note(assoc: Any) -> str:
        source = assoc.verified_source_document_id
        return assoc.association_type + (f", verified in {source}" if pd.notna(source) else "")

    return RecordDetail(
        ref=ref,
        record_type=RecordType.incidents,
        id=record_id,
        label=f"{row.id} {row.title}",
        attributes=_attrs(
            row,
            [
                "title",
                "severity",
                "status",
                "cause_category",
                "started_at",
                "detected_at",
                "mitigated_at",
                "resolved_at",
                "duration_min",
                "summary",
            ],
        ),
        links=[
            LinkGroup(
                title="Primary service (as recorded)", links=[link(s, row.primary_service_id)]
            ),
            LinkGroup(
                title="Affected services",
                links=[link(s, i.service_id, i.impact_type) for i in impacts.itertuples()],
            ),
            LinkGroup(
                title="Deployments (incident tracker)",
                links=[
                    link(s, assoc.deployment_id, tracker_note(assoc))
                    for assoc in links.itertuples()
                ],
            ),
            LinkGroup(title="Documents", links=_documents_about(s, record_id)),
            LinkGroup(
                title="Graph relations", links=[relation_link(r) for r in edges.itertuples()]
            ),
        ],
        evidence=_snippets(s, edges.loc[edges["relation_type"].isin(EXPLAINING_EDGES), "id"]),
        record_sources=[RecordSource(record_table="incidents", record_id=record_id)],
        notes=notes,
    )


def _service(s: Snapshot, ref: DatasetRef, record_id: str) -> RecordDetail:
    row = _one(s.services, record_id)
    deps = s.dependencies
    outgoing = deps[deps["service_id"] == record_id]
    incoming = deps[deps["depends_on_id"] == record_id]
    inc_ids = s.incident_services.loc[s.incident_services["service_id"] == record_id, "incident_id"]
    incidents = s.incidents[s.incidents["id"].isin(inc_ids)].sort_values("started_at")
    deployments = s.deployments[s.deployments["service_id"] == record_id].sort_values("deployed_at")
    docs = s.documents[s.documents["service_ids"].map(lambda ids: record_id in ids)]
    reasons = {d: s.doc_service_reasons.get(d, {}).get(record_id, set()) for d in docs["id"]}

    def validity(d: Any) -> str:
        if d.current:
            return d.dependency_type if d.valid_from is None else f"since {d.valid_from}"
        return f"until {d.valid_to} (historical)"

    return RecordDetail(
        ref=ref,
        record_type=RecordType.services,
        id=record_id,
        label=row.name,
        attributes={
            **_attrs(
                row,
                [
                    "name",
                    "slug",
                    "subsystem",
                    "team",
                    "tier",
                    "runtime",
                    "environment",
                    "description",
                ],
            ),
            "aliases": s.aliases.get(record_id, []),
        },
        links=[
            LinkGroup(
                title="Depends on",
                links=[
                    link(s, d.id, f"{d.depends_on}: {validity(d)}") for d in outgoing.itertuples()
                ],
            ),
            LinkGroup(
                title="Depended on by",
                links=[link(s, d.id, f"{d.service}: {validity(d)}") for d in incoming.itertuples()],
            ),
            LinkGroup(
                title="Incidents",
                links=[
                    link(s, i.id, f"SEV{i.severity}, {i.started_at:%Y-%m-%d}")
                    for i in incidents.itertuples()
                ],
            ),
            LinkGroup(
                title="Deployments",
                links=[
                    link(s, d.id, f"{d.kind}, {d.deployed_at:%Y-%m-%d}, {d.status}")
                    for d in deployments.itertuples()
                ],
            ),
            LinkGroup(
                title="Documents",
                links=[link(s, d, "; ".join(sorted(reasons[d]))) for d in sorted(reasons)],
            ),
            LinkGroup(
                title="Graph entity",
                links=[RecordLink(record_type=RecordType.entities, id=record_id, label=row.name)],
            ),
        ],
        evidence=_snippets(s, _touching(s, record_id, ["OWNED_BY"])["id"]),
        record_sources=[RecordSource(record_table="services", record_id=record_id)],
    )


def _deployment(s: Snapshot, ref: DatasetRef, record_id: str) -> RecordDetail:
    row = _one(s.deployments, record_id)
    links = s.incident_deployments[s.incident_deployments["deployment_id"] == record_id]
    rollback_of = (
        []
        if pd.isna(row.rolls_back_deployment_id)
        else [link(s, row.rolls_back_deployment_id, "rolled back by this deployment")]
    )
    undone = s.deployments[s.deployments["rolls_back_deployment_id"] == record_id]
    edges = _touching(s, record_id)
    return RecordDetail(
        ref=ref,
        record_type=RecordType.deployments,
        id=record_id,
        label=s.label(record_id),
        attributes=_attrs(
            row,
            [
                "service",
                "version",
                "kind",
                "status",
                "deployed_at",
                "deployed_by",
                "change_summary",
            ],
        ),
        links=[
            LinkGroup(title="Service", links=[link(s, row.service_id)]),
            LinkGroup(
                title="Rollback chain",
                links=rollback_of
                + [link(s, d.id, "rolls this deployment back") for d in undone.itertuples()],
            ),
            LinkGroup(
                title="Incidents (incident tracker)",
                links=[
                    link(s, assoc.incident_id, assoc.association_type)
                    for assoc in links.itertuples()
                ],
            ),
            LinkGroup(title="Documents", links=_documents_about(s, record_id)),
            LinkGroup(
                title="Graph relations", links=[relation_link(r) for r in edges.itertuples()]
            ),
        ],
        evidence=_snippets(s, edges.loc[edges["relation_type"] == "DEPLOYED_TO", "id"]),
        record_sources=[RecordSource(record_table="deployments", record_id=record_id)],
    )


def _dependency(s: Snapshot, ref: DatasetRef, record_id: str) -> RecordDetail:
    row = _one(s.dependencies, record_id)
    ev = s.evidence
    rel_ids = ev.loc[
        (ev["record_table"] == "service_dependencies") & (ev["record_id"] == record_id),
        "relation_id",
    ].unique()
    rels = s.relations[s.relations["id"].isin(rel_ids)]
    endpoints = [link(s, row.service_id, "depends on ->")]
    if row.target_kind == "service":
        endpoints.append(link(s, row.depends_on_id, "<- is depended on"))
    notes = [] if row.current else [f"Historical: valid until {row.valid_to}."]
    return RecordDetail(
        ref=ref,
        record_type=RecordType.dependencies,
        id=record_id,
        label=f"{row.service} depends on {row.depends_on}",
        attributes=_attrs(
            row,
            [
                "service",
                "depends_on",
                "target_kind",
                "dependency_type",
                "criticality",
                "valid_from",
                "valid_to",
                "current",
            ],
        ),
        links=[
            LinkGroup(title="Endpoints", links=endpoints),
            LinkGroup(title="Graph relations", links=[relation_link(r) for r in rels.itertuples()]),
        ],
        evidence=_snippets(s, rel_ids),
        record_sources=[RecordSource(record_table="service_dependencies", record_id=record_id)],
        notes=notes,
    )


def _document_record(s: Snapshot, ref: DatasetRef, record_id: str) -> RecordDetail:
    row = _one(s.documents, record_id)
    reasons = s.doc_service_reasons.get(record_id, {})
    return RecordDetail(
        ref=ref,
        record_type=RecordType.documents,
        id=record_id,
        label=row.title,
        attributes=_attrs(
            row,
            [
                "title",
                "doc_type",
                "created_at",
                "author",
                "source_uri",
                "length_chars",
                "word_count",
                "evidence_spans",
            ],
        ),
        links=[
            LinkGroup(
                title="Services",
                links=[link(s, svc, "; ".join(sorted(r))) for svc, r in sorted(reasons.items())],
            ),
            LinkGroup(title="Referenced records", links=_references(s, record_id)),
        ],
        evidence=[],
        record_sources=[],
    )


def _entity(s: Snapshot, ref: DatasetRef, record_id: str) -> RecordDetail:
    row = _one(s.entities, record_id, column="key")
    outgoing = s.relations[s.relations["source_key"] == record_id]
    incoming = s.relations[s.relations["target_key"] == record_id]
    record_links = []
    if isinstance(row.external_ref, str) and "/" in row.external_ref:
        table, key = row.external_ref.split("/", 1)
        if table in {t.value for t in RecordType}:
            record_links.append(
                RecordLink(
                    record_type=RecordType(table),
                    id=key,
                    label=s.label(key),
                    note=f"corpus.{table}",
                )
            )
    return RecordDetail(
        ref=ref,
        record_type=RecordType.entities,
        id=record_id,
        label=row.canonical_name,
        attributes={
            **_attrs(
                row, ["entity_type", "canonical_name", "external_ref", "out_degree", "in_degree"]
            ),
            "aliases": s.aliases.get(record_id, []),
        },
        links=[
            LinkGroup(title="Source record", links=record_links),
            LinkGroup(
                title=f"Outgoing relations ({len(outgoing)})",
                links=[relation_link(r) for r in outgoing.itertuples()],
            ),
            LinkGroup(
                title=f"Incoming relations ({len(incoming)})",
                links=[relation_link(r) for r in incoming.itertuples()],
            ),
        ],
        evidence=[],
        record_sources=[],
    )


def _relation(s: Snapshot, ref: DatasetRef, record_id: str) -> RecordDetail:
    row = _one(s.relations, record_id)
    sources = _record_sources(s, [record_id])
    record_links = []
    for src in sources:
        key = src.record_id.split("/")[0]
        if record_type_of(key) is not RecordType.entities:
            record_links.append(link(s, key, f"corpus.{src.record_table}"))
    evidence = _snippets(s, [record_id])
    notes = []
    if not evidence and not sources:
        notes.append("No supporting source available.")
    elif not evidence:
        notes.append("Backed by a business record only; no document passage states this edge.")
    if row.verified_status == "refuted":
        notes.append("Refuted: this suspicion was investigated and ruled out.")
    return RecordDetail(
        ref=ref,
        record_type=RecordType.relations,
        id=record_id,
        label=relation_label(row),
        attributes={
            **_attrs(
                row,
                [
                    "relation_type",
                    "source_key",
                    "target_key",
                    "verified_status",
                    "confidence",
                    "valid_from",
                    "valid_to",
                ],
            ),
            "direction": f"{row.source_key} -> {row.target_key}",
        },
        links=[
            LinkGroup(
                title="Source (from)",
                links=[
                    RecordLink(
                        record_type=RecordType.entities,
                        id=row.source_key,
                        label=row.source_name,
                        note=row.source_type,
                    )
                ],
            ),
            LinkGroup(
                title="Target (to)",
                links=[
                    RecordLink(
                        record_type=RecordType.entities,
                        id=row.target_key,
                        label=row.target_name,
                        note=row.target_type,
                    )
                ],
            ),
            LinkGroup(title="Supporting records", links=record_links),
        ],
        evidence=evidence,
        record_sources=sources,
        notes=notes,
    )


def _references(s: Snapshot, document_id: str) -> list[RecordLink]:
    text = s.content[document_id]
    keys = sorted(set(ID_PATTERN.findall(text)) | set(DOC_ID_PATTERN.findall(text)) - {document_id})
    known = set(s.incidents["id"]) | set(s.deployments["id"]) | set(s.documents["id"])
    return [link(s, k, "mentioned in text") for k in keys if k in known]


def document_detail(
    s: Snapshot,
    ref: DatasetRef,
    document_id: str,
    index_profile: str | None,
    chunks: list[dict[str, Any]],
) -> DocumentDetail:
    row = _one(s.documents, document_id)
    ev = s.evidence[
        (s.evidence["evidence_kind"] == "document") & (s.evidence["document_id"] == document_id)
    ]
    rel = s.relations.set_index("id")
    highlights = []
    for e in ev.sort_values(["span_start", "span_end"]).itertuples():
        r = rel.loc[e.relation_id]
        highlights.append(
            Highlight(
                span_start=int(e.span_start),
                span_end=int(e.span_end),
                relation_key=e.relation_id,
                relation_type=r["relation_type"],
                verified_status=r["verified_status"],
                source=RecordLink(
                    record_type=RecordType.entities, id=r["source_key"], label=r["source_name"]
                ),
                target=RecordLink(
                    record_type=RecordType.entities, id=r["target_key"], label=r["target_name"]
                ),
            )
        )
    reasons = s.doc_service_reasons.get(document_id, {})
    if index_profile is None:
        status = "Not indexed yet: no index profile selected or built for this dataset."
    elif not chunks:
        status = f"Index profile {index_profile} has no chunks for this document."
    else:
        status = f"{len(chunks)} chunks in {index_profile}."
    return DocumentDetail(
        ref=ref,
        id=row.id,
        title=row.title,
        doc_type=row.doc_type,
        created_at=row.created_at,
        author=row.author,
        source_uri=row.source_uri,
        content_hash=row.content_hash,
        metadata=row.metadata or {},
        content=s.content[document_id],
        length_chars=int(row.length_chars),
        word_count=int(row.word_count),
        services=[link(s, svc, "; ".join(sorted(r))) for svc, r in sorted(reasons.items())],
        referenced_records=_references(s, document_id),
        highlights=highlights,
        index_profile=index_profile,
        chunks=[ChunkSpan(**c) for c in chunks],
        chunk_status=status,
    )
