"""Graph Explorer: bounded neighborhood traversal, node/edge selection, paths, provenance."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from functools import partial
from typing import Any

import pandas as pd
import streamlit as st

from frontend import layout
from frontend.analysis import api, graph_view, state

SEED, DEPTH, DIRECTION, TYPES = "g_seed", "g_depth", "g_direction", "g_relation_types"
USE_DATE, AS_OF, REFUTED, MAX_NODES = "g_use_date", "g_as_of", "g_include_refuted", "g_max_nodes"
EXPANDED, MODE, TARGET, DIRECTED = "g_expanded", "g_mode", "g_path_target", "g_path_directed"
PATH_REFUTED, SEARCH, PRESELECT = "g_path_refuted", "g_search", "g_preselect"
CROSS = "g_cross_links"

MODES = ["Neighborhood", "Path"]
DIRECTIONS = {"both": "Both directions", "out": "Outgoing →", "in": "← Incoming"}
DEFAULT_SEED = "SVC-CHECKOUT-API"
STORY_TYPES = ["DEPENDS_ON", "AFFECTED_BY", "TRIGGERED_BY", "RESOLVED_BY"]


def init(as_of: date) -> None:
    defaults = {
        SEED: DEFAULT_SEED,
        DEPTH: 1,
        DIRECTION: "both",
        TYPES: [],
        USE_DATE: False,
        AS_OF: as_of,
        REFUTED: True,
        MAX_NODES: 100,
        EXPANDED: [],
        MODE: MODES[0],
        TARGET: None,
        DIRECTED: False,
        PATH_REFUTED: False,
        SEARCH: "",
        PRESELECT: None,
        CROSS: False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def start_at(key: str) -> None:
    """Make `key` the start node (also used by 'Explore in graph' in the record browser)."""
    ss = st.session_state
    ss[SEED] = key
    ss[EXPANDED] = []
    ss[MODE] = MODES[0]
    ss["da_view"] = "Graph Explorer"


def _expand(key: str) -> None:
    if key != st.session_state[SEED] and key not in st.session_state[EXPANDED]:
        st.session_state[EXPANDED] = [*st.session_state[EXPANDED], key]


def _undo_expand() -> None:
    st.session_state[EXPANDED] = st.session_state[EXPANDED][:-1]


def _reset() -> None:
    st.session_state[EXPANDED] = []
    state.close_detail()


def _path_to(key: str) -> None:
    st.session_state[TARGET] = key
    st.session_state[MODE] = "Path"


def _load_story() -> None:
    ss = st.session_state
    ss.update(
        {
            SEED: DEFAULT_SEED,
            DEPTH: 1,
            DIRECTION: "out",
            TYPES: STORY_TYPES,
            USE_DATE: False,
            REFUTED: True,
            EXPANDED: ["SVC-PAYMENTS-API", "INC-104"],
            MODE: "Neighborhood",
            PRESELECT: ("INC-104", "TRIGGERED_BY"),
        }
    )


def _load_path_example() -> None:
    ss = st.session_state
    ss.update(
        {
            SEED: DEFAULT_SEED,
            TARGET: "DPL-010",
            MODE: "Path",
            TYPES: [],
            DIRECTED: False,
            PATH_REFUTED: False,
            USE_DATE: False,
        }
    )


def _on_canvas_select(key: str) -> None:
    picked = graph_view.selection_of(st.session_state.get(key))
    if picked:
        kind, value = picked
        state.select("entities" if kind == "node" else "relations", value)


def _search_box(ref: dict[str, Any]) -> None:
    c = st.container(key="bar-search").columns([3, 3, 1, 1], vertical_alignment="bottom")
    c[0].text_input(
        "Find a node by ID, name or alias",
        key=SEARCH,
        placeholder="e.g. payment-service, INC-104, kafka, Orders DB",
    )
    query = st.session_state[SEARCH].strip()
    matches = api.get("/analysis/graph/search", **ref, q=query, limit=15) if query else []
    if not matches:
        c[1].caption(
            "Type to search; aliases such as 'payment-service' resolve too."
            if not query
            else "No matching node."
        )
        return
    options = {m["key"]: m for m in matches}
    picked = c[1].selectbox(
        "Matches",
        list(options),
        key=f"g_match_{query}",
        format_func=lambda k: (
            f"{options[k]['label']} · {options[k]['entity_type']} "
            f"(matched {options[k]['matched_on']}: {options[k]['matched_text']})"
        ),
    )
    c[2].button(
        "Start here",
        on_click=start_at,
        args=(picked,),
        width="stretch",
        icon=":material/my_location:",
    )
    c[3].button(
        "Path to",
        on_click=_path_to,
        args=(picked,),
        width="stretch",
        icon=":material/route:",
        help="Find the shortest connection from the start node",
    )


def _controls(facets: dict[str, Any], dmin: date, dmax: date) -> None:
    relation_types = {o["value"]: f"{o['label']} ({o['count']})" for o in facets["relation_types"]}
    ss = st.session_state
    hops = ss[DEPTH]
    summary = (
        f"Traversal: {hops} hop{'s' if hops > 1 else ''} · "
        f"{DIRECTIONS[ss[DIRECTION]].lower()} · "
        f"{len(ss[TYPES]) or 'all'} relation type{'s' if len(ss[TYPES]) != 1 else ''}"
    )
    with layout.panel(summary, key="g_controls_panel", border=True):
        c = st.columns([2, 2, 4, 2], vertical_alignment="bottom")
        c[0].segmented_control(
            "Hops",
            [1, 2, 3],
            key=DEPTH,
            required=True,
            help="How many edges away from the start node to traverse.",
        )
        c[1].selectbox(
            "Direction",
            list(DIRECTIONS),
            key=DIRECTION,
            format_func=DIRECTIONS.get,
            help="Outgoing follows arrows from the node; incoming follows arrows into "
            "it. Edges are always drawn with their stored direction.",
        )
        c[2].multiselect(
            "Relation types",
            list(relation_types),
            key=TYPES,
            format_func=relation_types.get,
            placeholder="All relation types",
        )
        c[3].slider(
            "Max nodes",
            min_value=20,
            max_value=200,
            step=10,
            key=MAX_NODES,
            help="Larger neighborhoods are cut to the closest nodes.",
        )
        c = st.columns([2, 2, 2, 2, 2], vertical_alignment="bottom")
        c[0].toggle(
            "Only edges valid on",
            key=USE_DATE,
            help="Hide relationships whose validity interval excludes this date "
            "(e.g. dependencies that changed during a migration).",
        )
        c[1].date_input(
            "Valid on",
            min_value=dmin,
            max_value=dmax,
            key=AS_OF,
            disabled=not st.session_state[USE_DATE],
            label_visibility="collapsed",
        )
        c[2].toggle(
            "Show refuted edges",
            key=REFUTED,
            help="Refuted edges are suspicions that were ruled out (drawn dashed red).",
        )
        c[3].toggle(
            "Show links between neighbors",
            key=CROSS,
            help="Off: only edges that lead one hop further out are drawn, which keeps the "
            "picture readable. Links of the selected node are always shown.",
        )


def _traversal_params() -> dict[str, Any]:
    ss = st.session_state
    return {
        "relation_type": ss[TYPES],
        "as_of": ss[AS_OF] if ss[USE_DATE] else None,
    }


def _breadcrumb(view: dict[str, Any]) -> None:
    labels = {n["key"]: n["label"] for n in view["nodes"]}
    trail = [labels.get(view["seed"], view["seed"])] + [labels.get(k, k) for k in view["expanded"]]
    c = st.container(key="bar-crumb").columns([6, 1, 1], vertical_alignment="center")
    c[0].markdown(
        "**Start:** "
        + " › ".join(f"`{t}`" for t in trail[:1])
        + ("".join(f" › expanded `{t}`" for t in trail[1:]))
    )
    c[1].button(
        "Undo expand",
        on_click=_undo_expand,
        disabled=not view["expanded"],
        width="stretch",
        icon=":material/undo:",
    )
    c[2].button("Reset", on_click=_reset, width="stretch", icon=":material/restart_alt:")


def _selection() -> tuple[str | None, set[str]]:
    selected = st.session_state.get("da_selected") or {}
    if selected.get("type") == "relations":
        return None, {selected["id"]}
    if selected.get("type") in ("entities", "services", "incidents", "deployments"):
        return selected["id"], set()
    return None, set()


def _apply_preselect(view: dict[str, Any]) -> None:
    wanted = st.session_state.get(PRESELECT)
    if not wanted:
        return
    st.session_state[PRESELECT] = None
    source, relation_type = wanted
    for e in view["edges"]:
        if e["source"] == source and e["relation_type"] == relation_type:
            state.select("relations", e["id"])
            return


def active_theme() -> str:
    try:
        return st.context.theme.type or "light"
    except AttributeError:
        return "light"


def _canvas(
    nodes: list[dict],
    edges: list[dict],
    pos: dict,
    key: str,
    highlight: set[str],
    selected_node: str | None,
    path_mode: bool = False,
) -> None:
    chart = graph_view.build_chart(
        nodes,
        edges,
        pos,
        highlight,
        selected_node,
        theme=active_theme(),
        radial_labels=not path_mode,
        dim_unfocused=not path_mode,
        width=graph_view.COMPACT_WIDTH if layout.is_compact() else graph_view.WIDTH,
    )
    with st.container(border=True):
        st.markdown(
            "**Edges:** :gray[━ verified] · :red[┅ refuted] · :orange[┅ unverified] · "
            ":blue[━ selected / path] · arrowheads show the stored direction.  \n"
            ":gray[Click a node to focus it (its links stay, the rest fades) or an edge's ◆ "
            "midpoint to see the passage that supports it.]"
        )
        st.altair_chart(chart, key=key, on_select=partial(_on_canvas_select, key), width="content")


def _node_actions(view_keys: set[str]) -> None:
    selected = st.session_state.get("da_selected") or {}
    key = selected.get("id")
    if selected.get("type") not in ("entities", "services", "incidents", "deployments") or (
        key not in view_keys
    ):
        return
    c = st.columns([1, 1, 1, 3])
    c[0].button(
        "Expand neighbors",
        on_click=_expand,
        args=(key,),
        width="stretch",
        icon=":material/unfold_more:",
        disabled=key == st.session_state[SEED] or key in st.session_state[EXPANDED],
    )
    c[1].button(
        "Make start node",
        on_click=start_at,
        args=(key,),
        width="stretch",
        icon=":material/my_location:",
        disabled=key == st.session_state[SEED],
    )
    c[2].button(
        "Path from start",
        on_click=_path_to,
        args=(key,),
        width="stretch",
        icon=":material/route:",
        disabled=key == st.session_state[SEED],
    )


def _tables(nodes: list[dict], edges: list[dict], export: dict[str, Any], name: str) -> None:
    with st.expander(f"Table view ({len(nodes)} nodes, {len(edges)} edges)"):
        left, right = st.columns(2)
        left.dataframe(
            pd.DataFrame(nodes)[
                ["key", "label", "entity_type", "depth", "in_degree", "out_degree"]
            ],
            hide_index=True,
            width="stretch",
            height=300,
        )
        if edges:
            right.dataframe(
                pd.DataFrame(edges)[
                    [
                        "id",
                        "source",
                        "relation_type",
                        "target",
                        "verified_status",
                        "evidence",
                        "valid_from",
                        "valid_to",
                    ]
                ],
                hide_index=True,
                width="stretch",
                height=300,
            )
        st.download_button(
            "Download graph JSON",
            data=json.dumps(export, indent=2, default=str),
            file_name=name,
            mime="application/json",
            icon=":material/download:",
        )


def _neighborhood(ref: dict[str, Any]) -> set[str]:
    ss = st.session_state
    params = {
        **ref,
        **_traversal_params(),
        "node": ss[SEED],
        "depth": ss[DEPTH],
        "direction": ss[DIRECTION],
        "include_refuted": ss[REFUTED],
        "expand": ss[EXPANDED],
        "max_nodes": ss[MAX_NODES],
    }
    view = api.get("/analysis/graph/neighborhood", **params)
    _apply_preselect(view)
    _breadcrumb(view)
    selected_node, highlight = _selection()
    shown, hidden = graph_view.visible_edges(view["nodes"], view["edges"], ss[CROSS], selected_node)
    summary = (
        f"{view['projection']['description']} {len(view['nodes'])} nodes, "
        f"{len(shown)} of {len(view['edges'])} edges drawn."
    )
    if hidden:
        summary += f" {hidden} links between neighbors hidden (see *Show links between neighbors*)."
    st.caption(summary)
    if view["truncated"]:
        st.warning(f"Too many nodes: {view['truncation_reason']}", icon=":material/hub:")
    pos = graph_view.ring_layout(view["nodes"], view["edges"])
    key = f"g_canvas_{abs(hash(json.dumps(params, sort_keys=True, default=str)))}"
    _canvas(view["nodes"], shown, pos, key, highlight, selected_node)
    keys = {n["key"] for n in view["nodes"]}
    _node_actions(keys)
    _tables(view["nodes"], view["edges"], view, f"graph-{ss[SEED]}.json")
    return keys


def _arrow(step: dict[str, Any]) -> str:
    parts = []
    for e in step["edges"]:
        if e["source"] == step["from_key"]:
            parts.append(f"—{e['relation_type']}→")
        else:
            parts.append(f"←{e['relation_type']}—")
    return " / ".join(parts)


def _path(ref: dict[str, Any]) -> set[str]:
    ss = st.session_state
    c = st.columns([3, 3, 2, 2], vertical_alignment="bottom")
    c[0].markdown(f"**From** `{ss[SEED]}` (start node)")
    c[1].markdown(
        f"**To** `{ss[TARGET]}`"
        if ss[TARGET]
        else "**To**: search a node above and press *Path to*."
    )
    c[2].toggle(
        "Follow edge direction",
        key=DIRECTED,
        help="Off: any connection, edges may be walked against their arrow.",
    )
    c[3].toggle("Allow refuted edges", key=PATH_REFUTED)
    if not ss[TARGET]:
        return set()
    params = {
        **ref,
        **_traversal_params(),
        "source": ss[SEED],
        "target": ss[TARGET],
        "directed": ss[DIRECTED],
        "include_refuted": ss[PATH_REFUTED],
    }
    result = api.get("/analysis/graph/path", **params)
    (st.info if result["paths"] else st.warning)(result["message"], icon=":material/route:")
    if not result["paths"]:
        return set()
    labels = {n["key"]: n["label"] for n in result["nodes"]}
    for i, p in enumerate(result["paths"], start=1):
        chain = labels.get(p["nodes"][0], p["nodes"][0])
        for step in p["steps"]:
            chain += f"  {_arrow(step)}  {labels.get(step['to_key'], step['to_key'])}"
        st.markdown(f"{i}. {chain}")
    edges = {e["id"]: e for p in result["paths"] for s in p["steps"] for e in s["edges"]}
    selected_node, highlight = _selection()
    pos = graph_view.path_layout(result["paths"])
    key = f"g_path_{abs(hash(json.dumps(params, sort_keys=True, default=str)))}"
    _canvas(
        result["nodes"],
        list(edges.values()),
        pos,
        key,
        highlight | set(edges),
        selected_node,
        path_mode=True,
    )
    keys = {n["key"] for n in result["nodes"]}
    _node_actions(keys)
    _tables(result["nodes"], list(edges.values()), result, f"path-{ss[SEED]}-{ss[TARGET]}.json")
    return keys


def render(
    ref: dict[str, Any],
    facets: dict[str, Any],
    dataset: dict[str, Any],
    detail: Callable[[dict[str, Any]], None],
) -> None:
    dmin, dmax = date.fromisoformat(dataset["period_start"]), date.fromisoformat(dataset["as_of"])
    init(dmax)
    st.caption(
        "Explore local neighborhoods rather than the whole graph. Every edge is typed and "
        "directed; click it to see the passage or record that supports it."
    )
    _search_box(ref)
    _controls(facets, dmin, dmax)
    c = st.columns([3, 2, 2], vertical_alignment="center")
    c[0].segmented_control("Mode", MODES, key=MODE, required=True, label_visibility="collapsed")
    c[1].button(
        "Example: Checkout → INC-104",
        on_click=_load_story,
        width="stretch",
        icon=":material/play_circle:",
        help="Checkout API depends on Payments API, which was affected by INC-104, "
        "triggered by deployment v2.8.0.",
    )
    c[2].button(
        "Example: shortest path",
        on_click=_load_path_example,
        width="stretch",
        icon=":material/route:",
    )
    if st.session_state[MODE] == "Neighborhood":
        _neighborhood(ref)
    else:
        _path(ref)
    st.session_state["da_node_applied"] = st.session_state[SEED]
    st.query_params["node"] = st.session_state[SEED]
    detail(ref)
