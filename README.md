# RAG-Lab

GraphRAG Lab — an interactive workspace for comparing retrieval strategies (exact SQL, PostgreSQL FTS, pgvector, graph traversal, hybrid, and a LangChain agent) over one shared engineering-operations corpus.

## Stack

- **Backend:** FastAPI
- **Frontend:** Streamlit
- **Database:** PostgreSQL 17 + pgvector (structured records, graph tables, FTS, embeddings)
- **DB access / migrations:** SQLAlchemy + psycopg, Alembic
- **Agent / LLM:** LangChain + langchain-openai
- **Tooling:** uv, ruff, pytest, Docker Compose

## Project structure

```txt
backend/app/
  main.py          # FastAPI app and dependency wiring
  config.py        # settings from environment
  api/             # HTTP routes
  models/          # request / evidence / result contracts
  services/        # query, comparison, indexing, evaluation
  retrieval/       # retriever strategies + registry
  indexing/        # pipeline, chunkers, extraction, index manifest
  storage/         # PostgreSQL access (only place with raw SQL)
  agent/           # LangChain tools and runner
  generation/      # answer generation
  evaluation/      # benchmark runner and metrics
frontend/          # Streamlit app
data/seed/         # synthetic company data
data/benchmark/    # benchmark questions and labels
migrations/        # Alembic migrations
tests/             # unit, integration, contract
docker/            # container init scripts
```

## Setup

Requirements: [uv](https://docs.astral.sh/uv/), Docker with Compose.

```bash
cp .env.example .env      # add OPENAI_API_KEY
make install              # create .venv with all dependencies
```

### Run with Docker

```bash
make up                   # db + backend + frontend
make migrate              # apply migrations
```

- API: http://localhost:8000 (docs at `/docs`)
- UI: http://localhost:8501

Host ports are configurable via `POSTGRES_PORT`, `BACKEND_PORT`, `FRONTEND_PORT` in `.env` (keep `DATABASE_URL` in sync with `POSTGRES_PORT`).

### Run locally

```bash
make db                   # only PostgreSQL in Docker
make migrate
make backend              # in one terminal
make frontend             # in another
```

## Development

```bash
make test                 # unit tests
make test-integration     # tests against running PostgreSQL
make lint                 # ruff check + format check
make format               # auto-format
make revision m="message" # new Alembic migration
```
