# Tamrena AI — Workout Plan Generation System

Tamrena is an AI-powered workout plan generator that replaces static gym
program templates with a personalized multi-agent pipeline. Instead of
picking a template off a few generic inputs, it reads a user's actual
body composition data (InBody scan) plus their goals and constraints,
and generates a plan unique to them — split, muscle emphasis, exercise
selection, and set/rep prescription all decided per individual.

Full architecture reference: [`tamrena_architecture_2.md`](./tamrena_architecture_2.md).

---

## How a plan gets built

```
User intake form + InBody scan
        │
        ▼
VLM parses InBody scan → structured data + FLAGS (tool, not an agent)
        │
        ▼
Supervisor agent
  - decides split (Full Body / PPL / Upper-Lower / etc.)
  - decides muscle groups + intensity per group
  - computes the DAY MAP (per-day set budget from session_duration)
  - routes InBody flags to only the muscle groups they apply to
  - initializes progress tracking
        │
        ▼
Exercise Recommender sub-agent (runs once per muscle group, sequentially)
  - reads shared memory, queries RAG + exercise DB
  - prescribes 3-5 exercises within its day's set budget
  - marks itself done in progress tracking
        │
        ▼
Plan Assembler sub-agent
  - only runs once every muscle group is confirmed complete
  - builds the weekly schedule, enforces recovery + session duration rules
        │
        ▼
Supervisor returns the final plan
```

Agents run **sequentially, not in parallel** — each one depends on reading
what the previous agent wrote before it can make its own decisions.

## Why a shared markdown file instead of a database

There's no shared database between agents. Each session gets its own file
at `sessions/{session_id}/plan.md`, and every agent reads the whole file
before acting and appends its own section when done. This means:

- No context-sync problems — every agent sees exactly the same state
- The file itself is a full audit trail of every decision made
- No concurrent-write conflicts, because execution is sequential

Alongside it, `sessions/{session_id}/progress.json` tracks which muscle
groups are actually complete. This exists because early testing showed
the Supervisor could lose track of its own dispatch history by relying on
free-form markdown alone — a fully-planned muscle group was silently
dropped from a real plan with no error (see "Change Log" section 14, v1.2,
in the architecture doc). Progress is now written and read only through
structured tool calls (`init_plan_progress`, `mark_step_done`,
`get_plan_progress`, `validate_plan_completeness`), never parsed back out
of agent-written prose.

## Agents

| Agent | Role | Tools |
|---|---|---|
| InBody Parser | Tool (not an agent) — vision call that turns a raw scan into structured data + flags | Azure OpenAI vision |
| Supervisor | Orchestrates the whole run: split, intensity, DAY MAP, flag routing, dispatch order | `parse_inbody`, `write_todos`, `task` |
| Exercise Recommender | One agent definition, called once per muscle group with a different prompt each time | `search_rag`, `search_exercise_db`, `read_plan_memory`, `write_plan_memory`, `mark_step_done` |
| Plan Assembler | Builds the final weekly schedule and enforces session-duration budgets | `read_plan_memory`, `write_plan_memory`, `validate_session_duration`, `validate_plan_completeness`, `format_plan_session` |

All LLM calls run through Azure OpenAI (`gpt-4.1-mini`) via an initialized
`AzureChatOpenAI` instance — deepagents' plain model-string shorthand only
targets OpenAI directly, not Azure.

## Retrieval (RAG)

Two Qdrant collections back the recommender's exercise-science knowledge:

- **`tamrena_principles`** — recovery, progressive overload, periodization; queried by every agent call, no filtering
- **`tamrena_muscle_specific`** — exercise mechanics tagged by muscle group; filtered by muscle before hybrid search runs

Search is hybrid (BM25 sparse + `BAAI/bge-m3` dense, fused with RRF) and
reranked locally with `BAAI/bge-reranker-v2-m3`. Everything in the RAG
pipeline runs locally — no embedding or reranking API calls.

**Current status:** RAG is a hardcoded stub in the notebook
(`search_rag` returns static training principles per muscle group). The
Qdrant pipeline described above and in architecture doc section 7 is the
target design, not yet implemented — pending the RAG team's ingestion
pipeline.

## Exercise database

MongoDB collection `tamrena.exercises`, seeded from a 1,324-exercise
dataset via `database/seed.py`. This part is real and already wired up —
the recommender queries it directly by muscle group, movement type, and
contraindications.

## Where things stand

Development is happening notebook-first, in
[`notebooks/Agent_exploration.ipynb`](./notebooks/Agent_exploration.ipynb),
to validate each part of the pipeline before it's split out into the
`agents/` / `tools/` / `api/` module layout described in architecture doc
section 11. [`notebooks/RAG_exploration.ipynb`](./notebooks/RAG_exploration.ipynb)
covers RAG-side exploration separately.

| Part | Status |
|---|---|
| InBody VLM parsing | Implemented in notebook |
| Supervisor + Exercise Recommender + Plan Assembler agents | Implemented in notebook |
| Shared MD memory + progress tracking | Implemented in notebook |
| MongoDB exercise search | Real — connects to `tamrena.exercises` |
| RAG (Qdrant hybrid search) | Hardcoded stub — real pipeline pending RAG team |
| FastAPI endpoints (`/health`, `/ingest`, `/plan`) | Designed, not yet built |

**Build order:** MongoDB seed → local embedding/reranker models → RAG
ingestion pipeline → tool functions → agents → FastAPI → smoke test.

## Environment

LLM calls go through Azure OpenAI — see `tamrena_architecture_2.md`
section 10 for the full list of required environment variables
(`AZURE_OPENAI_*`, `QDRANT_URL`, `MONGODB_URI`, `LANGSMITH_*`). No
Pinecone, Cohere, OpenAI, or HuggingFace API keys are needed — the RAG
embedding/reranking models are public and run locally.
