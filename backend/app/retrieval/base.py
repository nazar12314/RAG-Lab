"""The contract every retrieval strategy implements."""

from __future__ import annotations

from typing import Protocol

from backend.app.models.contracts import RetrievalRequest, RetrievalResult


class Unsupported(Exception):
    """The strategy cannot run in this configuration; reported instead of falling back."""


class ProviderError(Exception):
    """A model provider call failed. The message is safe to show in the UI."""


class Retriever(Protocol):
    label: str
    description: str

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult: ...
