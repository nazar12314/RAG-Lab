"""Chunkers split one document's text. They know nothing about storage or embeddings."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.M)
SEPARATORS = ("\n\n", "\n", ". ", " ")
PATH_JOINER = " > "


@dataclass(frozen=True)
class Chunk:
    """`text` is exactly content[span_start:span_end], so gold fact spans can be matched."""

    text: str
    span_start: int
    span_end: int
    section_path: str | None


class Chunker(Protocol):
    name: str
    config: dict[str, Any]

    def split(self, content: str) -> list[Chunk]: ...


@dataclass
class _Section:
    start: int
    end: int
    path: str | None


@dataclass
class SectionChunker:
    """One chunk per markdown section, packing oversized sections on paragraph boundaries.

    Very short sections join a neighbour: a title or an "Owner: X" line is useless alone.
    """

    max_chars: int = 800
    min_chars: int = 150
    name: str = field(default="section", init=False)

    @property
    def config(self) -> dict[str, Any]:
        return {"max_chars": self.max_chars, "min_chars": self.min_chars}

    def split(self, content: str) -> list[Chunk]:
        chunks = []
        for section in self._merge_short(self._sections(content)):
            for start, end in self._pack(self._pieces(content, section.start, section.end)):
                trimmed = _trim(content, start, end)
                if trimmed:
                    chunks.append(Chunk(content[trimmed[0] : trimmed[1]], *trimmed, section.path))
        return chunks

    def _sections(self, content: str) -> list[_Section]:
        headings = list(HEADING.finditer(content))
        sections = []
        if not headings or headings[0].start() > 0:
            sections.append(_Section(0, headings[0].start() if headings else len(content), None))
        stack: list[tuple[int, str]] = []
        for i, match in enumerate(headings):
            level = len(match.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            # The H1 repeats the document title, which is indexed separately.
            if level > 1:
                stack.append((level, match.group(2)))
            end = headings[i + 1].start() if i + 1 < len(headings) else len(content)
            path = PATH_JOINER.join(title for _, title in stack) or None
            sections.append(_Section(match.start(), end, path))
        return sections

    def _merge_short(self, sections: list[_Section]) -> list[_Section]:
        merged: list[_Section] = []
        for section in sections:
            previous = merged[-1] if merged else None
            if (
                previous is not None
                and min(previous.end - previous.start, section.end - section.start) < self.min_chars
                and section.end - previous.start <= self.max_chars
            ):
                previous.end = section.end
                previous.path = previous.path or section.path
            else:
                merged.append(_Section(section.start, section.end, section.path))
        return merged

    def _pieces(self, content: str, start: int, end: int, depth: int = 0) -> list[tuple[int, int]]:
        if end - start <= self.max_chars:
            return [(start, end)]
        if depth == len(SEPARATORS):
            return [(i, min(i + self.max_chars, end)) for i in range(start, end, self.max_chars)]
        separator = SEPARATORS[depth]
        pieces: list[tuple[int, int]] = []
        cursor = start
        while cursor < end:
            found = content.find(separator, cursor, end)
            # The separator stays with the left piece, so spans remain contiguous.
            stop = end if found == -1 else found + len(separator)
            pieces.extend(self._pieces(content, cursor, stop, depth + 1))
            cursor = stop
        return pieces

    def _pack(self, pieces: list[tuple[int, int]]) -> list[tuple[int, int]]:
        packed: list[tuple[int, int]] = []
        for start, end in pieces:
            if packed and end - packed[-1][0] <= self.max_chars:
                packed[-1] = (packed[-1][0], end)
            else:
                packed.append((start, end))
        return packed


def _trim(content: str, start: int, end: int) -> tuple[int, int] | None:
    while start < end and content[start].isspace():
        start += 1
    while end > start and content[end - 1].isspace():
        end -= 1
    return (start, end) if start < end else None


def indexed_text(title: str, section_path: str | None, text: str) -> str:
    """What both BM25 and embeddings see: a mid-document chunk often never names its subject."""
    heading = f"{title}{PATH_JOINER}{section_path}" if section_path else title
    return f"{heading}\n\n{text}"


CHUNKERS = {"section": SectionChunker}
