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
| `hybrid` | Hybrid | Reciprocal Rank Fusion (k 60) of BM25 and vector | mixed questions | the failure of both sides |
| `graph` | Graph | entity linking, then a bounded walk over typed edges | relationships, multi-hop chains | questions naming no known entity |
| `agent` | Agent | an LLM calls retrieval tools step by step | investigations, counts, mixed questions | cost and latency |

BM25 is computed in the backend because PostgreSQL's `ts_rank` is a different formula. The
tokenizer keeps identifiers such as `INC-104` whole and also indexes their parts.

Retrievers read through the `raglab_retriever` role, which has no access to the `eval` schema.

### Graph retrieval

1. Names and aliases in the question are linked to entities. The longest alias wins its span,
   and an ambiguous alias keeps every entity it names. If nothing links, the strategy reports
   `unsupported` rather than falling back.
2. A recursive SQL query walks edges in both directions, up to the hop limit (default 2, max 3).
   Team and subsystem nodes can end a walk but not continue one, since sharing an owner says
   nothing about cause.
3. Each edge's supporting document spans are mapped to chunks of the selected index, so results
   compare directly with the other strategies.
4. Chunks are ranked by question overlap, divided by hop distance, multiplied by edge confidence.
   Refuted edges stay available at reduced weight, because "what was ruled out?" is a real
   question.

The playground draws the 10 strongest paths on the Graph Explorer canvas, hops running left to
right. A path is only as strong as its worst-supported edge, so a direct, well-evidenced edge is
never pushed out by a long, weak chain.

This walks the **curated** graph, an upper-bound baseline: its edges were authored with the
dataset, so scores show what graph retrieval can do with a perfect graph, not an extracted one.

To add a strategy, implement `Retriever` in `backend/app/retrieval/` and register it in
`registry.py`. The contract tests, API and playground pick it up from the registry.

### Agent

One LangChain `create_agent` loop over six typed, read-only tools. The search tools are the same
retriever instances the other strategies use, so the modes cannot drift apart.

| Tool | Backed by |
| --- | --- |
| `exact_lookup` | parameterized queries over incidents, deployments, services, teams |
| `aggregate_records` | counts with fixed group-by columns and filters |
| `keyword_search` | the BM25 retriever |
| `semantic_search` | the vector retriever |
| `graph_traverse` | the graph retriever, from one named entity |
| `fetch_evidence` | the full document or record behind an evidence ID |

There is no free-form SQL. Limits: 8 tool calls and 90 seconds per question, top-k per search
call. The model must give a reason with each call. That reason, the arguments, returned
evidence IDs and timing form the tool trace shown in the playground.

The agent writes its own answer, so it bypasses the shared answer prompt. Citations that do not
match evidence it actually retrieved are not counted. Its evidence is everything it collected,
cited items first, so it can exceed top-k.

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
