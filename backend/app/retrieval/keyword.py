"""Okapi BM25 over the chunks of an index profile.

A real BM25, computed here because PostgreSQL's ts_rank is a different formula: it has no
inverse document frequency, which is the part that lets a rare token like INC-104 dominate.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Protocol

import snowballstemmer

from backend.app.indexing.chunkers import indexed_text
from backend.app.models.contracts import Evidence, RetrievalRequest, RetrievalResult
from backend.app.storage.search import StoredChunk

K1 = 1.5
B = 0.75

_WORD = re.compile(r"[^\W_]+(?:[-_.][^\W_]+)*")
_JOINERS = re.compile(r"[-_.]")
_STOPWORD_LIST = """
a about after all also am an and any are as at be been before but by can could did do does for
from had has have how i if in into is it its may me my no not of on or our should so than that
the their them then there these they this to was we were what when where which who whom why
will with would you your
"""
_STOPWORDS = frozenset(_STOPWORD_LIST.split())
_stemmer = snowballstemmer.stemmer("english")
# The stemmer instance holds per-call state and requests arrive on a thread pool.
_stemmer_lock = Lock()


def _stem(word: str) -> str:
    with _stemmer_lock:
        return _stemmer.stemWord(word)


def tokenize(text: str) -> list[str]:
    """Stemmed terms. Identifiers such as INC-104 stay whole and also yield their parts."""
    terms: list[str] = []
    for word in _WORD.findall(text.casefold()):
        parts = _JOINERS.split(word)
        if len(parts) > 1:
            terms.append(word)
        terms.extend(_stem(p) for p in parts if p not in _STOPWORDS)
    return terms


@dataclass(frozen=True)
class Hit:
    position: int
    score: float
    matched_terms: list[str]


class BM25Index:
    def __init__(self, documents: list[list[str]], k1: float = K1, b: float = B) -> None:
        self.k1 = k1
        self.b = b
        self.lengths = [len(terms) for terms in documents]
        self.average_length = sum(self.lengths) / len(documents) if documents else 0.0
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for position, terms in enumerate(documents):
            for term, frequency in Counter(terms).items():
                self.postings[term].append((position, frequency))

    def idf(self, term: str) -> float:
        total = len(self.lengths)
        containing = len(self.postings.get(term, ()))
        # The +1 keeps very common terms from scoring negative.
        return math.log(1 + (total - containing + 0.5) / (containing + 0.5))

    def search(self, query_terms: list[str], top_k: int) -> list[Hit]:
        contributions: dict[int, dict[str, float]] = defaultdict(dict)
        for term in dict.fromkeys(query_terms):
            idf = self.idf(term)
            for position, frequency in self.postings.get(term, ()):
                relative_length = self.lengths[position] / self.average_length
                norm = self.k1 * (1 - self.b + self.b * relative_length)
                contributions[position][term] = idf * frequency * (self.k1 + 1) / (frequency + norm)
        ranked = sorted(contributions.items(), key=lambda item: (-sum(item[1].values()), item[0]))
        return [
            Hit(position, sum(terms.values()), sorted(terms, key=lambda t: -terms[t]))
            for position, terms in ranked[:top_k]
        ]


class ChunkSource(Protocol):
    def chunks(self, profile_id: str) -> list[StoredChunk]: ...


class BM25Retriever:
    label = "BM25"
    description = "Ranks chunks by shared keywords, weighting rare terms such as IDs most."

    def __init__(self, store: ChunkSource) -> None:
        self.store = store
        self._cache: dict[str, tuple[datetime | None, list[StoredChunk], BM25Index]] = {}
        self._lock = Lock()

    def _load(
        self, profile_id: str, built_at: datetime | None
    ) -> tuple[list[StoredChunk], BM25Index]:
        with self._lock:
            cached = self._cache.get(profile_id)
            if cached is not None and cached[0] == built_at:
                return cached[1], cached[2]
            chunks = self.store.chunks(profile_id)
            index = BM25Index(
                [tokenize(indexed_text(c.title, c.section_path, c.text)) for c in chunks]
            )
            self._cache[profile_id] = (built_at, chunks, index)
            return chunks, index

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        chunks, index = self._load(request.index.id, request.index.built_at)
        terms = list(dict.fromkeys(tokenize(request.question)))
        evidence = [
            Evidence(
                document_id=chunks[hit.position].document_id,
                document_title=chunks[hit.position].title,
                doc_type=chunks[hit.position].doc_type,
                source_uri=chunks[hit.position].source_uri,
                created_at=chunks[hit.position].created_at,
                section_path=chunks[hit.position].section_path,
                text=chunks[hit.position].text,
                span_start=chunks[hit.position].span_start,
                span_end=chunks[hit.position].span_end,
                rank=rank,
                score=hit.score,
                matched_terms=hit.matched_terms,
            )
            for rank, hit in enumerate(index.search(terms, request.top_k), start=1)
        ]
        return RetrievalResult(
            evidence=evidence,
            metadata={"query_terms": terms, "k1": index.k1, "b": index.b, "chunks": len(chunks)},
        )
