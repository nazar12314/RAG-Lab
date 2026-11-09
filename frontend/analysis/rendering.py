"""Safe HTML rendering of untrusted source text with evidence highlights.

Document text is data, never markup: every character is HTML-escaped before it is wrapped
in highlight elements, so embedded HTML or scripts are displayed, not executed.
"""

from __future__ import annotations

import html
from typing import Any

STYLE = """
<style>
.doc-source { white-space: pre-wrap; line-height: 1.55; font-size: 0.92rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; padding: 0.75rem 1rem;
  border: 1px solid rgba(128,128,128,0.25); border-radius: 0.5rem; max-height: 640px;
  overflow-y: auto; }
.doc-source mark.ev { background: rgba(42,120,214,0.16); color: inherit;
  border-bottom: 2px solid #2a78d6; border-radius: 2px; padding: 0 1px; }
.doc-source mark.ev.refuted { border-bottom-style: dashed; background: rgba(208,59,59,0.12);
  border-bottom-color: #d03b3b; }
.doc-source mark.ev.focus { background: rgba(250,178,25,0.45); border-bottom-color: #c98500; }
.ev-legend { font-size: 0.8rem; opacity: 0.85; margin: 0.25rem 0 0.5rem 0; }
.ev-legend span { padding: 0 4px; margin-right: 10px; border-radius: 2px; }
blockquote.snippet { white-space: pre-wrap; margin: 0.25rem 0 0.5rem 0; padding: 0.4rem 0.8rem;
  border-left: 3px solid #2a78d6; background: rgba(42,120,214,0.06); font-size: 0.9rem; }
</style>
"""

LEGEND = (
    '<div class="ev-legend">'
    '<span style="background: rgba(42,120,214,0.16); border-bottom: 2px solid #2a78d6">'
    "supports a graph edge</span>"
    '<span style="background: rgba(208,59,59,0.12); border-bottom: 2px dashed #d03b3b">'
    "supports a refuted edge</span>"
    '<span style="background: rgba(250,178,25,0.45)">selected passage</span>'
    "</div>"
)


def highlight_html(
    content: str, highlights: list[dict[str, Any]], focus: tuple[int, int] | None = None
) -> str:
    """Escaped document text; overlapping spans are merged into segments with combined titles."""
    bounds = {0, len(content)}
    for h in highlights:
        bounds.update((h["span_start"], h["span_end"]))
    if focus:
        bounds.update(focus)
    points = sorted(b for b in bounds if 0 <= b <= len(content))
    parts = []
    for start, end in zip(points, points[1:], strict=False):
        segment = html.escape(content[start:end])
        covering = [h for h in highlights if h["span_start"] <= start and end <= h["span_end"]]
        focused = bool(focus and focus[0] <= start and end <= focus[1])
        if not covering and not focused:
            parts.append(segment)
            continue
        classes = ["ev"]
        if covering and all(h["verified_status"] == "refuted" for h in covering):
            classes.append("refuted")
        if focused:
            classes.append("focus")
        title = "; ".join(
            f"{h['source']['label']} --{h['relation_type']}--> {h['target']['label']}"
            for h in covering
        )
        parts.append(
            f'<mark class="{" ".join(classes)}" title="{html.escape(title, quote=True)}">'
            f"{segment}</mark>"
        )
    return f'{STYLE}{LEGEND}<div class="doc-source">{"".join(parts)}</div>'


def snippet_html(text: str) -> str:
    return f'{STYLE}<blockquote class="snippet">{html.escape(text)}</blockquote>'
