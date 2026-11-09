"""Retrieval Playground: one question, what each strategy retrieved, and what it answered.

Evidence is always drawn above the answer, so retrieval mistakes can be told apart from
generation mistakes.
"""

from __future__ import annotations

import re
from typing import Any

import streamlit as st

from frontend.analysis.api import LabApiError
from frontend.analysis.rendering import snippet_html
from frontend.playground import api

QUESTION_KEY, EXAMPLE_KEY, RESULT_KEY = "pg_question", "pg_example", "pg_result"
SNIPPET_CHARS = 220
COSTLY_BY_DEFAULT = {"agent"}

# Colours are fixed rather than themed so the active tab stands out in light and dark mode.
TAB_STYLE = """
<style>
.st-key-strategy-tabs [role="tablist"] { gap: 0.25rem; }
.st-key-strategy-tabs [role="tab"] {
  padding: 0.4rem 1rem;
  border-radius: 0.5rem 0.5rem 0 0;
}
.st-key-strategy-tabs [role="tab"][aria-selected="true"] { background: #2a78d6; }
.st-key-strategy-tabs [role="tab"][aria-selected="true"],
.st-key-strategy-tabs [role="tab"][aria-selected="true"] * { color: #ffffff; }
.st-key-strategy-tabs [role="tab"] [class*="SelectionIndicator"] { background: #2a78d6; }
</style>
"""

_MARKDOWN_SPECIAL = re.compile(r"([\\`*_\[\]~$:])")


def escape_markdown(text: str) -> str:
    return _MARKDOWN_SPECIAL.sub(r"\\\1", text)


def answer_markdown(text: str) -> str:
    """Answers are model-written markdown; a bare `$` would otherwise start a LaTeX span."""
    return text.replace("$", r"\$")


def snippet(text: str, limit: int = SNIPPET_CHARS) -> str:
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def in_strategy_order(results: list[dict[str, Any]], order: list[str]) -> list[dict[str, Any]]:
    """Tabs follow the backend's first-to-last order, however the strategies were picked."""
    return sorted(results, key=lambda result: order.index(result["strategy"]))


def _use_example() -> None:
    picked = st.session_state.get(EXAMPLE_KEY)
    if picked is not None:
        st.session_state[QUESTION_KEY] = picked["question"]


def _controls(options: dict[str, Any], examples: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Returns the submitted request, or None until Run is pressed."""
    st.selectbox(
        "Example question",
        examples,
        index=None,
        key=EXAMPLE_KEY,
        placeholder="Pick a showcase question, or write your own below",
        format_func=lambda e: f"{e['id']} · {e['category']} · {e['question']}",
        on_change=_use_example,
    )
    st.text_area("Question", key=QUESTION_KEY, height=80)

    labels = {s["id"]: s["label"] for s in options["strategies"]}
    cols = st.columns([3, 2, 2, 3])
    strategies = cols[0].multiselect(
        "Strategies",
        list(labels),
        default=[s for s in labels if s not in COSTLY_BY_DEFAULT],
        format_func=labels.get,
        help="The agent makes several LLM calls per question, so it is off by default.",
    )
    top_k = cols[1].slider("Top-k", 1, options["max_top_k"], options["default_top_k"])
    indexes = [i["id"] for i in options["indexes"]]
    hop_limit = cols[2].slider(
        "Graph hops",
        1,
        options["max_hops"],
        options["default_hop_limit"],
        disabled="graph" not in strategies,
        help="Used by Graph. The agent chooses its own depth.",
    )
    index_profile = cols[3].selectbox("Index", indexes)

    with st.container(key="bar-playground"):
        bar = st.columns([1, 2, 3])
        submitted = bar[0].button("Run", type="primary", icon=":material/play_arrow:")
        generate = bar[1].toggle(
            "Generate answer",
            value=options["generation_available"],
            disabled=not options["generation_available"],
            help="Off stops after retrieval. The agent always uses the LLM.",
        )
    if not submitted:
        return None
    question = st.session_state.get(QUESTION_KEY, "").strip()
    if not question:
        st.warning("Write a question or pick an example first.")
        return None
    if not strategies:
        st.warning("Pick at least one strategy.")
        return None
    return {
        "strategies": strategies,
        "payload": {
            "question": question,
            "index_profile": index_profile,
            "top_k": top_k,
            "hop_limit": hop_limit,
            "generate": generate,
        },
    }


def _evidence_card(item: dict[str, Any]) -> None:
    with st.container(border=True):
        st.markdown(
            f"**#{item['rank']}** · score `{item['score']:.3f}` · "
            f"{escape_markdown(item['doc_type'])} · {(item['created_at'] or 'undated')[:10]}"
        )
        section = f" › {escape_markdown(item['section_path'])}" if item["section_path"] else ""
        st.markdown(f"**{escape_markdown(item['document_title'])}**{section}")
        st.html(snippet_html(snippet(item["text"])))
        if item["matched_terms"]:
            st.caption("Matched terms: " + ", ".join(item["matched_terms"]))
        if item["rank_details"]:
            ranks = ", ".join(f"{name} #{rank}" for name, rank in item["rank_details"].items())
            st.caption(f"Ranked by: {ranks}")
        if item["supports"]:
            st.caption("Backs: " + "; ".join(item["supports"]))
        with st.expander("Full chunk"):
            st.html(snippet_html(item["text"]))
            st.caption(f"Evidence id: {item['evidence_id']}")


def _answer(result: dict[str, Any]) -> None:
    answer = result["answer"]
    if result["answer_error"]:
        st.error(result["answer_error"], icon=":material/error:")
    if answer is None:
        return
    st.markdown("**Generated answer**")
    if answer["abstained"]:
        st.warning(answer["text"], icon=":material/help:")
    else:
        st.markdown(answer_markdown(answer["text"]))
    by_id = {e["evidence_id"]: e for e in result["evidence"]}
    cited = [f"#{by_id[c]['rank']} {by_id[c]['document_title']}" for c in answer["citations"]]
    if cited:
        st.caption("Cited: " + "; ".join(cited))
    st.caption(
        f"{answer['model'] or 'no model call'} · {answer['prompt_version']} · "
        f"{answer['context_sources']} sources in context"
    )


def _tool_trace(result: dict[str, Any]) -> None:
    trace = result["tool_trace"]
    stop = result["metadata"].get("stop_reason", "unknown")
    with st.expander(f"Tool trace · {len(trace)} calls · stopped: {stop}", expanded=True):
        for number, call in enumerate(trace, start=1):
            args = ", ".join(f"{key}={value}" for key, value in call["args"].items())
            st.markdown(f"**{number}. {call['tool']}** · {call['duration_ms']:.0f} ms")
            st.text(args)
            found = f"{len(call['evidence_ids'])} evidence items"
            st.caption(f"{escape_markdown(call['reason'])} ({found})")
            if call["message"]:
                st.warning(call["message"])


def _result(result: dict[str, Any], info: dict[str, Any]) -> None:
    st.caption(info["description"])
    if result["status"] != "ok":
        show = st.error if result["status"] == "error" else st.warning
        show(result["message"])
        return

    latency, usage = result["latency"], result["usage"]
    with st.container(key=f"grid2-{result['strategy']}"):
        cols = st.columns(3)
        cols[0].metric("Retrieval", f"{latency['retrieval_ms']:.0f} ms")
        generation = latency["generation_ms"]
        cols[1].metric("Answer", f"{generation:.0f} ms" if generation is not None else "–")
        cols[2].metric(
            "Tokens",
            usage["embedding_tokens"] + usage["prompt_tokens"] + usage["completion_tokens"],
            help=(
                f"Embedding {usage['embedding_tokens']}, prompt {usage['prompt_tokens']}, "
                f"completion {usage['completion_tokens']}"
            ),
        )

    if result["entities"]:
        named = ", ".join(f"{e['name']} ({e['entity_type']})" for e in result["entities"])
        st.caption(f"Started from: {named}")
    if result["tool_trace"]:
        _tool_trace(result)
    if result["graph_paths"]:
        st.markdown("**Graph paths**")
        for path in result["graph_paths"]:
            st.text("\n".join(path["steps"]))
    if result["tool_trace"]:
        st.markdown(f"**Evidence collected** · {len(result['evidence'])}, cited first")
    else:
        st.markdown(f"**Retrieved evidence** · top {result['top_k']}")
    if not result["evidence"]:
        st.info("No chunk matched this question.", icon=":material/search_off:")
    for item in result["evidence"]:
        _evidence_card(item)
    _answer(result)


def render() -> None:
    st.title("Retrieval Playground")
    st.caption("Ask one question and compare what each retrieval strategy finds.")
    try:
        options = api.options()
        examples = api.examples()
    except LabApiError as exc:
        st.error(str(exc))
        return
    if not options["indexes"]:
        st.warning(
            f"No index is built for {options['dataset_version']} yet. Run `make index`, "
            "then reload this page.",
            icon=":material/build:",
        )
        return

    request = _controls(options, examples)
    if request is not None:
        try:
            with st.spinner("Running retrieval"):
                st.session_state[RESULT_KEY] = {
                    "question": request["payload"]["question"],
                    "results": api.run(request["strategies"], request["payload"]),
                }
        except LabApiError as exc:
            st.error(str(exc))
            return

    run = st.session_state.get(RESULT_KEY)
    if run is None:
        return
    st.divider()
    st.markdown(f"**Results for:** {escape_markdown(run['question'])}")
    st.caption("Scores are on different scales, so compare ranks between strategies, not scores.")
    infos = {s["id"]: s for s in options["strategies"]}
    results = in_strategy_order(run["results"], list(infos))
    st.html(TAB_STYLE)
    with st.container(key="strategy-tabs"):
        tabs = st.tabs([infos[result["strategy"]]["label"] for result in results])
    for tab, result in zip(tabs, results, strict=True):
        with tab:
            _result(result, infos[result["strategy"]])
