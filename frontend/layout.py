"""Phone support: compact-layout detection and the narrow-screen stylesheet.

Streamlit stacks every column below 640px. The stylesheet only adjusts that stacking inside
keyed containers (`st.container(key=...)` adds an `st-key-<key>` class):
- `grid2-*`: columns pair up two per row (metric tiles, fact lists);
- `bar-*`: toolbar rows; columns holding a button or toggle pair up, the rest stay full width.

Compact mode is decided server side (the canvas width and collapsed panels need it) from the
browser's User-Agent; `?layout=compact` or `?layout=wide` overrides it for the session.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

import streamlit as st

LAYOUT_PARAM, LAYOUT_KEY = "layout", "layout_mode"
MODES = ("compact", "wide")
PHONE_AGENT = re.compile(r"iPhone|iPod|Android.*Mobile|Mobile Safari|Windows Phone", re.I)

STYLE = """
<style>
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] {
    padding: 3.5rem 0.75rem 3rem 0.75rem;
  }
  h1 { font-size: 1.85rem !important; }
  [class*="st-key-grid2-"] [data-testid="stColumn"] {
    min-width: calc(50% - 0.5rem) !important;
  }
  [class*="st-key-bar-"] [data-testid="stColumn"]:has(
    [data-testid="stButton"], [data-testid="stDownloadButton"], [data-testid="stCheckbox"]
  ) {
    min-width: calc(50% - 0.5rem) !important;
  }
  [data-testid="stMetricValue"] { font-size: 1.6rem; }
  [data-testid="stVegaLiteChart"] { overflow-x: auto; }
  [data-testid="stButtonGroup"] button { max-width: 100%; height: auto; }
  [data-testid="stButtonGroup"] button div { white-space: normal; text-align: left; }
  .doc-source { max-height: 60vh; font-size: 0.82rem; padding: 0.5rem 0.6rem; }
}
</style>
"""


def is_phone_agent(user_agent: str) -> bool:
    return bool(PHONE_AGENT.search(user_agent or ""))


def resolve_mode(query: Mapping[str, str], remembered: str | None, user_agent: str) -> str:
    """Explicit query parameter, then the session's earlier choice, then the device."""
    requested = query.get(LAYOUT_PARAM)
    if requested in MODES:
        return requested
    if remembered in MODES:
        return remembered
    return "compact" if is_phone_agent(user_agent) else "wide"


def setup() -> None:
    """Once per run from the entry point: settle the mode and inject the stylesheet."""
    try:
        agent = st.context.headers.get("User-Agent", "")
    except AttributeError:
        agent = ""
    st.session_state[LAYOUT_KEY] = resolve_mode(
        st.query_params, st.session_state.get(LAYOUT_KEY), agent
    )
    st.html(STYLE)


def is_compact() -> bool:
    return st.session_state.get(LAYOUT_KEY) == "compact"


def panel(label: str, key: str, border: bool = False) -> st.delta_generator.DeltaGenerator:
    """A collapsed expander on phones (so controls do not push content off-screen), a plain
    container otherwise. The key keeps the expander open while its label changes."""
    if is_compact():
        return st.expander(label, key=key)
    return st.container(border=border)
