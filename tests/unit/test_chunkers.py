import json

import pytest

from backend.app.dataset.build import SEED_DIR
from backend.app.indexing.chunkers import SectionChunker, indexed_text


def seed_contents():
    lines = (SEED_DIR / "corpus" / "documents.jsonl").read_text().splitlines()
    return [json.loads(line)["content"] for line in lines if line]


@pytest.mark.parametrize("max_chars", [300, 800])
def test_chunks_are_exact_spans_covering_every_seed_document(max_chars):
    chunker = SectionChunker(max_chars=max_chars)
    for content in seed_contents():
        chunks = chunker.split(content)
        covered = set()
        previous_end = 0
        for chunk in chunks:
            assert chunk.text == content[chunk.span_start : chunk.span_end]
            assert len(chunk.text) <= max_chars
            assert chunk.span_start >= previous_end
            previous_end = chunk.span_end
            covered.update(range(chunk.span_start, chunk.span_end))
        assert all(i in covered for i, ch in enumerate(content) if not ch.isspace())


def test_section_path_follows_heading_nesting_without_the_title():
    long = "x" * 200
    content = f"# Title\n\n## Alerts\n\n{long}\n\n### Pool\n\n{long}\n\n## Signals\n\n{long}\n"
    assert [c.section_path for c in SectionChunker().split(content)] == [
        "Alerts",
        "Alerts > Pool",
        "Signals",
    ]


def test_short_preamble_joins_the_following_section():
    content = "# Title\n\nOwner: Payments\n\n## Alerts\n\n" + "y" * 300
    chunks = SectionChunker(max_chars=800, min_chars=150).split(content)
    assert len(chunks) == 1
    assert chunks[0].section_path == "Alerts"
    assert chunks[0].text.startswith("# Title")


def test_oversized_section_splits_on_paragraphs_first():
    first, second = "a" * 500, "b" * 500
    chunks = SectionChunker(max_chars=800).split(f"## S\n\n{first}\n\n{second}")
    assert len(chunks) == 2
    assert chunks[0].text.endswith(first)
    assert chunks[1].text == second
    assert {c.section_path for c in chunks} == {"S"}


def test_unbroken_text_is_hard_split_within_the_limit():
    chunks = SectionChunker(max_chars=100).split("z" * 250)
    assert [len(c.text) for c in chunks] == [100, 100, 50]


@pytest.mark.parametrize("content", ["", "  \n\n \t"])
def test_blank_documents_have_no_chunks(content):
    assert SectionChunker().split(content) == []


def test_indexed_text_carries_the_document_context():
    assert indexed_text("Runbook", "Alerts", "body") == "Runbook > Alerts\n\nbody"
    assert indexed_text("Runbook", None, "body") == "Runbook\n\nbody"
