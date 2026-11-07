# Data Analysis module

A read-only workspace for inspecting the corpus before experimenting with retrieval. It
implements phase DA-1 of the Data Analysis spec: **Overview** and **Records & Documents**.
Graph Explorer (DA-2) and Data Quality / graph statistics (DA-3) build on the same API.

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
  `/data_analysis?record=incidents/INC-104`.

The browser search is for locating records; it is deliberately not one of the benchmarked
retrieval methods.

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
