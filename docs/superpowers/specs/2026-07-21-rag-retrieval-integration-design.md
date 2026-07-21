# RAG Retrieval Integration — Real Pipeline Design

## Context

`tools/rag.py` is currently a hardcoded stub — static per-muscle-group text
blocks — used only by `agents/exercise_recommender.py` via the
`search_rag(muscle_group, query)` LangChain tool. Its own docstring already
documents the intended replacement: bge-m3 dense + BM25 sparse retrieval,
RRF fusion, and bge-reranker-v2-m3 reranking, all local.

The RAG team (Mohammed) has now delivered that pipeline as two notebooks
(`notebooks/chunking.ipynb`, `notebooks/vectordb_retrieval.ipynb`) plus real
ingested data: `rag_data/qdrant` contains three populated local Qdrant
collections (`principles`, `hypertrophy`, `strength`), sourced from
`rag_data/books/science_and_development_of_muscle_hypertrophy` (chunked into
~1239 files). `vectordb_retrieval.ipynb` contains working, demoed classes for
the full retrieve → rerank flow, including an LLM-based metadata-filter
extractor for the goal-specific collections (`hypertrophy`/`strength`).

This spec covers porting that pipeline into `tools/rag.py` as the real
implementation behind the existing `search_rag` contract, replacing the
static stub. It does not touch `chunking.ipynb`'s output (the already-ingested
`rag_data/qdrant` data) or re-run ingestion.

## Goals

- Replace the static stub with real hybrid search + reranking over the
  already-ingested Qdrant collections.
- Route each query to the collection(s) that match the plan's paradigm
  (goal), and narrow within a collection using LLM-extracted metadata
  filters, rather than searching a whole collection unfiltered.
- Retrieve top 10 chunks per collection (RRF fusion), rerank the merged
  candidates, return only the top 3 to the calling agent.
- Keep `search_rag`'s job as "return evidence text for the agent to reason
  over" — no second LLM call inside the tool to generate a prose answer.

## Non-goals / explicitly out of scope

- Running or modifying `chunking.ipynb`'s ingestion — `rag_data/qdrant` is
  treated as already correct and complete.
- Any change to `rag_data/books/` source content.
- Latency/cost optimization beyond what's described here (e.g. batching
  extraction calls, streaming). The user will benchmark actual latency
  after this lands and decide whether further optimization is needed.
- A UI or evaluation harness — this is a backend tool swap only.

## Architecture / data flow

```
search_rag(muscle_group, query, goal)
  │
  ├─ combined_query = f"{muscle_group}: {query}"
  │
  ├─ collections = route(goal)          # see Collection routing below
  │
  ├─ for each collection in collections:
  │     filter = extract_metadata(combined_query, collection)   # 1 LLM call/collection, cached by exact query string
  │     candidates += HybridRetriever(collection, top_k=10)
  │                     .retrieve(combined_query, filter)        # dense bge-m3 + BM25 RRF fusion
  │
  ├─ reranked = CrossEncoderReranker(bge-reranker-v2-m3)
  │                .rerank(combined_query, candidates)           # sorts all merged candidates desc by score
  │
  ├─ top3 = reranked[:3]
  │
  └─ return formatted_text(top3)        # source-attributed, no extra LLM call
```

### Collection routing

| `goal` | collections queried |
|---|---|
| `"hypertrophy"` | `hypertrophy`, `principles` |
| `"strength"` | `strength`, `principles` |
| anything else (including empty/unrecognized) | `principles` only |

`goal` is expected to be the plan's paradigm string, the same value
`prompts/exercise_recommender.md` already tells the agent to read from the
`Paradigm:` field. `prompts/exercise_recommender.md` will be updated to
instruct passing it as the new `goal` argument. An unrecognized value never
raises — it just means principles-only, so a forgetful or malformed tool
call degrades gracefully instead of breaking the agent turn.

### Metadata filtering (per collection type)

Two different metadata schemas exist in the ingested data (ported verbatim
from `vectordb_retrieval.ipynb`):

- `hypertrophy` / `strength` chunks carry `GoalNamespaceMetadata`
  (`muscle`, `topic`, `experience_level`, `goals`).
- `principles` chunks carry `PrinciplesMetadata`
  (`topic`, `planner_stage`, `goals`, `applies_to`, `knowledge_type`).

The notebook already implements the goal-collection side end-to-end:
`GoalQueryFilter` (Pydantic model), `GOAL_QUERY_FILTER_PROMPT` +
`GoalMetadataExtractor` (LLM structured-output extraction, cached per exact
query string), and `GoalFilterBuilder` (builds a Qdrant `Filter` via
`FieldCondition`/`MatchAny`, always OR'd with `"all"` for fields that support
it). These port over unchanged.

The notebook defines `PrinciplesQueryFilter` but never builds a matching
extractor or filter builder — that half needs to be written new, following
the exact same `BaseMetadataExtractor`/`BaseFilterBuilder` pattern already in
the notebook: `PRINCIPLES_QUERY_FILTER_PROMPT`, `PrinciplesMetadataExtractor`,
`PrinciplesFilterBuilder`. Both extractors use `get_llm(temperature=0)` from
`agents/llm.py` (Azure OpenAI, the project's only LLM provider) via
`.with_structured_output(...)` — the notebook's own `create_llm` (which
supports Gemini/Groq/NVIDIA/OpenRouter/ITI) is not used; this project only
ever wires Azure.

### Retrieval + reranking

- `HybridRetriever`, `hybrid_search`, `embed_dense_query`,
  `embed_sparse_query`, `BaseRetriever`, `ScoredChunk`, `Chunk`,
  `BaseReranker`, `CrossEncoderReranker` port over from the notebook
  essentially unchanged.
- `top_k=10` per collection query (the RRF fusion `limit` inside
  `hybrid_search`). When both a goal collection and `principles` are
  queried, up to 20 candidates go into the reranker; principles-only goals
  send up to 10.
- The reranker sorts the *merged* candidate list (not per-collection) and
  the top 3 overall are kept — so a query can end up citing only
  `principles`, only the goal collection, or a mix, based purely on
  relevance score.
- No `RAG`/`RAGResponse` class is ported — that notebook class makes a
  second LLM call to synthesize a prose answer, which duplicates
  `exercise_recommender`'s own job. `search_rag` returns evidence chunks,
  not an answer.

### Output format

Replaces the old `=== PRINCIPLES ===` / `=== {MUSCLE} SPECIFIC ===` static
block format with the 3 reranked chunks, source-attributed:

```
=== RAG RESULTS (top 3, reranked) ===
[1] score=3.42 | book: science_and_development_of_muscle_hypertrophy | chapter: 4 | collection: hypertrophy
{chunk text}

[2] score=1.87 | book: ... | chapter: ... | collection: principles
{chunk text}

[3] ...
```

`score` is the raw `CrossEncoder.predict` output (an unbounded logit, not a
0-1 probability) — shown only for debuggability, not meant to be interpreted
as a normalized confidence.

### Models, data, and paths

- New `config.py` constants, following the existing `BASE_DIR`-relative
  pattern: `RAG_DATA_DIR = BASE_DIR / "rag_data"`,
  `QDRANT_PATH = RAG_DATA_DIR / "qdrant"`, `RAG_MODELS_DIR = DATA_DIR /
  "models"`.
- `bge-m3` (`SentenceTransformer`), `bge-reranker-v2-m3` (`CrossEncoder`),
  and the fastembed BM25 model (`Qdrant/bm25`) are downloaded from
  HuggingFace on first use and cached under `RAG_MODELS_DIR`
  (`data/models/...`) — reusing the existing gitignored `data/` directory
  rather than the notebook's own ad hoc `assets/` folder, so no `.gitignore`
  change is needed. First call after a fresh checkout is slow (multi-GB
  download); every call after is fast, matching the notebook's own
  idempotent "skip if already exists" download logic.
- All of the above (Qdrant client, both models, the extractors/filter
  builders/retrievers) are lazily constructed on first `search_rag()` call
  and cached as module-level singletons for the life of the process, guarded
  by a `threading.Lock` so concurrent first calls don't double-initialize.
  They are not loaded at import time, so importing `tools.rag` stays cheap
  when RAG isn't used in a given run.

## Error handling

- Qdrant connection failure or model-loading failure (e.g. no network for
  the first-time HuggingFace download): raise. No silent fallback to the
  old static stub — a silently-degraded RAG tool mid-transition is worse
  than a loud failure.
- Unrecognized/empty `goal`: not an error — falls back to `principles`-only
  per the routing table above.
- Metadata extraction returning an empty/all-`None` filter (LLM found
  nothing confidently extractable, which the extractor's own prompt
  explicitly allows — "never guess... leave it empty"): not an error —
  `GoalFilterBuilder`/`PrinciplesFilterBuilder` builds a `Filter` with an
  empty `must` list, which Qdrant treats as no filtering, so the search
  degrades to unfiltered hybrid search over that collection rather than
  failing.

## File-by-file changes

| File | Change |
|---|---|
| `tools/rag.py` | Rewritten. Real pipeline replaces the static stub. Keeps `search_rag` as the `@tool`-decorated entry point (contract preserved, `goal` param added). |
| `config.py` | Add `RAG_DATA_DIR`, `QDRANT_PATH`, `RAG_MODELS_DIR` constants. |
| `prompts/exercise_recommender.md` | Update the `search_rag` calling instructions to also pass `goal` (the paradigm value already being read for the intensity tables). |
| `agents/exercise_recommender.py` | No change — `search_rag` is still passed into the `tools` list as-is; the LLM tool-calling agent supplies the new `goal` arg based on the updated prompt. |
| `requirements.txt` | No change expected — `qdrant-client`, `sentence-transformers`, `fastembed` are already listed/installed. Verify during implementation. |

## Open questions / deferred

- Actual end-to-end latency of 1-2 metadata-extraction LLM calls + hybrid
  search + reranking per `search_rag` call, across the up-to-5 calls one
  `exercise_recommender` run makes (one per muscle group) — to be measured
  after implementation; the user will decide then whether it needs
  optimizing (e.g. parallelizing the two extraction calls, reducing
  `top_k`).
- Whether `chunking.ipynb`'s ingestion should be re-run for additional
  source books beyond `science_and_development_of_muscle_hypertrophy` —
  unrelated to this spec, owned by the RAG data pipeline, not this
  integration.
