"""HTTP client for the backend /analysis API, with short-lived Streamlit caching."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
CACHE_TTL_SECONDS = 30


class LabApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def _request(path: str, params: dict[str, Any]) -> httpx.Response:
    try:
        response = httpx.get(f"{BACKEND_URL}{path}", params=params, timeout=15)
    except httpx.HTTPError as exc:
        raise LabApiError(f"Backend not reachable at {BACKEND_URL} ({exc})") from exc
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise LabApiError(str(detail), response.status_code)
    return response


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _get_json(path: str, params_json: str) -> Any:
    return _request(path, json.loads(params_json)).json()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _get_text(path: str, params_json: str) -> str:
    return _request(path, json.loads(params_json)).text


def _clean(params: dict[str, Any]) -> str:
    kept = {k: v for k, v in params.items() if v not in (None, [], "")}
    return json.dumps(kept, sort_keys=True, default=str)


def get(path: str, **params: Any) -> Any:
    return _get_json(path, _clean(params))


def get_text(path: str, **params: Any) -> str:
    return _get_text(path, _clean(params))
