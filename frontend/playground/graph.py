"""Draws a strategy's graph paths on the Graph Explorer canvas."""

from __future__ import annotations

from collections import Counter
from typing import Any

import streamlit as st

from frontend import layout
from frontend.analysis import graph_view
from frontend.analysis.graph_page import active_theme

Row = dict[str, Any]
HOP_SPREAD, ROW_SPREAD = 2.5, 0.6


def _evidence_label(edge: Row, ranks: dict[str, int]) -> str:
    found = sorted(ranks[e] for e in edge["evidence_ids"] if e in ranks)
    return "evidence " + ", ".join(f"#{rank}" for rank in found) if found else "graph record"


def path_graph(paths: list[Row], evidence: list[Row]) -> tuple[list[Row], list[Row]]:
    """Merges paths into the nodes and edges the canvas expects; shared parts appear once."""
    ranks = {item["evidence_id"]: item["rank"] for item in evidence}
    unique = {edge["id"]: edge for path in paths for edge in path["edges"]}
    depth: dict[str, int] = {}
    for path in paths:
        for hop, key in enumerate(path["nodes"]):
            depth[key] = min(hop, depth.get(key, hop))

    incoming = Counter(edge["target"] for edge in unique.values())
    outgoing = Counter(edge["source"] for edge in unique.values())
    details = {}
    for edge in unique.values():
        details[edge["source"]] = (edge["source_label"], edge["source_type"])
        details[edge["target"]] = (edge["target_label"], edge["target_type"])
    nodes = [
        {
            "key": key,
            "label": details[key][0],
            "description": details[key][0],
            "entity_type": details[key][1],
            "depth": hops,
            "is_seed": hops == 0,
            "in_degree": incoming[key],
            "out_degree": outgoing[key],
        }
        for key, hops in depth.items()
        if key in details
    ]
    edges = [
        {
            "id": edge["id"],
            "source": edge["source"],
            "target": edge["target"],
            # Every path edge is drawn highlighted, so a refuted one must say so in its label.
            "relation_type": edge["relation_type"]
            + (" (refuted)" if edge["verified_status"] == "refuted" else ""),
            "verified_status": edge["verified_status"],
            "evidence": _evidence_label(edge, ranks),
            "valid_from": edge["valid_from"],
            "valid_to": edge["valid_to"],
        }
        for edge in unique.values()
    ]
    return nodes, edges


def canvas_layout(paths: list[Row], compact: bool) -> dict[str, graph_view.Position]:
    # path_layout keeps a node where it first appears, so shortest paths first gives every node
    # its earliest hop and stops edges running along a column through other nodes.
    positions = graph_view.path_layout(sorted(paths, key=lambda path: len(path["nodes"])))
    if compact:
        return positions
    # Unstretched, a small graph is tall and thin on a wide canvas.
    return {key: (x * HOP_SPREAD, y * ROW_SPREAD) for key, (x, y) in positions.items()}


def render_paths(result: Row) -> None:
    paths = result["graph_paths"]
    nodes, edges = path_graph(paths, result["evidence"])
    compact = layout.is_compact()
    chart = graph_view.build_chart(
        nodes,
        edges,
        canvas_layout(paths, compact),
        {edge["id"] for edge in edges},
        theme=active_theme(),
        radial_labels=False,
        dim_unfocused=False,
        width=graph_view.COMPACT_WIDTH if compact else graph_view.WIDTH,
    )
    st.markdown(f"**Graph paths** · {len(paths)}")
    with st.container(border=True):
        st.caption(
            "Hops run left to right from the entity in the question. Arrowheads show the stored "
            "direction. Hover a node or edge for details."
        )
        st.altair_chart(chart, key=f"pg-graph-{result['strategy']}", width="content")
    with st.expander("Paths as text"):
        for path in paths:
            st.text("\n".join(path["steps"]))
