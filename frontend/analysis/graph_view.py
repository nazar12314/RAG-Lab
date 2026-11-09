"""Graph canvas: deterministic layouts and an Altair rendering with clickable nodes and edges.

Pure functions (no Streamlit) so layouts and chart specs can be unit-tested.
Hops from the start node become concentric rings; paths are laid out left to right.

Readability rules:
- colors come from the reference palette for the active light/dark theme;
- by default only hop-to-hop edges are drawn; edges between nodes on the same ring are
  hidden unless requested or touching the focused node;
- a focused (clicked) node keeps its edges and neighbors in front and dims the rest;
- labels sit outside the ring, aligned away from the center.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import altair as alt
import pandas as pd

WIDTH, HEIGHT = 1180, 720
COMPACT_WIDTH = 320  # fits a ~390px phone viewport inside a bordered container
NODE_SELECTION, EDGE_SELECTION = "node", "edge"
MIN_GAP = 0.55  # minimum arc distance between neighbors on a ring, in layout units
RING_STEP = 1.7  # distance between rings; leaves room for outward labels of the inner ring
ARROW_BACKOFF_PX = 13
LABEL_OFFSET_PX = 12
DIM_EDGE, DIM_NODE = 0.3, 0.45  # unfocused context stays legible, especially on dark

NODE_TYPES = ["service", "incident", "deployment", "team", "subsystem", "external_system"]
SHAPES = {
    "service": "circle",
    "incident": "square",
    "deployment": "diamond",
    "team": "cross",
    "subsystem": "triangle-down",
    "external_system": "wedge",
}


@dataclass(frozen=True)
class Theme:
    nodes: dict[str, str]
    text: str
    muted: str
    edge: str
    edge_focus: str
    refuted: str
    unverified: str
    highlight: str
    node_stroke: str


# Categorical slots in fixed order (reference palette), stepped per mode; shape is the second
# channel so node type never relies on color alone.
THEMES = {
    "light": Theme(
        nodes={
            "service": "#2a78d6",
            "incident": "#eb6834",
            "deployment": "#1baf7a",
            "team": "#eda100",
            "subsystem": "#e87ba4",
            "external_system": "#008300",
        },
        text="#0b0b0b",
        muted="#52514e",
        edge="#a3a29c",
        edge_focus="#52514e",
        refuted="#d03b3b",
        unverified="#c98500",
        highlight="#2a78d6",
        node_stroke="#ffffff",
    ),
    "dark": Theme(
        nodes={
            "service": "#3987e5",
            "incident": "#d95926",
            "deployment": "#199e70",
            "team": "#c98500",
            "subsystem": "#d55181",
            "external_system": "#008300",
        },
        text="#f0efec",
        muted="#c3c2b7",
        edge="#5f5e5a",
        edge_focus="#c3c2b7",
        refuted="#e66767",
        unverified="#eda100",
        highlight="#3987e5",
        node_stroke="#0e1117",
    ),
}

Position = tuple[float, float]


# ---------------------------------------------------------------- layouts


def ring_layout(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Position]:
    """Seed at the center, one ring per hop; each ring is ordered by its neighbors' angles,
    then grouped by entity type so similar nodes sit together."""
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
            placed = [angle[n] for n in adjacency[key] if n in angle and pos[n] != (0.0, 0.0)]
            if not placed:
                return -math.pi  # nodes attached only to the center: grouped by type below
            # Circular mean keeps neighbors on either side of +/-pi together.
            return math.atan2(sum(math.sin(a) for a in placed), sum(math.cos(a) for a in placed))

        ordered = sorted(
            ring,
            key=lambda k: (
                round(anchor(k), 2),
                NODE_TYPES.index(meta[k]["entity_type"])
                if meta[k]["entity_type"] in NODE_TYPES
                else 99,
                meta[k]["label"],
                k,
            ),
        )
        step = 1.0 if radius == 0 else RING_STEP
        radius = max(radius + step, len(ordered) * MIN_GAP / (2 * math.pi))
        start = math.pi / 2 if anchor(ordered[0]) == -math.pi else anchor(ordered[0])
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


# ---------------------------------------------------------------- visibility


def visible_edges(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    show_cross: bool,
    focus_node: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Hop-to-hop edges always; same-ring 'cross' edges only on request or at the focus node.

    Returns the visible edges and how many cross edges were hidden.
    """
    depth = {n["key"]: n["depth"] for n in nodes}
    shown, hidden = [], 0
    for e in edges:
        hop = abs(depth.get(e["source"], 0) - depth.get(e["target"], 0)) == 1
        if hop or show_cross or focus_node in (e["source"], e["target"]):
            shown.append(e)
        else:
            hidden += 1
    return shown, hidden


# ---------------------------------------------------------------- frames


MIN_HEIGHT = 280


def _bounds(pos: dict[str, Position], width: int = WIDTH) -> tuple[float, float, float, float, int]:
    """Data domain plus canvas height. Flat layouts (paths) get a shorter canvas instead of
    floating in empty space."""
    xs = [p[0] for p in pos.values()] or [0.0]
    ys = [p[1] for p in pos.values()] or [0.0]
    pad_x = max(0.9, (max(xs) - min(xs)) * 0.18)  # room for labels beside the outer ring
    pad_y = max(0.35, (max(ys) - min(ys)) * 0.1)
    x0, x1, y0, y1 = min(xs) - pad_x, max(xs) + pad_x, min(ys) - pad_y, max(ys) + pad_y
    min_height = MIN_HEIGHT if width >= WIDTH else MIN_HEIGHT // 2
    height = int(min(HEIGHT, max(min_height, (y1 - y0) / (x1 - x0) * width)))
    # Same units-per-pixel on both axes, so hop rings render as circles.
    units_per_px = max((x1 - x0) / width, (y1 - y0) / height)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    half_w, half_h = units_per_px * width / 2, units_per_px * height / 2
    return cx - half_w, cx + half_w, cy - half_h, cy + half_h, height


def _is_compact(width: int) -> bool:
    return width < WIDTH / 2


def _short(text: str, size: int = 24) -> str:
    return text if len(text) <= size else text[: size - 1] + "…"


CHAR_PX, LINE_PX, NODE_BOX_PX = 6.6, 15, 9


def _label_box(side: str, px: float, py: float, width: float) -> tuple[float, ...]:
    """Screen-space bounding box (left, top, right, bottom) of a label on one side."""
    half = LINE_PX / 2
    if side == "right":
        return px + LABEL_OFFSET_PX, py - half, px + LABEL_OFFSET_PX + width, py + half
    if side == "left":
        return px - LABEL_OFFSET_PX - width, py - half, px - LABEL_OFFSET_PX, py + half
    if side == "above":
        return px - width / 2, py - LABEL_OFFSET_PX - LINE_PX, px + width / 2, py - LABEL_OFFSET_PX
    return px - width / 2, py + LABEL_OFFSET_PX, px + width / 2, py + LABEL_OFFSET_PX + LINE_PX


def _overlaps(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def place_labels(
    rows: list[dict[str, Any]], radial: bool, keep: set[str], max_x: float | None = None
) -> dict[str, str | None]:
    """Greedy collision-free label placement in screen space.

    Higher-priority nodes (start, focus, inner rings, busier nodes) choose first. Each tries
    its natural side, then below / above / the opposite side; if every side collides the
    label is hidden (the tooltip still names the node). Nodes in `keep` always get a label.
    With `max_x`, a side that would run past the left or right canvas edge counts as a
    collision (narrow canvases have no spare room around the outer ring).
    """
    obstacles = [
        (r["px"] - NODE_BOX_PX, r["py"] - NODE_BOX_PX, r["px"] + NODE_BOX_PX, r["py"] + NODE_BOX_PX)
        for r in rows
    ]
    placed: list[tuple[float, ...]] = []
    sides: dict[str, str | None] = {}
    order = sorted(rows, key=lambda r: (r["key"] not in keep, r["depth"], -r["degree"], r["key"]))
    for r in order:
        width = len(r["short"]) * CHAR_PX
        if radial and (r["rx"] or r["ry"]):
            natural = "right" if r["rx"] > 0 else "left"
            if abs(r["rx"]) < 0.15 * math.hypot(r["rx"], r["ry"]):
                natural = "above" if r["ry"] > 0 else "below"
        else:
            natural = "below"
        candidates = [
            natural,
            "below",
            "above",
            {"right": "left", "left": "right"}.get(natural, "right"),
        ]
        own = (
            r["px"] - NODE_BOX_PX,
            r["py"] - NODE_BOX_PX,
            r["px"] + NODE_BOX_PX,
            r["py"] + NODE_BOX_PX,
        )
        chosen = None
        for side in dict.fromkeys(candidates):
            box = _label_box(side, r["px"], r["py"], width)
            if max_x is not None and (box[0] < 0 or box[2] > max_x):
                continue
            if not any(_overlaps(box, p) for p in placed) and not any(
                _overlaps(box, o) for o in obstacles if o != own
            ):
                chosen = side
                break
        if chosen is None and r["key"] in keep:
            chosen = natural
        if chosen:
            placed.append(_label_box(chosen, r["px"], r["py"], width))
        sides[r["key"]] = chosen
    return sides


def _validity(e: dict[str, Any]) -> str:
    if not e.get("valid_from") and not e.get("valid_to"):
        return "always"
    return f"{e.get('valid_from') or '…'} to {e.get('valid_to') or '…'}"


def build_frames(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    pos: dict[str, Position],
    highlight_edges: set[str],
    selected_node: str | None,
    theme: str = "light",
    radial_labels: bool = True,
    dim_unfocused: bool = True,
    width: int = WIDTH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    t = THEMES.get(theme, THEMES["light"])
    x0, x1, y0, y1, height = _bounds(pos, width)
    sx, sy = width / (x1 - x0), height / (y1 - y0)
    compact = _is_compact(width)
    labels = {n["key"]: n["label"] for n in nodes}

    # Focus: the selected node, or the endpoints of a selected edge.
    focus_edges: set[str] = set()
    focus_nodes: set[str] = set()
    if selected_node:
        focus_nodes.add(selected_node)
        for e in edges:
            if selected_node in (e["source"], e["target"]):
                focus_edges.add(e["id"])
                focus_nodes.update((e["source"], e["target"]))
    for e in edges:
        if e["id"] in highlight_edges:
            focus_edges.add(e["id"])
            focus_nodes.update((e["source"], e["target"]))
    focused = bool(focus_nodes) and dim_unfocused

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
        in_focus = e["id"] in focus_edges
        if e["id"] in highlight_edges:
            color, stroke = t.highlight, 3.0
        elif e["verified_status"] == "refuted":
            color, stroke = t.refuted, 1.6
        elif e["verified_status"] == "unverified":
            color, stroke = t.unverified, 1.6
        else:
            color, stroke = (t.edge_focus, 1.8) if in_focus and focused else (t.edge, 1.2)
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
                # Relation labels sit past the midpoint, away from the crowded inner ring.
                "lx": ax + (bx - ax) * 0.62 + nx_ * shift / sx,
                "ly": ay + (by - ay) * 0.62 + ny_ * shift / sy,
                "relation_type": e["relation_type"],
                "from": labels.get(e["source"], e["source"]),
                "to": labels.get(e["target"], e["target"]),
                "verified_status": e["verified_status"],
                "evidence": e["evidence"],
                "validity": _validity(e),
                "color": color,
                "width": stroke,
                "dashed": e["verified_status"] != "verified" and e["id"] not in highlight_edges,
                "alpha": 1.0 if (in_focus or not focused) else DIM_EDGE,
                "show_label": in_focus,
                "highlight": e["id"] in highlight_edges,
            }
        )

    seed = next((n["key"] for n in nodes if n["is_seed"]), None)
    center = pos.get(seed, (0.0, 0.0)) if seed else (0.0, 0.0)
    node_rows = []
    for n in nodes:
        if n["key"] not in pos:
            continue
        x, y = pos[n["key"]]
        in_focus = n["key"] in focus_nodes or not focused
        size = 560 if n["is_seed"] else 320 if n.get("is_expanded") else 190
        node_rows.append(
            {
                "key": n["key"],
                "x": x,
                "y": y,
                "label": n["label"],
                "description": n.get("description", n["label"]),
                # Incident IDs alone say nothing; show the start of the title as well
                # (except on a phone-width canvas, where the ID is all that fits).
                "short": _short(n["label"], 14)
                if compact
                else _short(n.get("description", n["label"]), 30)
                if n["entity_type"] == "incident"
                else _short(n["label"]),
                "entity_type": n["entity_type"],
                "depth": n["depth"],
                "size": size,
                "in_degree": n["in_degree"],
                "out_degree": n["out_degree"],
                "selected": n["key"] == selected_node,
                "alpha": 1.0 if in_focus else DIM_NODE,
                "label_color": t.text if (n["is_seed"] or n["key"] in focus_nodes) else t.muted,
                "label_weight": 700 if (n["is_seed"] or n["key"] == selected_node) else 400,
                "px": (x - x0) * sx,
                "py": (y1 - y) * sy,
                "rx": x - center[0],
                "ry": y - center[1],
                "degree": n["in_degree"] + n["out_degree"],
            }
        )
    keep = {n["key"] for n in nodes if n["is_seed"]} | focus_nodes
    sides = place_labels(node_rows, radial_labels, keep, max_x=width if compact else None)
    for row in node_rows:
        row["placement"] = sides[row["key"]] or "hidden"
    return pd.DataFrame(node_rows), pd.DataFrame(edge_rows)


# ---------------------------------------------------------------- chart


def build_chart(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    pos: dict[str, Position],
    highlight_edges: set[str] | None = None,
    selected_node: str | None = None,
    theme: str = "light",
    radial_labels: bool = True,
    dim_unfocused: bool = True,
    width: int = WIDTH,
) -> alt.LayerChart:
    t = THEMES.get(theme, THEMES["light"])
    node_df, edge_df = build_frames(
        nodes,
        edges,
        pos,
        highlight_edges or set(),
        selected_node,
        theme,
        radial_labels,
        dim_unfocused,
        width,
    )
    x0, x1, y0, y1, height = _bounds(pos, width)
    compact = _is_compact(width)

    def X(field: str) -> alt.X:  # noqa: N802 - mirrors alt.X
        return alt.X(f"{field}:Q", scale=alt.Scale(domain=[x0, x1]), axis=None)

    def Y(field: str) -> alt.Y:  # noqa: N802
        return alt.Y(f"{field}:Q", scale=alt.Scale(domain=[y0, y1]), axis=None)

    raw = None  # use the color values in the data as-is
    alpha = alt.Opacity("alpha:Q", scale=None, legend=None)
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
        for dashed, df in edge_df.groupby("dashed"):
            layers.append(
                alt.Chart(df)
                .mark_rule(strokeDash=[5, 4] if dashed else [1, 0])
                .encode(
                    x=X("x"),
                    y=Y("y"),
                    x2="x2:Q",
                    y2="y2:Q",
                    color=alt.Color("color:N", scale=raw, legend=None),
                    strokeWidth=alt.StrokeWidth("width:Q", scale=None, legend=None),
                    opacity=alpha,
                    tooltip=edge_tooltip,
                )
            )
        layers.append(
            alt.Chart(edge_df)
            .mark_point(shape="triangle-up", filled=True, size=75)
            .encode(
                x=X("ax"),
                y=Y("ay"),
                angle=alt.Angle("angle:Q", scale=alt.Scale(domain=[0, 360], range=[0, 360])),
                color=alt.Color("color:N", scale=raw, legend=None),
                opacity=alpha,
                tooltip=edge_tooltip,
            )
        )
        edge_pick = alt.selection_point(name=EDGE_SELECTION, fields=["edge_id"], on="click")
        layers.append(
            alt.Chart(edge_df)
            .mark_point(shape="diamond", filled=True, size=40)
            .encode(
                x=X("mx"),
                y=Y("my"),
                color=alt.Color("color:N", scale=raw, legend=None),
                opacity=alpha,
                tooltip=edge_tooltip,
            )
            .add_params(edge_pick)
        )
        labelled = edge_df[edge_df["show_label"]]
        if not labelled.empty:
            layers.append(
                alt.Chart(labelled)
                .mark_text(fontSize=10, dy=-9, fontWeight=500)
                .encode(
                    x=X("lx"),
                    y=Y("ly"),
                    text="relation_type:N",
                    color=alt.value(t.muted),
                )
            )
    if not node_df.empty:
        node_tooltip = [
            alt.Tooltip("description:N", title="name"),
            alt.Tooltip("key:N", title="id"),
            alt.Tooltip("entity_type:N", title="type"),
            alt.Tooltip("depth:Q", title="hops"),
            alt.Tooltip("in_degree:Q", title="incoming"),
            alt.Tooltip("out_degree:Q", title="outgoing"),
        ]
        types = [k for k in NODE_TYPES if k in set(node_df["entity_type"])]
        legend = alt.Legend(
            orient="bottom",
            direction="horizontal",
            title="Node type",
            symbolSize=120,
            labelFontSize=12,
            columns=3 if compact else 0,
        )
        color = alt.Color(
            "entity_type:N",
            legend=legend,
            scale=alt.Scale(domain=types, range=[t.nodes[k] for k in types]),
        )
        shape = alt.Shape(
            "entity_type:N",
            legend=legend,
            scale=alt.Scale(domain=types, range=[SHAPES[k] for k in types]),
        )
        selected = node_df[node_df["selected"]]
        if not selected.empty:
            layers.append(
                alt.Chart(selected)
                .mark_point(
                    shape="circle", size=1500, filled=False, strokeWidth=2.5, color=t.highlight
                )
                .encode(x=X("x"), y=Y("y"))
            )
        node_pick = alt.selection_point(name=NODE_SELECTION, fields=["key"], on="click")
        layers.append(
            alt.Chart(node_df)
            .mark_point(filled=True, stroke=t.node_stroke, strokeWidth=1.5)
            .encode(
                x=X("x"),
                y=Y("y"),
                color=color,
                shape=shape,
                opacity=alpha,
                size=alt.Size("size:Q", legend=None, scale=None),
                tooltip=node_tooltip,
            )
            .add_params(node_pick)
        )
        offsets = {
            "right": {"align": "left", "dx": LABEL_OFFSET_PX, "dy": 0, "baseline": "middle"},
            "left": {"align": "right", "dx": -LABEL_OFFSET_PX, "dy": 0, "baseline": "middle"},
            "above": {"align": "center", "dx": 0, "dy": -LABEL_OFFSET_PX, "baseline": "bottom"},
            "below": {"align": "center", "dx": 0, "dy": LABEL_OFFSET_PX, "baseline": "top"},
        }
        labelled = node_df[node_df["placement"] != "hidden"]
        for (placement, weight), df in labelled.groupby(["placement", "label_weight"]):
            layers.append(
                alt.Chart(df)
                .mark_text(fontSize=12, fontWeight=int(weight), **offsets[placement])
                .encode(
                    x=X("x"),
                    y=Y("y"),
                    text="short:N",
                    opacity=alpha,
                    color=alt.Color("label_color:N", scale=raw, legend=None),
                )
            )
    # Layers share scales by default; edge colors and node-type colors must not be merged.
    chart = (
        alt.layer(*layers)
        .resolve_scale(color="independent", shape="independent")
        .properties(width=width, height=height)
        .configure_view(strokeWidth=0)
    )
    if compact:
        # Streamlit's default "fit" autosize takes the legend's rows out of the plot height,
        # which flattens the rings on a short canvas; "pad" keeps the plot at width x height.
        chart = chart.properties(autosize=alt.AutoSizeParams(type="pad"))
    return chart


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
