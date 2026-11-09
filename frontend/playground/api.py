"""HTTP client for the backend query API."""

from __future__ import annotations

from typing import Any

import httpx
import streamlit as st

from frontend.analysis.api import BACKEND_URL, LabApiError

CACHE_TTL_SECONDS = 30
TIMEOUT_SECONDS = 120


def _send(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    try:
        response = httpx.request(method, f"{BACKEND_URL}{path}", json=body, timeout=TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        raise LabApiError(f"Backend not reachable at {BACKEND_URL} ({exc})") from exc
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise LabApiError(str(detail), response.status_code)
    return response.json()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def options() -> dict[str, Any]:
    return _send("GET", "/query/options")


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def examples() -> list[dict[str, Any]]:
    return _send("GET", "/examples")


def run(strategy: str | None, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """One strategy, or every strategy on the same question when `strategy` is None."""
    if strategy is None:
        return _send("POST", "/query/compare", payload)["results"]
    return [_send("POST", "/query", {**payload, "strategy": strategy})]
