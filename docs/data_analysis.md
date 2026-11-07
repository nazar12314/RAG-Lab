# Data Analysis module

A read-only workspace for inspecting the corpus before experimenting with retrieval. It
implements phases DA-1 (**Overview**, **Records & Documents**) and DA-2 (**Graph Explorer**) of
the Data Analysis spec. Data Quality / graph statistics (DA-3) build on the same API.

No OpenAI key, embeddings or index are needed.

## Using it

```bash
make db && make migrate && make seed
make backend      # FastAPI on :8000
make frontend     # Streamlit on :8501 -> "Data Analysis" in the top navigation
```

- **Shared controls**: dataset version, graph source (curated / extracted), index profile, and
  filters for service, document type, severity, entity type, relation type, date range and
  free-text search. "Clear filters" resets everything.
- **Overview**: summary cards, computed observations (each with "Show records"), and nine
  charts. Clicking a bar, cell or histogram bin sets the matching filter and opens those
  records below; dragging on the incident timeline selects a time window. Charts ignore their
  own dimension when cross-filtering, so the other values stay visible (dimmed).
- **Records & Documents**: documents, incidents, services, deployments, dependencies, graph
  entities and relations, sortable, paginated, exportable to CSV/JSON. Selecting a row opens
  its detail panel: attributes, connected records (click to navigate, with a Back trail), and
  the document passages that support its graph edges.
- **Document inspector**: metadata, the services it is linked to and why, the graph edges it
  supports (select one to highlight its passage), and the full text as escaped source with
  evidence highlights, rendered markdown, or raw text.
- **Stable links**: `?record=<type>/<id>` opens any record, e.g.
  `/data_analysis?record=incidents/INC-104`; `?node=<key>` opens the Graph Explorer there.

The browser search is for locating records; it is deliberately not one of the benchmarked
retrieval methods.

## Graph Explorer

Local exploration of the selected graph version instead of a whole-graph hairball.

- **Find a node** by ID, name or alias (`payment-service` resolves to Payments API). *Start
  here* makes it the center; *Path to* sets it as a path target.
- **Traversal controls**: 1-3 hops, direction (both / outgoing / incoming), relation types,
  "only edges valid on" a date (historical dependencies drop out), show/hide refuted edges, and
  a node cap (default 100). Every response states its projection, e.g. "1-hop neighborhood of
  SVC-CHECKOUT-API over DEPENDS_ON, AFFECTED_BY, following edges outgoing only".
- **Canvas**: the start node in the center, one ring per hop, nodes grouped by type around
  each ring. Node color and shape show the entity type; arrowheads show the stored direction;
  grey = verified, dashed red = refuted, dashed orange = unverified, thick blue = selected edge
  or path. Colors follow the active Streamlit theme (light or dark palette).
- **Readability**: only edges leading one hop further out are drawn by default; links between
  nodes on the same ring are counted and hidden behind *Show links between neighbors*.
  Clicking a node puts it in focus: its links (including hidden ones) and neighbors stay in
  front with relation labels, the rest fades. Labels sit outside the ring and are placed to
  avoid collisions; a label with no free space is hidden (hover the node for its full name).
  Incident nodes show the start of their title, not just the ID.
- **Click a node** to see its type, aliases, incoming/outgoing degree, connected records and
  source record, with actions *Expand neighbors*, *Make start node* and *Path from start*.
  Expansions form a breadcrumb trail with *Undo expand* and *Reset*.
- **Click an edge** (its ◆ midpoint) to see relation type, direction, validity, verification
  status and the supporting passages or records; *Open in document* jumps to the exact
  sentence. Edges without a source say "No supporting source available."
- **Path mode**: up to five shortest connections between the start node and a target, drawn
  left to right and listed as `A —REL→ B ←REL— C`. By default direction is ignored and refuted
  edges are excluded; edges walked against their arrow keep their stored direction. A shortest
  connection is not proof of causality.
- **Safeguards**: the node and edge caps report how many nodes were reachable and suggest
  narrowing the filters; layouts are deterministic; a table view and JSON export are always
  available.
- **Examples**: *Checkout → INC-104* loads the spec's demo story (Checkout API depends on
  Payments API, affected by INC-104, triggered by v2.8.0) with the triggering edge and its
  postmortem passage selected; *shortest path* shows two 2-hop connections from Checkout API to
  that deployment.

Rendering uses NetworkX for traversal and Altair for the canvas (both native to the stack), so
node and edge clicks use Streamlit's built-in selection events. The third-party graph widgets
suggested in the spec (st-graph-workbench 0.1.0, one release; streamlit-sigmajs 0.3.0) were
reviewed and not adopted for now; the backend's `GraphView` is widget-independent, so one can
be swapped in later without API changes.

## Phone layout

Phones get a compact layout, chosen from the browser's User-Agent (`frontend/layout.py`):
dataset, filter and traversal controls fold into collapsed expanders (the filter header shows
how many are active), metric tiles and document facts sit two per row, toolbar buttons pair
up, and the graph canvas is drawn 320px wide with ID-only labels that never leave the canvas.
Append `?layout=compact` or `?layout=wide` to the URL to force either layout for the session.
Desktop rendering is unchanged.

## Architecture

```txt
frontend/screens/data_analysis.py  ->  frontend/analysis/*   (presentation only, HTTP client)
            |
            v
backend/app/api/analysis.py        /analysis/* read-only endpoints
            |
backend/app/services/analysis_service.py   resolves dataset/graph/index, caches snapshots
            |
backend/app/analysis/              snapshot, filters, overview charts, detail panels
            |
backend/app/storage/analysis.py    SQL over corpus/search/graph schemas only
```

The service builds one in-memory snapshot per (dataset, graph) and invalidates it when the
dataset is reseeded (`loaded_at` changes). The corpus is small, so filtering and
distributions run on the snapshot instead of issuing dozens of SQL queries per page view.

The module never reads the `eval` schema: it shows what retrievers can see, not the gold
labels.

| Endpoint | Purpose |
| --- | --- |
| `GET /analysis/datasets` | loaded dataset versions with their graph versions and index profiles |
| `GET /analysis/facets` | filter options with counts |
| `GET /analysis/overview` | cards, chart specs (with drill-down contract) and observations |
| `GET /analysis/records` | filtered, sorted, paginated records (max 200 per page) |
| `GET /analysis/records/{type}/{id}` | record detail, links and supporting passages |
| `GET /analysis/documents/{id}` | full document, evidence highlights, chunks when indexed |
| `GET /analysis/export` | filtered CSV or JSON (up to 10,000 rows) |
| `GET /analysis/graph/search` | nodes matching an ID, name or alias, ranked |
| `GET /analysis/graph/neighborhood` | bounded 1-3 hop subgraph with projection and truncation |
| `GET /analysis/graph/path` | up to 10 shortest connections, edges in stored direction |

All endpoints take `dataset` and optional `graph`; an index profile or graph that does not
belong to the dataset is rejected with HTTP 400. Record pages report which filters were
applied and which do not apply to that record type.

## How documents are linked to services

A document counts for a service when any of these hold, and the UI shows which:

1. the service is listed in the document metadata;
2. the document is about an incident that affected the service, or lists its deployment;
3. the text mentions an incident or deployment ID of that service;
4. the document supports a graph edge that touches the service.

## Safety

Read-only endpoints, no arbitrary SQL. Document text is treated as untrusted: it is
HTML-escaped before evidence highlights are added, and markdown is rendered without HTML.
