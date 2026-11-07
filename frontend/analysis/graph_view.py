"""Graph canvas: deterministic layouts and an Altair rendering with clickable nodes and edges.

Pure functions (no Streamlit) so layouts and chart specs can be unit-tested.
Hops from the start node become concentric rings; paths are laid out left to right.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

import altair as alt
import pandas as pd

WIDTH, HEIGHT = 980, 680
NODE_SELECTION, EDGE_SELECTION = "node", "edge"
MIN_GAP = 0.42  # minimum arc distance between neighbors on a ring, in layout units
ARROW_BACKOFF_PX = 13

# Categorical slots in fixed order (reference palette); shape is a second channel for CVD.
TYPE_STYLE = {
    "service": ("#2a78d6", "circle"),
    "incident": ("#eb6834", "square"),
    "deployment": ("#1baf7a", "diamond"),
    "team": ("#eda100", "cross"),
    "subsystem": ("#e87ba4", "triangle-down"),
    "external_system": ("#008300", "wedge"),
}
EDGE_COLORS = {
    "verified": "#898781",
    "unverified": "#c98500",
    "refuted": "#d03b3b",
    "highlight": "#2a78d6",
}

Position = tuple[float, float]


def ring_layout(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Position]:
    """Seed at the center, one ring per hop; each ring is ordered by its neighbors' angles."""
    by_depth: dict[int, list[str]] = defaultdict(list)
    meta = {n["key"]: n for n in nodes}
    for n in nodes:
        by_depth[n["depth"]].append(n["key"])
    adjacency: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        adjacency[e["source"]].add(e["target"])
        adjacency[e["target"]].add(e["source"])

    pos: dict[str, Position] = {}
    angle: dict[str, float] = {}
    radius = 0.0
    for depth in sorted(by_depth):
        ring = by_depth[depth]
        if depth == 0 or (not pos and len(ring) == 1):
            for key in ring:
                pos[key], angle[key] = (0.0, 0.0), 0.0
            continue

        def anchor(key: str) -> float:
            placed = [angle[n] for n in adjacency[key] if n in angle]
            if not placed:
                return math.pi
            # Circular mean keeps neighbors on either side of +/-pi together.
            return math.atan2(sum(math.sin(a) for a in placed), sum(math.cos(a) for a in placed))

        ordered = sorted(
            ring, key=lambda k: (anchor(k), meta[k]["entity_type"], meta[k]["label"], k)
        )
        radius = max(radius + 1.0, len(ordered) * MIN_GAP / (2 * math.pi))
        start = anchor(ordered[0])
        for i, key in enumerate(ordered):
            theta = start + 2 * math.pi * i / len(ordered)
            pos[key] = (radius * math.cos(theta), radius * math.sin(theta))
            angle[key] = theta
    return pos


def path_layout(paths: list[dict[str, Any]]) -> dict[str, Position]:
    """Hop index on x; alternative paths stacked on y, shared nodes placed once."""
    pos: dict[str, Position] = {}
    rows: dict[int, int] = defaultdict(int)
    for path in paths:
        for hop, key in enumerate(path["nodes"]):
            if key not in pos:
                pos[key] = (float(hop), -float(rows[hop]))
                rows[hop] += 1
    for x in {int(p[0]) for p in pos.values()}:
        column = [k for k, p in pos.items() if int(p[0]) == x]
        offset = (len(column) - 1) / 2
        for k in column:
            pos[k] = (pos[k][0], pos[k][1] + offset)
    return pos


def _bounds(pos: dict[str, Position]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in pos.values()] or [0.0]
    ys = [p[1] for p in pos.values()] or [0.0]
    pad_x = max(0.6, (max(xs) - min(xs)) * 0.08)
    pad_y = max(0.6, (max(ys) - min(ys)) * 0.1)
    x0, x1, y0, y1 = min(xs) - pad_x, max(xs) + pad_x, min(ys) - pad_y, max(ys) + pad_y
    # Same units-per-pixel on both axes, so hop rings render as circles.
    units_per_px = max((x1 - x0) / WIDTH, (y1 - y0) / HEIGHT)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    half_w, half_h = units_per_px * WIDTH / 2, units_per_px * HEIGHT / 2
    return cx - half_w, cx + half_w, cy - half_h, cy + half_h


def _short(text: str, size: int = 26) -> str:
    return text if len(text) <= size else text[: size - 1] + "…"


def build_frames(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    pos: dict[str, Position],
    highlight_edges: set[str],
    selected_node: str | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    x0, x1, y0, y1 = _bounds(pos)
    sx, sy = WIDTH / (x1 - x0), HEIGHT / (y1 - y0)
    labels = {n["key"]: n["label"] for n in nodes}

    pair_count: dict[frozenset, int] = defaultdict(int)
    edge_rows = []
    for e in edges:
        if e["source"] not in pos or e["target"] not in pos:
            continue
        (ax, ay), (bx, by) = pos[e["source"]], pos[e["target"]]
        dx_px, dy_px = (bx - ax) * sx, (by - ay) * sy
        length = math.hypot(dx_px, dy_px) or 1.0
        back = min(ARROW_BACKOFF_PX, length / 3)
        # Parallel edges between the same pair get their midpoint markers spread apart.
        pair = frozenset((e["source"], e["target"]))
        shift = pair_count[pair] * 10
        pair_count[pair] += 1
        nx_, ny_ = -dy_px / length, dx_px / length
        status = "highlight" if e["id"] in highlight_edges else e["verified_status"]
        edge_rows.append(
            {
                "edge_id": e["id"],
                "x": ax,
                "y": ay,
                "x2": bx,
                "y2": by,
                "ax": bx - dx_px / length * back / sx,
                "ay": by - dy_px / length * back / sy,
                "angle": math.degrees(math.atan2(dx_px, dy_px)),
                "mx": (ax + bx) / 2 + nx_ * shift / sx,
                "my": (ay + by) / 2 + ny_ * shift / sy,
                "relation_type": e["relation_type"],
                "from": labels.get(e["source"], e["source"]),
                "to": labels.get(e["target"], e["target"]),
                "status": status,
                "verified_status": e["verified_status"],
                "evidence": e["evidence"],
                "validity": _validity(e),
                "highlight": e["id"] in highlight_edges,
            }
        )
    node_rows = []
    show_all_labels = len(nodes) <= 60
    for n in nodes:
        if n["key"] not in pos:
            continue
        x, y = pos[n["key"]]
        size = 520 if n["is_seed"] else 300 if n.get("is_expanded") else 170
        node_rows.append(
            {
                "key": n["key"],
                "x": x,
                "y": y,
                "label": n["label"],
                "short": _short(n["label"]) if show_all_labels or n["depth"] <= 1 else "",
                "entity_type": n["entity_type"],
                "depth": n["depth"],
                "size": size,
                "in_degree": n["in_degree"],
                "out_degree": n["out_degree"],
                "selected": n["key"] == selected_node,
            }
        )
    return pd.DataFrame(node_rows), pd.DataFrame(edge_rows)


def _validity(e: dict[str, Any]) -> str:
    if not e.get("valid_from") and not e.get("valid_to"):
        return "always"
    return f"{e.get('valid_from') or '…'} to {e.get('valid_to') or '…'}"


def build_chart(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    pos: dict[str, Position],
    highlight_edges: set[str] | None = None,
    selected_node: str | None = None,
) -> alt.LayerChart:
    node_df, edge_df = build_frames(nodes, edges, pos, highlight_edges or set(), selected_node)
    x0, x1, y0, y1 = _bounds(pos)
    x = alt.X("x:Q", scale=alt.Scale(domain=[x0, x1]), axis=None)
    y = alt.Y("y:Q", scale=alt.Scale(domain=[y0, y1]), axis=None)
    status_scale = alt.Scale(domain=list(EDGE_COLORS), range=list(EDGE_COLORS.values()))
    types = [t for t in TYPE_STYLE if t in set(node_df.get("entity_type", []))] or ["service"]
    color = alt.Color(
        "entity_type:N",
        title="node type",
        scale=alt.Scale(domain=types, range=[TYPE_STYLE[t][0] for t in types]),
    )
    shape = alt.Shape(
        "entity_type:N",
        title="node type",
        scale=alt.Scale(domain=types, range=[TYPE_STYLE[t][1] for t in types]),
    )
    edge_tooltip = [
        alt.Tooltip("relation_type:N", title="relation"),
        alt.Tooltip("from:N"),
        alt.Tooltip("to:N"),
        alt.Tooltip("verified_status:N", title="status"),
        alt.Tooltip("evidence:N", title="source"),
        alt.Tooltip("validity:N"),
    ]
    layers = []
    if not edge_df.empty:
        dashed = alt.condition(
            "datum.verified_status != 'verified' && !datum.highlight",
            alt.value([5, 4]),
            alt.value([1, 0]),
        )
        stroke = alt.Color("status:N", scale=status_scale, legend=None)
        layers.append(
            alt.Chart(edge_df)
            .mark_rule(opacity=0.85)
            .encode(
                x=x,
                y=y,
                x2="x2:Q",
                y2="y2:Q",
                color=stroke,
                strokeDash=dashed,
                strokeWidth=alt.condition("datum.highlight", alt.value(3), alt.value(1.3)),
                tooltip=edge_tooltip,
            )
        )
        layers.append(
            alt.Chart(edge_df)
            .mark_point(shape="triangle-up", filled=True, size=70)
            .encode(
                x=alt.X("ax:Q", scale=alt.Scale(domain=[x0, x1]), axis=None),
                y=alt.Y("ay:Q", scale=alt.Scale(domain=[y0, y1]), axis=None),
                angle=alt.Angle("angle:Q", scale=alt.Scale(domain=[0, 360], range=[0, 360])),
                color=stroke,
                tooltip=edge_tooltip,
            )
        )
        edge_pick = alt.selection_point(name=EDGE_SELECTION, fields=["edge_id"], on="click")
        layers.append(
            alt.Chart(edge_df)
            .mark_point(shape="diamond", filled=True, size=55, stroke="white", strokeWidth=1)
            .encode(
                x=alt.X("mx:Q", scale=alt.Scale(domain=[x0, x1]), axis=None),
                y=alt.Y("my:Q", scale=alt.Scale(domain=[y0, y1]), axis=None),
                color=stroke,
                tooltip=edge_tooltip,
            )
            .add_params(edge_pick)
        )
        if len(edge_df) <= 40:
            layers.append(
                alt.Chart(edge_df)
                .mark_text(fontSize=9, dy=-8, opacity=0.75)
                .encode(
                    x=alt.X("mx:Q", scale=alt.Scale(domain=[x0, x1]), axis=None),
                    y=alt.Y("my:Q", scale=alt.Scale(domain=[y0, y1]), axis=None),
                    text="relation_type:N",
                )
            )
    if not node_df.empty:
        node_tooltip = [
            alt.Tooltip("label:N", title="name"),
            alt.Tooltip("key:N", title="id"),
            alt.Tooltip("entity_type:N", title="type"),
            alt.Tooltip("depth:Q", title="hops"),
            alt.Tooltip("in_degree:Q", title="incoming"),
            alt.Tooltip("out_degree:Q", title="outgoing"),
        ]
        layers.append(
            alt.Chart(node_df[node_df["selected"]])
            .mark_point(shape="circle", size=1300, filled=False, strokeWidth=2.5, color="#2a78d6")
            .encode(x=x, y=y)
        )
        node_pick = alt.selection_point(name=NODE_SELECTION, fields=["key"], on="click")
        layers.append(
            alt.Chart(node_df)
            .mark_point(filled=True, opacity=1, stroke="white", strokeWidth=1.5)
            .encode(
                x=x,
                y=y,
                color=color,
                shape=shape,
                size=alt.Size("size:Q", legend=None, scale=None),
                tooltip=node_tooltip,
            )
            .add_params(node_pick)
        )
        layers.append(
            alt.Chart(node_df)
            .mark_text(fontSize=11, dy=17, fontWeight=500)
            .encode(
                x=x,
                y=y,
                text="short:N",
            )
        )
    # Layers share scales by default; edge-status and node-type colors must not be merged.
    return (
        alt.layer(*layers)
        .resolve_scale(color="independent", shape="independent")
        .properties(width=WIDTH, height=HEIGHT)
        .configure_view(strokeWidth=0)
    )


def selection_of(event: Any) -> tuple[str, str] | None:
    """('node', key) or ('edge', id) from Streamlit's chart selection state."""
    try:
        selection = event["selection"]
    except (KeyError, TypeError):
        return None
    for name, kind, field in ((NODE_SELECTION, "node", "key"), (EDGE_SELECTION, "edge", "edge_id")):
        picked = selection.get(name) or []
        if picked and field in picked[0]:
            return kind, picked[0][field]
    return None
