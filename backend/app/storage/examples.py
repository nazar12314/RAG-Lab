"""Showcase questions for the playground."""

from __future__ import annotations

from sqlalchemy import Engine, select

from backend.app.models.contracts import ExampleQuestion
from backend.app.storage.tables.eval import Question


class PostgresExampleStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def showcase(self) -> list[ExampleQuestion]:
        # Selected column by column: reference answers and evidence must not reach the UI.
        query = (
            select(Question.id, Question.category, Question.question)
            .where(Question.split == "showcase")
            .order_by(Question.id)
        )
        with self.engine.connect() as conn:
            return [ExampleQuestion(**row._mapping) for row in conn.execute(query)]
