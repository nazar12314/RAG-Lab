"""OpenAI embedding calls, used both at index time and for query vectors."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import cached_property
from typing import Protocol

import openai
import tiktoken

from backend.app.retrieval.base import ProviderError

logger = logging.getLogger(__name__)

BATCH_SIZE = 128
TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class Embeddings:
    vectors: list[list[float]]
    tokens: int


class Embedder(Protocol):
    model: str

    def embed(self, texts: list[str]) -> Embeddings: ...

    def count_tokens(self, text: str) -> int: ...


class OpenAIEmbedder:
    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self.client = openai.OpenAI(api_key=api_key, timeout=TIMEOUT_SECONDS)

    @cached_property
    def _encoding(self) -> tiktoken.Encoding:
        return tiktoken.encoding_for_model(self.model)

    def count_tokens(self, text: str) -> int:
        return len(self._encoding.encode(text))

    def embed(self, texts: list[str]) -> Embeddings:
        vectors: list[list[float]] = []
        tokens = 0
        try:
            for i in range(0, len(texts), BATCH_SIZE):
                response = self.client.embeddings.create(
                    model=self.model, input=texts[i : i + BATCH_SIZE]
                )
                vectors.extend(item.embedding for item in response.data)
                tokens += response.usage.total_tokens
        except openai.OpenAIError as exc:
            logger.warning("embedding request failed: %s", exc)
            raise ProviderError(f"OpenAI embedding request failed ({type(exc).__name__})") from exc
        return Embeddings(vectors, tokens)
