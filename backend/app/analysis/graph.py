"""Graph traversal over one graph version: node search, bounded neighborhoods, paths.

Built once per snapshot with NetworkX. Traversals are deterministic (neighbors are visited in
(relation_type, key) order) so the same request always returns the same subgraph.
"""

from __future__ import annotations

from collections import deque
from datetime import date, datetime
from itertools import islice
from typing import Any

import networkx as nx

from backend.app.analysis.details import NotFound, link, record_type_of
from backend.app.analysis.snapshot import Snapshot
from backend.app.models.analysis import (
    DatasetRef,
    GraphEdge,
    GraphNode,
    GraphPath,
    GraphProjection,
    GraphView,
    NodeMatch,
    PathResult,
    PathStep,
    RecordType,
    TraversalFilter,
)

MAX_DEPTH = 3
DEFAULT_MAX_NODES = 100
DEFAULT_MAX_EDGES = 250


def _date(value: Any) -> date | None:
    return value if isinstance(value, date) else None


class GraphIndex:
    def __init__(self, s: Snapshot) -> None:
        self.s = s
        self.g = nx.MultiDiGraph()
        for e in s.entities.itertuples():
            self.g.add_node(e.key, entity_type=e.entity_type, label=e.canonical_name)
        self.edges: dict[str, GraphEdge] = {}
        for r in s.relations.sort_values("id").itertuples():
            edge = GraphEdge(
                id=r.id,
                source=r.source_key,
                target=r.target_key,
                relation_type=r.relation_type,
                verified_status=r.verified_status,
                confidence=float(r.confidence),
                valid_from=_date(r.valid_from),
                valid_to=_date(r.valid_to),
                doc_evidence=int(r.doc_evidence),
                record_evidence=int(r.record_evidence),
                evidence=r.evidence,
            )
            self.edges[r.id] = edge
            self.g.add_edge(r.source_key, r.target_key, key=r.id)

    # ------------------------------------------------------------ helpers

    def _require(self, key: str) -> None:
        if key not in self.g:
            raise NotFound(f"graph node {key}")

    @staticmethod
    def allows(edge: GraphEdge, f: TraversalFilter) -> bool:
        if f.relation_types and edge.relation_type not in f.relation_types:
            return False
        if not f.include_refuted and edge.verified_status == "refuted":
            return False
        if f.as_of:
            if edge.valid_from and edge.valid_from > f.as_of:
                return False
            if edge.valid_to and f.as_of >= edge.valid_to:
                return False
        return True

    def _steps(self, key: str, f: TraversalFilter, direction: str) -> list[tuple[str, GraphEdge]]:
        """(neighbor, edge) pairs leaving `key` in the requested direction, sorted."""
        out: list[tuple[str, GraphEdge]] = []
        if direction in ("both", "out"):
            out += [(v, self.edges[k]) for _, v, k in self.g.out_edges(key, keys=True)]
        if direction in ("both", "in"):
            out += [(u, self.edges[k]) for u, _, k in self.g.in_edges(key, keys=True)]
        out = [(n, e) for n, e in out if self.allows(e, f)]
        return sorted(out, key=lambda ne: (ne[1].relation_type, ne[0], ne[1].id))

    def node(self, key: str, depth: int, seed: str, expanded: set[str]) -> GraphNode:
        data = self.g.nodes[key]
        rt = record_type_of(key)
        record = None if rt is RecordType.entities else link(self.s, key)
        return GraphNode(
            key=key,
            label=data["label"],
            entity_type=data["entity_type"],
            depth=depth,
            in_degree=self.g.in_degree(key),
            out_degree=self.g.out_degree(key),
            is_seed=key == seed,
            is_expanded=key in expanded,
            record=record,
        )

    # ------------------------------------------------------------ search

    def search(self, query: str, limit: int = 20) -> list[NodeMatch]:
        q = query.strip().lower()
        if not q:
            return []
        ranked: dict[str, tuple[int, str, str]] = {}

        def offer(key: str, rank: int, how: str, text: str) -> None:
            if key not in ranked or rank < ranked[key][0]:
                ranked[key] = (rank, how, text)

        for key, data in self.g.nodes(data=True):
            if key.lower() == q:
                offer(key, 0, "id", key)
            elif q in key.lower():
                offer(key, 4, "id", key)
            name = data["label"]
            if name.lower() == q:
                offer(key, 1, "name", name)
            elif q in name.lower():
                offer(key, 3 if name.lower().startswith(q) else 5, "name", name)
            for alias in self.s.aliases.get(key, []):
                if alias.lower() == q:
                    offer(key, 2, "alias", alias)
                elif q in alias.lower():
                    offer(key, 6, "alias", alias)
        order = sorted(ranked, key=lambda k: (ranked[k][0], -self.g.degree(k), k))
        return [
            NodeMatch(
                key=k,
                label=self.g.nodes[k]["label"],
                entity_type=self.g.nodes[k]["entity_type"],
                matched_on=ranked[k][1],  # type: ignore[arg-type]
                matched_text=ranked[k][2],
                degree=self.g.degree(k),
            )
            for k in order[:limit]
        ]

    # ------------------------------------------------------------ neighborhood

    def neighborhood(
        self,
        ref: DatasetRef,
        seed: str,
        depth: int,
        f: TraversalFilter,
        expand: list[str] | None = None,
        max_nodes: int = DEFAULT_MAX_NODES,
        max_edges: int = DEFAULT_MAX_EDGES,
    ) -> GraphView:
        self._require(seed)
        depth = max(1, min(depth, MAX_DEPTH))
        expanded = [k for k in dict.fromkeys(expand or []) if k in self.g and k != seed]

        # Breadth-first from the seed: discovery order = (hop distance, sorted neighbors).
        dist: dict[str, int] = {seed: 0}
        order = [seed]
        queue = deque([seed])
        while queue:
            key = queue.popleft()
            if dist[key] >= depth:
                continue
            for neighbor, _ in self._steps(key, f, f.direction):
                if neighbor not in dist:
                    dist[neighbor] = dist[key] + 1
                    order.append(neighbor)
                    queue.append(neighbor)
        # On-demand expansion: one more hop around each expanded node.
        for key in expanded:
            if key not in dist:
                dist[key] = depth + 1
                order.append(key)
            for neighbor, _ in self._steps(key, f, f.direction):
                if neighbor not in dist:
                    dist[neighbor] = dist[key] + 1
                    order.append(neighbor)

        reachable = len(order)
        protected = {seed, *expanded}
        position = {k: i for i, k in enumerate(order)}
        ranked = sorted(order, key=lambda k: (k not in protected, dist[k], position[k]))
        kept = set(ranked[:max_nodes])

        edges = [
            self.edges[k]
            for u, v, k in self.g.edges(kept, keys=True)
            if u in kept and v in kept and self.allows(self.edges[k], f)
        ]
        edges = sorted(
            {e.id: e for e in edges}.values(),
            key=lambda e: (min(dist[e.source], dist[e.target]), e.relation_type, e.id),
        )
        reasons = []
        if reachable > len(kept):
            reasons.append(
                f"{reachable} nodes are reachable; showing the closest {len(kept)}. "
                "Reduce the depth or select fewer relation types."
            )
        if len(edges) > max_edges:
            reasons.append(f"{len(edges)} edges; showing the first {max_edges}.")
            edges = edges[:max_edges]

        types = ", ".join(f.relation_types) if f.relation_types else "all relation types"
        arrows = {"both": "in both directions", "out": "outgoing only", "in": "incoming only"}
        description = (
            f"{depth}-hop neighborhood of {seed} over {types}, following edges "
            f"{arrows[f.direction]}"
            + (f", valid on {f.as_of}" if f.as_of else "")
            + ("" if f.include_refuted else ", excluding refuted edges")
            + f". Graph: {self.s.graph['id']} ({self.s.graph['kind']})."
        )
        return GraphView(
            ref=ref,
            projection=GraphProjection(
                graph=self.s.graph["id"],
                graph_kind=self.s.graph["kind"],
                filter=f,
                depth=depth,
                max_nodes=max_nodes,
                max_edges=max_edges,
                description=description,
            ),
            seed=seed,
            expanded=expanded,
            nodes=[self.node(k, dist[k], seed, set(expanded)) for k in ranked if k in kept],
            edges=edges,
            reachable_nodes=reachable,
            truncated=bool(reasons),
            truncation_reason=" ".join(reasons) or None,
            computed_at=datetime.now().astimezone(),
        )

    # ------------------------------------------------------------ paths

    def paths(
        self,
        ref: DatasetRef,
        source: str,
        target: str,
        f: TraversalFilter,
        directed: bool,
        limit: int = 5,
    ) -> PathResult:
        self._require(source)
        self._require(target)
        allowed = nx.DiGraph()
        allowed.add_nodes_from(self.g.nodes)
        for u, v, k in self.g.edges(keys=True):
            if self.allows(self.edges[k], f):
                allowed.add_edge(u, v)
        search_graph = allowed if directed else allowed.to_undirected(as_view=True)

        try:
            found = list(islice(nx.all_shortest_paths(search_graph, source, target), limit))
        except nx.NetworkXNoPath:
            found = []

        paths = []
        for node_path in found:
            steps = []
            for a, b in zip(node_path, node_path[1:], strict=False):
                candidates = [self.edges[k] for k in (self.g.get_edge_data(a, b) or {})]
                if not directed:
                    candidates += [self.edges[k] for k in (self.g.get_edge_data(b, a) or {})]
                hop = sorted(
                    (e for e in candidates if self.allows(e, f)),
                    key=lambda e: (e.source != a, e.relation_type, e.id),
                )
                steps.append(PathStep(from_key=a, to_key=b, edges=hop))
            paths.append(GraphPath(nodes=node_path, steps=steps))

        hop_of: dict[str, int] = {source: 0}
        for p in paths:
            for i, k in enumerate(p.nodes):
                hop_of[k] = min(hop_of.get(k, i), i)
        if not paths:
            hop_of[target] = 1
        hops = len(paths[0].steps) if paths else None
        if paths:
            message = (
                f"Shortest connection: {hops} hop(s); {len(paths)} path(s) of that length shown"
                + ("" if directed else ", ignoring edge direction")
                + ". A connection in the stored graph is not proof of causality."
            )
        else:
            message = "No connection with the selected relation types" + (
                " following edge direction." if directed else "."
            )
        return PathResult(
            ref=ref,
            source=source,
            target=target,
            directed=directed,
            filter=f,
            length=hops,
            paths=paths,
            nodes=[self.node(k, hop, source, set()) for k, hop in hop_of.items()],
            message=message,
        )


def graph_index(s: Snapshot) -> GraphIndex:
    """Lazily built once per snapshot."""
    if s.graph_index is None:
        s.graph_index = GraphIndex(s)
    return s.graph_index
