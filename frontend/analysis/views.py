"""Data Analysis page: shared controls, Overview, Records & Documents, detail panels."""

from __future__ import annotations

import json
from functools import partial
from typing import Any
from urllib.parse import quote

import pandas as pd
import streamlit as st

from frontend.analysis import api, charts, state
from frontend.analysis.api import LabApiError
from frontend.analysis.rendering import highlight_html, snippet_html

PAGE_SIZE = 50
CHART_ROWS = [
    ["doc_types", "docs_by_service"],
    ["doc_length", "incident_severity"],
    ["incident_timeline"],
    ["service_severity", "evidence_coverage"],
    ["entity_types", "relation_types"],
]
DOC_MODES = ["Highlighted source", "Rendered markdown", "Raw text"]


def render() -> None:
    st.title("Data Analysis")
    st.caption(
        "Read-only exploration of the corpus the retrievers will search. Every chart leads to "
        "its records, and every record leads to its sources."
    )
    try:
        datasets = api.get("/analysis/datasets")
    except LabApiError as exc:
        st.error(str(exc))
        st.stop()
    if not datasets:
        st.info("No dataset is loaded yet. Run `make migrate && make seed`, then reload.")
        st.stop()

    ref = _snapshot_controls(datasets)
    try:
        facets = api.get("/analysis/facets", **ref)
    except LabApiError as exc:
        st.error(str(exc))
        st.stop()
    state.init(facets)
    _apply_deep_link()
    _filter_bar(facets)
    filters = state.api_filters(facets)

    st.segmented_control(
        "View", state.VIEWS, key="da_view", required=True, label_visibility="collapsed"
    )
    try:
        if st.session_state["da_view"] == "Overview":
            _overview(ref, filters, facets)
        else:
            _records(ref, filters)
            _detail(ref)
    except LabApiError as exc:
        st.error(str(exc))


# ---------------------------------------------------------------- shared controls


def _apply_deep_link() -> None:
    """`?record=<type>/<id>` opens that record, so any record can be shared as a stable link."""
    ss = st.session_state
    target = st.query_params.get("record")
    if not target or target == ss.get("da_link_applied") or "/" not in target:
        return
    record_type, record_id = target.split("/", 1)
    ss["da_link_applied"] = target
    if record_type in state.RECORD_TYPES:
        state.select(record_type, record_id)
        ss["da_view"] = "Records & Documents"
        ss["da_record_type"] = record_type


def _sync_deep_link(selected: dict[str, Any] | None) -> None:
    target = f"{selected['type']}/{selected['id']}" if selected else None
    if target:
        st.session_state["da_link_applied"] = target
        st.query_params["record"] = target
    elif "record" in st.query_params:
        del st.query_params["record"]


def _reset_snapshot() -> None:
    for key in list(st.session_state):
        if key.startswith(("f_", "da_")) and key not in ("da_dataset", "da_graph", "da_index"):
            del st.session_state[key]


def _snapshot_controls(datasets: list[dict[str, Any]]) -> dict[str, Any]:
    cols = st.columns([2, 2, 2, 4])
    by_id = {d["id"]: d for d in datasets}
    dataset_id = cols[0].selectbox(
        "Dataset", list(by_id), key="da_dataset", on_change=_reset_snapshot
    )
    info = by_id[dataset_id]
    graphs = {g["id"]: g for g in info["graphs"]}
    graph_id = cols[1].selectbox(
        "Graph source",
        list(graphs),
        key="da_graph",
        on_change=_reset_snapshot,
        format_func=lambda g: f"{graphs[g]['kind']} ({g})",
        disabled=len(graphs) < 2,
        help="Curated graphs are derived from canonical facts (upper-bound baseline). "
        "Extracted graphs appear here once the extraction pipeline has run.",
    )
    profiles = [p["id"] for p in info["index_profiles"]]
    index_profile = cols[2].selectbox(
        "Index profile",
        profiles or ["not indexed"],
        key="da_index",
        disabled=not profiles,
        help="Chunk boundaries are shown in the document viewer once an index is built.",
    )
    cols[3].caption(
        f"**{info['company']}** · data as of {info['as_of']} · period {info['period_start']} "
        f"to {info['period_end']}  \nloaded {info['loaded_at'][:19].replace('T', ' ')} · corpus "
        f"`{info['corpus_hash'][:12]}`"
    )
    ref: dict[str, Any] = {"dataset": dataset_id, "graph": graph_id}
    if profiles:
        ref["index_profile"] = index_profile
    return ref


def _label_with_count(options: list[dict[str, Any]]) -> dict[Any, str]:
    return {o["value"]: f"{o['label']} ({o['count']})" for o in options}


def _filter_bar(facets: dict[str, Any]) -> None:
    services = {o["value"]: o["label"] for o in facets["services"]}
    doc_types = _label_with_count(facets["doc_types"])
    severities = {int(o["value"]): f"{o['label']} ({o['count']})" for o in facets["severities"]}
    entity_types = _label_with_count(facets["entity_types"])
    relation_types = _label_with_count(facets["relation_types"])
    dmin, dmax = state.date_bounds(facets)
    with st.container(border=True):
        c = st.columns([2, 2, 2, 2])
        c[0].selectbox(
            "Service",
            [None, *services],
            key=state.SERVICE,
            placeholder="All services",
            format_func=lambda v: "All services" if v is None else services[v],
        )
        c[1].multiselect(
            "Document type",
            list(doc_types),
            key=state.DOC_TYPES,
            format_func=doc_types.get,
            placeholder="All types",
        )
        c[2].multiselect(
            "Incident severity",
            list(severities),
            key=state.SEVERITIES,
            format_func=severities.get,
            placeholder="All severities",
        )
        c[3].date_input(
            "Date range",
            min_value=dmin,
            max_value=dmax,
            key=state.DATES,
            help="Documents by creation date, incidents by start, deployments by "
            "deploy time, dependencies and relations by validity.",
        )
        c = st.columns([2, 2, 3, 1])
        c[0].multiselect(
            "Entity type",
            list(entity_types),
            key=state.ENTITY_TYPES,
            format_func=entity_types.get,
            placeholder="All entity types",
        )
        c[1].multiselect(
            "Relation type",
            list(relation_types),
            key=state.RELATION_TYPES,
            format_func=relation_types.get,
            placeholder="All relation types",
        )
        c[2].text_input(
            "Search IDs, names, titles and document text",
            key=state.QUERY,
            placeholder="e.g. INC-104, payment-service, connection pool",
        )
        c[3].button("Clear filters", on_click=state.clear_filters, args=(facets,), width="stretch")
        chips = []
        if st.session_state[state.LENGTH]:
            lo, hi = st.session_state[state.LENGTH]
            chips.append((f"length {lo:,}-{hi:,} chars", state.LENGTH))
        if st.session_state[state.EVIDENCE]:
            chips.append((f"evidence: {st.session_state[state.EVIDENCE]}", state.EVIDENCE))
        if chips:
            cols = st.columns(len(chips) + 4)
            for col, (label, key) in zip(cols, chips, strict=False):
                col.button(
                    f"✕ {label}",
                    key=f"chip-{key}",
                    on_click=lambda k=key: st.session_state.__setitem__(k, None),
                )


# ---------------------------------------------------------------- overview


def _fingerprint(filters: dict[str, Any]) -> str:
    return str(abs(hash(json.dumps(filters, sort_keys=True, default=str))))


def _on_chart_select(spec: dict[str, Any], key: str, facets: dict[str, Any]) -> None:
    state.apply_chart_click(spec, charts.selection_of(st.session_state.get(key)), facets)


def _overview(ref: dict[str, Any], filters: dict[str, Any], facets: dict[str, Any]) -> None:
    ov = api.get("/analysis/overview", **ref, **filters)
    cards = ov["cards"]
    for start in range(0, len(cards), 6):
        cols = st.columns(6)
        for col, card in zip(cols, cards[start : start + 6], strict=False):
            value = card["value"]
            if card.get("total") is not None and card["total"] != value:
                value = f"{value} / {card['total']}"
            col.metric(card["label"], value, help=card["help"], border=True)

    if ov["observations"]:
        with st.expander(f"Observations ({len(ov['observations'])})", expanded=True):
            for i, obs in enumerate(ov["observations"]):
                left, right = st.columns([6, 1], vertical_alignment="center")
                icon = ":material/warning:" if obs["level"] == "warning" else ":material/info:"
                left.markdown(f"{icon} {obs['message']}")
                right.button(
                    "Show records",
                    key=f"obs-{i}",
                    width="stretch",
                    on_click=state.apply_observation,
                    args=(obs, facets),
                )

    specs = {c["id"]: c for c in ov["charts"]}
    fingerprint = _fingerprint(filters)
    for row in CHART_ROWS:
        cols = st.columns(len(row))
        for col, chart_id in zip(cols, row, strict=True):
            spec = specs[chart_id]
            with col.container(border=True):
                st.markdown(f"**{spec['title']}**")
                st.caption(spec["description"])
                chart = charts.build_chart(spec, filters)
                if chart is None:
                    st.caption("No data for the current filters.")
                    continue
                key = f"chart-{chart_id}-{fingerprint}"
                st.altair_chart(
                    chart,
                    key=key,
                    width="stretch",
                    on_select=partial(_on_chart_select, spec, key, facets),
                )
                action = "Drag" if spec["kind"] == "timeline" else "Click"
                hint = f"{action} to filter {state.RECORD_LABELS[spec['record_type']].lower()}."
                if spec["applied_filters"]:
                    hint += f" Filters used: {', '.join(spec['applied_filters'])}."
                st.caption(hint)

    st.divider()
    st.subheader("Filtered records")
    _records(ref, filters)
    _detail(ref)


# ---------------------------------------------------------------- records


def _records(ref: dict[str, Any], filters: dict[str, Any]) -> None:
    ss = st.session_state
    rt = st.segmented_control(
        "Record type",
        state.RECORD_TYPES,
        key="da_record_type",
        format_func=state.RECORD_LABELS.get,
        required=True,
    )
    sort_key, desc_key = f"da_sort_{rt}", f"da_desc_{rt}"
    ss.setdefault(sort_key, None)
    ss.setdefault(desc_key, False)
    params = {
        **ref,
        **filters,
        "record_type": rt,
        "limit": PAGE_SIZE,
        "offset": (ss["da_page"] - 1) * PAGE_SIZE,
        "sort": ss[sort_key],
        "descending": ss[desc_key] if ss[sort_key] else None,
    }
    page = api.get("/analysis/records", **params)
    pages = max(1, -(-page["total"] // PAGE_SIZE))
    if ss["da_page"] > pages:
        ss["da_page"] = 1
        page = api.get("/analysis/records", **{**params, "offset": 0})

    label = state.RECORD_LABELS[rt].lower()
    summary = f"**{page['total']}** of {page['unfiltered_total']} {label} match."
    if page["applied_filters"]:
        summary += f" Applied: {', '.join(page['applied_filters'])}."
    if page["ignored_filters"]:
        summary += f" Not applicable to {label}: {', '.join(page['ignored_filters'])}."

    c = st.columns([4, 2, 1, 1, 1, 1], vertical_alignment="bottom")
    c[0].markdown(summary)
    c[1].selectbox(
        "Sort by",
        [None, *page["columns"]],
        key=sort_key,
        placeholder=f"default ({page['sort']})",
        format_func=lambda v: f"default ({page['sort']})" if v is None else v,
    )
    c[2].toggle("Descending", key=desc_key, disabled=ss[sort_key] is None)
    c[3].number_input("Page", min_value=1, max_value=pages, key="da_page")
    export = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    c[4].download_button(
        "CSV",
        data=api.get_text("/analysis/export", **export, format="csv"),
        file_name=f"{ref['dataset']}-{rt}.csv",
        mime="text/csv",
        icon=":material/download:",
        width="stretch",
        help="Export all filtered rows (up to 10,000).",
    )
    c[5].download_button(
        "JSON",
        data=api.get_text("/analysis/export", **export, format="json"),
        file_name=f"{ref['dataset']}-{rt}.json",
        mime="application/json",
        icon=":material/download:",
        width="stretch",
    )

    df = pd.DataFrame(page["items"], columns=page["columns"])
    if df.empty:
        st.info("No records match the current filters.")
        return
    config = {
        col: st.column_config.DatetimeColumn(col, format="YYYY-MM-DD HH:mm")
        for col in df.columns
        if col.endswith("_at")
    }
    table_key = f"table-{rt}-{_fingerprint(params)}"
    event = st.dataframe(
        df,
        key=table_key,
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
        column_config=config,
        width="stretch",
        height=min(36 * (len(df) + 1) + 2, 420),
    )
    rows = event.selection.rows if event else []
    if rows:
        marker = (table_key, df.iloc[rows[0]]["id"])
        if ss["da_table_seen"] != marker:
            ss["da_table_seen"] = marker
            state.select(rt, str(marker[1]))
    else:
        st.caption("Select a row to open its details and sources.")


# ---------------------------------------------------------------- detail panels


def _detail(ref: dict[str, Any]) -> None:
    selected = st.session_state.get("da_selected")
    _sync_deep_link(selected)
    if not selected:
        return
    st.divider()
    with st.container(border=True):
        trail = st.session_state["da_history"][-3:]
        c = st.columns([1, 1, 6], vertical_alignment="center")
        c[0].button(
            "Back",
            icon=":material/arrow_back:",
            on_click=state.back,
            disabled=not st.session_state["da_history"],
            width="stretch",
        )
        c[1].button("Close", icon=":material/close:", on_click=state.close_detail, width="stretch")
        if trail:
            c[2].caption(
                "Trail: " + " → ".join(s["id"] for s in trail) + f" → **{selected['id']}**"
            )
        try:
            if selected["type"] == "documents":
                _document(ref, selected)
            else:
                _record(ref, selected)
        except LabApiError as exc:
            if exc.status == 404:
                st.warning(f"{selected['id']} does not exist in this snapshot.")
            else:
                raise


def _on_link(key: str, links: list[dict[str, Any]]) -> None:
    index = st.session_state.get(key)
    if index is not None:
        target = links[index]
        state.select(target["record_type"], target["id"])


def _link_label(link: dict[str, Any]) -> str:
    def clip(value: str, size: int) -> str:
        return value if len(value) <= size else value[: size - 1] + "…"

    text = link["label"]
    if not text.startswith(link["id"]):
        text = f"{link['id']} · {text}"
    text = clip(text, 64)
    if link.get("note"):
        text += f" — {clip(link['note'], 40)}"
    return text


def _link_groups(groups: list[dict[str, Any]], key_prefix: str) -> None:
    for i, group in enumerate(groups):
        links = group["links"]
        if not links:
            st.caption(f"{group['title']}: none")
            continue
        key = f"{key_prefix}-links-{i}"
        st.pills(
            group["title"],
            options=list(range(len(links))),
            key=key,
            format_func=lambda j, links=links: _link_label(links[j]),
            on_change=_on_link,
            args=(key, links),
        )


def _record(ref: dict[str, Any], selected: dict[str, Any]) -> None:
    rt, record_id = selected["type"], selected["id"]
    detail = api.get(f"/analysis/records/{rt}/{quote(record_id, safe='')}", **ref)
    st.subheader(detail["label"])
    st.caption(state.RECORD_LABELS[rt].rstrip("s") if rt != "entities" else "Entity")
    st.code(record_id, language=None)
    for note in detail["notes"]:
        st.warning(note, icon=":material/report:")
    left, right = st.columns([2, 3])
    with left:
        st.markdown("**Attributes**")
        rows = [
            {"field": k, "value": ", ".join(map(str, v)) if isinstance(v, list) else str(v)}
            for k, v in detail["attributes"].items()
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        if detail["record_sources"]:
            st.caption(
                "Business records: "
                + ", ".join(
                    f"`{s['record_table']}/{s['record_id']}`" for s in detail["record_sources"]
                )
            )
    with right:
        st.markdown("**Connected records**")
        _link_groups(detail["links"], f"{rt}-{record_id}")
    if detail["evidence"]:
        st.markdown(f"**Supporting passages ({len(detail['evidence'])})**")
        for i, ev in enumerate(detail["evidence"]):
            c = st.columns([5, 1], vertical_alignment="center")
            c[0].caption(
                f"{ev['relation_type']} · {ev['document_title']} (`{ev['document_id']}`) · "
                f"chars {ev['span_start']}-{ev['span_end']}"
            )
            c[1].button(
                "Open in document",
                key=f"ev-{record_id}-{i}",
                width="stretch",
                on_click=state.select,
                args=("documents", ev["document_id"], (ev["span_start"], ev["span_end"])),
            )
            st.html(snippet_html(ev["text"]))


def _document(ref: dict[str, Any], selected: dict[str, Any]) -> None:
    doc_id = selected["id"]
    doc = api.get(f"/analysis/documents/{quote(doc_id, safe='')}", **ref)
    st.subheader(doc["title"])
    st.code(doc_id, language=None)
    facts = [
        ("Type", doc["doc_type"]),
        ("Created", doc["created_at"][:10]),
        ("Author", doc["author"]),
        ("Length", f"{doc['length_chars']:,} chars · {doc['word_count']:,} words"),
        ("Edges supported", str(len(doc["highlights"]))),
    ]
    for col, (label, value) in zip(st.columns(len(facts)), facts, strict=True):
        col.caption(label)
        col.text(value)
    st.caption(
        f"Source `{doc['source_uri']}` · dataset {doc['ref']['dataset']} · content hash "
        f"`{doc['content_hash'][:12]}`"
    )
    with st.expander("Metadata"):
        st.json(doc["metadata"])
    _link_groups(
        [
            {"title": "Services (and why)", "links": doc["services"]},
            {"title": "Records referenced in the text", "links": doc["referenced_records"]},
        ],
        f"doc-{doc_id}",
    )

    focus = tuple(selected["focus"]) if selected.get("focus") else None
    if doc["highlights"]:
        st.markdown("**Graph edges supported by this document**")
        hl = pd.DataFrame(
            [
                {
                    "relation": h["relation_type"],
                    "from": h["source"]["label"],
                    "to": h["target"]["label"],
                    "status": h["verified_status"],
                    "chars": f"{h['span_start']}-{h['span_end']}",
                    "edge": h["relation_key"],
                }
                for h in doc["highlights"]
            ]
        )
        event = st.dataframe(
            hl,
            key=f"hl-{doc_id}",
            on_select="rerun",
            selection_mode="single-row",
            hide_index=True,
            width="stretch",
            height=min(36 * (len(hl) + 1) + 2, 280),
        )
        if event and event.selection.rows:
            h = doc["highlights"][event.selection.rows[0]]
            focus = (h["span_start"], h["span_end"])
            st.button(
                "Open this edge",
                key=f"edge-{doc_id}",
                on_click=state.select,
                args=("relations", h["relation_key"]),
            )
    if focus:
        st.markdown(f"**Selected passage** (chars {focus[0]}-{focus[1]})")
        st.html(snippet_html(doc["content"][focus[0] : focus[1]].strip()))

    mode = st.segmented_control(
        "Document view", DOC_MODES, default=DOC_MODES[0], key=f"mode-{doc_id}", required=True
    )
    if mode == "Highlighted source":
        st.html(highlight_html(doc["content"], doc["highlights"], focus))
    elif mode == "Rendered markdown":
        with st.container(border=True, height=640):
            st.markdown(doc["content"])
    else:
        st.code(doc["content"], language=None, wrap_lines=True)
    st.info(doc["chunk_status"], icon=":material/view_agenda:")
