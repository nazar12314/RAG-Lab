.PHONY: install up down logs db migrate revision dataset dataset-check seed index backend frontend test test-integration lint format

install:
	uv sync --all-extras

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

db:
	docker compose up -d db

migrate:
	uv run alembic upgrade head

revision:
	uv run alembic revision --autogenerate -m "$(m)"

dataset:
	uv run python -m backend.app.dataset.build

dataset-check:
	uv run python -m backend.app.dataset.build --check

seed:
	uv run python -m backend.app.dataset.load

index:
	uv run python -m backend.app.indexing.pipeline

backend:
	uv run uvicorn backend.app.main:app --reload

frontend:
	uv run streamlit run frontend/app.py

test:
	uv run pytest -m "not integration"

test-integration:
	uv run pytest -m integration

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .
