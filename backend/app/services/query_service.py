"""Runs retrieval strategies and optional answer generation for the playground."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from typing import Protocol

from backend.app.generation.answer import AnswerGenerator
from backend.app.models.contracts import (
    CompareRequest,
    CompareResponse,
    IndexProfile,
    Latency,
    PlaygroundOptions,
    QueryOptions,
    QueryRequest,
    QueryResponse,
    RetrievalRequest,
    StrategyInfo,
    Usage,
)
from backend.app.retrieval.base import ProviderError, Retriever, Unsupported

NO_KEY_MESSAGE = "OPENAI_API_KEY is not set, so answers cannot be generated."
NO_INDEX_MESSAGE = "Index not built. Run `make index` to create one."


class UnknownStrategy(Exception):
    pass


class ProfileSource(Protocol):
    def ready_profiles(self, dataset: str) -> list[IndexProfile]: ...


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 1)


class QueryService:
    def __init__(
        self,
        retrievers: dict[str, Retriever],
        profiles: ProfileSource,
        answers: AnswerGenerator | None,
        dataset: str,
        default_top_k: int = 5,
        default_hop_limit: int = 2,
    ) -> None:
        self.retrievers = retrievers
        self.profiles = profiles
        self.answers = answers
        self.dataset = dataset
        self.default_top_k = default_top_k
        self.default_hop_limit = default_hop_limit

    def options(self) -> PlaygroundOptions:
        return PlaygroundOptions(
            dataset_version=self.dataset,
            strategies=[
                StrategyInfo(id=key, label=r.label, description=r.description)
                for key, r in self.retrievers.items()
            ],
            indexes=self.profiles.ready_profiles(self.dataset),
            generation_available=self.answers is not None,
            default_top_k=self.default_top_k,
            default_hop_limit=self.default_hop_limit,
        )

    def _index(self, requested: str | None) -> IndexProfile | None:
        ready = self.profiles.ready_profiles(self.dataset)
        if requested is None:
            return ready[0] if ready else None
        return next((p for p in ready if p.id == requested), None)

    def _check(self, strategies: list[str]) -> None:
        unknown = [s for s in strategies if s not in self.retrievers]
        if unknown:
            raise UnknownStrategy(f"Unknown strategy: {', '.join(unknown)}")

    def query(self, request: QueryRequest) -> QueryResponse:
        self._check([request.strategy])
        question = request.question.strip()
        return self._run(request.strategy, question, self._index(request.index_profile), request)

    def compare(self, request: CompareRequest) -> CompareResponse:
        strategies = request.strategies or list(self.retrievers)
        self._check(strategies)
        question = request.question.strip()
        # Resolved once, so every strategy answers against the same index snapshot.
        index = self._index(request.index_profile)
        # Concurrent so a slow strategy such as the agent does not hold up the rest.
        with ThreadPoolExecutor(max_workers=len(strategies)) as pool:
            results = list(pool.map(lambda s: self._run(s, question, index, request), strategies))
        return CompareResponse(
            question=question,
            index_profile=index.id if index else None,
            results=results,
        )

    def _run(
        self, strategy: str, question: str, index: IndexProfile | None, options: QueryOptions
    ) -> QueryResponse:
        def failed(status, message: str, started: float) -> QueryResponse:
            return QueryResponse(
                strategy=strategy,
                status=status,
                message=message,
                index_profile=index.id if index else options.index_profile,
                top_k=options.top_k,
                latency=Latency(retrieval_ms=_elapsed_ms(started)),
            )

        started = perf_counter()
        if index is None:
            return failed("unsupported", NO_INDEX_MESSAGE, started)
        try:
            result = self.retrievers[strategy].retrieve(
                RetrievalRequest(
                    question=question,
                    index=index,
                    top_k=options.top_k,
                    hop_limit=options.hop_limit,
                )
            )
        except Unsupported as exc:
            return failed("unsupported", str(exc), started)
        except ProviderError as exc:
            return failed("error", str(exc), started)

        response = QueryResponse(
            strategy=strategy,
            status="ok",
            index_profile=index.id,
            top_k=options.top_k,
            evidence=result.evidence,
            graph_paths=result.graph_paths,
            entities=result.entities,
            tool_trace=result.tool_trace,
            answer=result.answer,
            latency=Latency(retrieval_ms=_elapsed_ms(started)),
            usage=result.usage,
            metadata=result.metadata,
        )
        if options.generate and result.answer is None:
            self._generate(question, response)
        return response

    def _generate(self, question: str, response: QueryResponse) -> None:
        if self.answers is None:
            response.answer_error = NO_KEY_MESSAGE
            return
        started = perf_counter()
        try:
            answer = self.answers.generate(question, response.evidence)
        except ProviderError as exc:
            response.answer_error = str(exc)
            return
        response.answer = answer
        response.latency.generation_ms = _elapsed_ms(started)
        response.usage = Usage(
            embedding_tokens=response.usage.embedding_tokens,
            prompt_tokens=answer.prompt_tokens,
            completion_tokens=answer.completion_tokens,
        )
