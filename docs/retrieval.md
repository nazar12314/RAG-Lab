# Retrieval

The corpus is not searchable until it is indexed. `make index` builds an **index profile**:

1. `SectionChunker` splits each document on its markdown headings, up to 800 characters per
   chunk. Spans are exact offsets into `corpus.documents.content`, so gold facts can be matched
   to any chunking.
2. Each chunk is embedded with `OPENAI_EMBEDDING_MODEL`.
3. The profile and its chunks replace any earlier build in one transaction.

An unchanged profile is skipped; `python -m backend.app.indexing.pipeline --force` rebuilds it.
`make seed` drops all indexes, so run `make index` again after reseeding.

BM25 and the embedder both see the same text: the document title and section path, then the
chunk. Without that prefix, a chunk in the middle of a postmortem may never name its incident.

## Strategies

| Id | Label | How it ranks | Good at | Weak at |
| --- | --- | --- | --- | --- |
| `bm25` | BM25 | Okapi BM25 (k1 1.5, b 0.75) in Python over stemmed terms | IDs, config names, exact wording | paraphrases |
| `vector` | Vector | exact cosine similarity in pgvector | paraphrases, concepts | identifiers, rare tokens |

BM25 is computed in the backend because PostgreSQL's `ts_rank` is a different formula. The
tokenizer keeps identifiers such as `INC-104` whole and also indexes their parts.

Retrievers read through the `raglab_retriever` role, which has no access to the `eval` schema.

To add a strategy, implement `Retriever` in `backend/app/retrieval/` and register it in
`registry.py`. The contract tests, API and playground pick it up from the registry.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /query/options` | strategies, ready indexes, whether generation is available |
| `GET /examples` | showcase questions, without answers or labels |
| `POST /query` | one strategy, optional generation |
| `POST /query/compare` | several strategies against one index snapshot |

A strategy that cannot run returns `status: unsupported` or `error` with a message. It never
falls back to another method. In a comparison, the other strategies still return results.

## Generation

Every strategy shares one prompt (`PROMPT_VERSION` in `backend/app/generation/answer.py`),
model and 8,000-character context budget, so answer differences come from retrieval. Answers
cite sources by number and return "Not enough evidence." when the sources do not cover the
question. If nothing was retrieved, no model call is made.
