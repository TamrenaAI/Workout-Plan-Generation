# Tamrena AI — Workout Plan Generation System

Tamrena is an AI-powered workout plan generator that replaces static gym
program templates with a personalized multi-agent pipeline. Instead of
picking a template off a few generic inputs, it reads a user's actual
body composition data (InBody scan) plus their goals and constraints,
and generates a plan unique to them — split, muscle emphasis, exercise
selection, and set/rep prescription all decided per individual.

---

## How a plan gets built

```
User intake form + InBody scan
        │
        ▼
InBody image pipeline (tools/inbody.py) → structured data + FLAGS
  quality check → authenticity check → VLM extraction → deterministic flags
        │
        ▼
Supervisor agent
  - classifies the goal into a programming paradigm
  - decides split (Full Body / PPL / Upper-Lower / etc.)
  - decides muscle groups + intensity per group
  - computes the DAY MAP (per-day set budget from session_duration)
  - routes InBody flags to only the muscle groups they apply to
  - initializes progress tracking
        │
        ▼
Exercise Recommender sub-agent (runs once per muscle_group ID, sequentially)
  - reads shared memory, queries RAG stub + SQLite exercise DB
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

## Project layout

Production code lives in flat top-level packages, not notebooks:

```
main.py                    ← single entry point: python main.py starts the API + frontend
config.py                  ← env loading, shared paths (SESSION_DIR, DB_PATH, PROMPTS_DIR)

agents/
  llm.py                     ← shared Azure OpenAI client factory
  supervisor.py               ← build_supervisor()
  exercise_recommender.py     ← EXERCISE_RECOMMENDER definition
  plan_assembler.py           ← PLAN_ASSEMBLER definition
  plan_adjuster.py             ← build_plan_adjuster() — standalone agent invoked on demand from
                                 post-workout feedback, not a Supervisor sub-agent
  streaming.py                 ← translates deepagents' event stream into live progress events

tools/
  memory.py                 ← shared MD memory file + progress tracking tools + read_workout_feedback
  rag.py                    ← search_rag — HARDCODED STUB, see below
  database.py                ← search_exercise_db — SQLite
  inbody.py                  ← InBody VLM pipeline (quality/auth/extraction/flags) + parse_inbody_text

pipeline/
  plan_finalize.py           ← enforce_volume_budget — deterministic post-processing run by the
                                API route after the agent pipeline finishes, not an agent tool
  inbody_history.py           ← per-user InBody scan history (SQLite) + latest-vs-previous comparison,
                                recorded by the API route right after each InBody pipeline run
  workout_feedback.py          ← records post-workout feedback (JSON, not plan.md prose) + decides
                                 whether it needs the Plan Adjuster agent dispatched at all

auth/
  tokens.py                   ← issues/verifies this backend's own session JWTs
  dependencies.py              ← get_current_user — FastAPI dependency protecting a route
  ownership.py                 ← plan_sessions table: which user owns which generated-plan session_id

prompts/
  supervisor.md
  exercise_recommender.md
  plan_assembler.md
  plan_adjuster.md

See docs/CODE_MAP.md for the layer diagram and the checklist for adding a new agent.

api/
  main.py                    ← FastAPI app
  routes/health.py            ← GET /health
  routes/plan.py               ← POST /validate-image, POST /generate-plan (requires login),
                                  GET /generate-plan/stream/{id} (ownership-checked),
                                  GET /sessions (current user's past sessions),
                                  GET /sessions/{id}/plan (persisted weekly schedule, fetchable any
                                  time after generation — not just live via the SSE stream)
  routes/progress.py            ← GET /progress/scans, GET /progress/comparison (latest vs previous InBody scan)
  routes/workouts.py             ← POST /workouts/{id}/feedback — records feedback, dispatches the
                                   Plan Adjuster agent only if an exercise was flagged
  schemas/response.py          ← response models

database/
  seed.py                     ← seeds data/tamreena.db (SQLite)

scripts/
  run_pipeline.py               ← run any of the 13 test cases end-to-end from the CLI
  inspect_session.py             ← view a session's plan.md / progress.json after a run

sessions/                      ← created at runtime, one dir per session_id
data/tamreena.db                ← SQLite exercise database
tests/test_cases.py              ← 13 reference user profiles used by scripts/run_pipeline.py
notebooks/                       ← original exploration notebooks, kept as reference/history

frontend/                        ← vanilla JS/CSS web UI (see FRONTEND.md), mounted by api/main.py at "/".
                                    No login flow — since /generate-plan now requires auth, this is
                                    superseded by the mobile app rather than actively developed further.
  index.html
  src/theme.css, base.css        ← design tokens + shared component classes
  src/main.js                    ← hash router
  src/pages/                     ← home, intake, capture, processing, plan
  src/components/CameraCapture.js ← live camera feed + quality/authenticity state machine
```

mobile/ has moved to its own repo: https://github.com/TamrenaAI/mobile
(git history preserved via `git subtree split`). See that repo's README
for the app's source-tree breakdown, auth setup (Google Sign-In native
module, dev-client build requirements), and web-preview instructions.

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
in `tamrena_architecture_2.md`). Progress is now written and read only
through structured tool calls (`init_plan_progress`, `mark_step_done`,
`get_plan_progress`, `validate_plan_completeness`), never parsed back out
of agent-written prose.

## Agents

| Agent | Role | Tools |
|---|---|---|
| InBody pipeline | Tool (not an agent) — quality check, authenticity check, VLM extraction, deterministic flag computation | `tools/inbody.py` |
| Supervisor | Orchestrates the whole run: paradigm classification, split, intensity, DAY MAP, flag routing, dispatch order | `parse_inbody_text`, `read_plan_memory`, `write_plan_memory`, `init_plan_progress`, `get_plan_progress` |
| Exercise Recommender | One agent definition, called once per muscle_group ID with a different prompt each time | `search_rag`, `search_exercise_db`, `read_plan_memory`, `write_plan_memory`, `mark_step_done` |
| Plan Assembler | Builds the final weekly schedule and enforces session-duration budgets | `read_plan_memory`, `write_plan_memory`, `validate_plan_completeness`, `validate_session_duration` |

All LLM calls go through Azure OpenAI (`AZURE_OPENAI_DEPLOYMENT_NAME`) via
`ChatOpenAI` pointed at the Azure endpoint's OpenAI-compatible `base_url`
(`agents/llm.py`).

## Retrieval (RAG) — real hybrid search + reranking

`tools/rag/` is a package: `models.py` (Pydantic schemas matching the
ingested data), `filtering.py` (LLM-extracted metadata filters + Qdrant
filter builders), `retrieval.py` (dense `BAAI/bge-m3` + BM25 sparse hybrid
search fused with RRF), `reranking.py` (`BAAI/bge-reranker-v2-m3`
cross-encoder), and `pipeline.py` (orchestration). `tools/rag/__init__.py`
re-exports `search_rag`, the only contract the rest of the system depends
on — now `search_rag(muscle_group, query, goal)`, where `goal` is the
plan's paradigm.

Three real Qdrant collections live in `rag_data/qdrant` (`principles`,
`hypertrophy`, `strength`), ingested from
`rag_data/books/science_and_development_of_muscle_hypertrophy` by
`notebooks/chunking.ipynb` + `notebooks/vectordb_retrieval.ipynb`. `goal`
routes each query to the matching collection plus `principles`
(`hypertrophy` → `[hypertrophy, principles]`; `strength` →
`[strength, principles]`; any other paradigm → `[principles]` only).
Within each collection, an LLM call extracts a structured filter (muscle,
topic, experience level, etc.) to narrow the search instead of scanning
the whole collection, then hybrid search retrieves the top 10 per
collection and the cross-encoder reranks the merged candidates down to
the top 3 returned to the calling agent.

Models and the BM25 index are downloaded from Hugging Face on first use
and cached under `data/models/` (gitignored); Qdrant, the dense/reranker
models, and the LLM client are lazily loaded once per process. See
`docs/superpowers/specs/2026-07-21-rag-retrieval-integration-design.md`
for the full design.

## Exercise database — SQLite, by design at this stage

`data/tamreena.db`, seeded via `python database/seed.py`. `tools/database.py`
queries it by muscle group, movement type, and contraindications through
`search_exercise_db`. MongoDB (`tamrena_architecture_2.md` Section 8) is the
future target once the system needs the richer 12-muscle-group schema; this
stage stays on SQLite with the 5 broad muscle-group IDs the Supervisor
actually dispatches (`chest`, `back`, `shoulders`, `arms`, `legs`, with
`legs` split into `legs_a`/`legs_b` on 4-day Upper/Lower splits).

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in AZURE_OPENAI_* (and LANGSMITH_* if you want tracing)

python database/seed.py                 # seed the SQLite exercise DB

python main.py                           # start the API + frontend (or: uvicorn api.main:app --reload)
# UI   http://localhost:8001/            (frontend/, see FRONTEND.md)
# GET  http://localhost:8001/health
# POST http://localhost:8001/validate-image  (multipart: file)
# POST http://localhost:8001/plan             (multipart: inbody_file + intake form fields)
# POST http://localhost:8001/generate-plan    (alias of /plan, used by the frontend)
# Port comes from main.py's PORT env var (default 8001) — set HOST/PORT to override.

python scripts/run_pipeline.py --list    # or run a reference case end-to-end from the CLI
python scripts/run_pipeline.py --case 1
python scripts/inspect_session.py <session_id>
```

## Where things stand

| Part | Status |
|---|---|
| InBody VLM parsing (quality/authenticity/extraction/deterministic flags) | Implemented (`tools/inbody.py`) |
| Supervisor + Exercise Recommender + Plan Assembler agents | Implemented (`agents/`, `prompts/`) |
| Shared MD memory + progress tracking | Implemented (`tools/memory.py`) |
| SQLite exercise search | Implemented (`tools/database.py`, `database/seed.py`) |
| RAG (Qdrant hybrid search) | Implemented (`tools/rag/`) — hybrid dense+sparse retrieval, reranking, real ingested data |
| FastAPI endpoints (`/health`, `/validate-image`, `/plan`, `/generate-plan`) | Implemented (`api/`) |
| Frontend (vanilla JS/CSS, mounted at `/`) | Implemented (`frontend/`, see `FRONTEND.md`) |
| `/ingest` (RAG document ingestion) | Not built as an API route — ingestion is done offline via `notebooks/chunking.ipynb` + `notebooks/vectordb_retrieval.ipynb` |
| MongoDB exercise DB | Not built — deferred, SQLite is used at this stage per current direction |

`notebooks/Agent_exploration.ipynb` and `notebooks/Inbody_Agent.ipynb` are
kept as the historical record of how each piece was validated before being
productionized into the module layout above — they are not the source of
truth for running the system anymore.

## Environment

See `.env.example`. LLM calls go through Azure OpenAI
(`AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`,
`AZURE_OPENAI_API_VERSION`). `LANGSMITH_*` enables tracing. No MongoDB URI,
no Qdrant URL, no Pinecone/Cohere/OpenAI/HuggingFace API keys are needed at
this stage.

## Deploying to AWS ECR

Manual build-and-push process (no CI/CD pipeline yet — see
`docs/superpowers/specs/2026-07-23-docker-ecr-deployment-design.md`
for why that's out of scope for now):

```bash
# One-time: find your AWS account ID
aws sts get-caller-identity --query Account --output text

# Authenticate Docker against ECR
aws ecr get-login-password --region eu-north-1 \
  | docker login --username AWS --password-stdin <account-id>.dkr.ecr.eu-north-1.amazonaws.com

# Build, tag, push
docker build -t tamreena-backend .
docker tag tamreena-backend:latest <account-id>.dkr.ecr.eu-north-1.amazonaws.com/tamreena-backend:latest
docker push <account-id>.dkr.ecr.eu-north-1.amazonaws.com/tamreena-backend:latest
```

Replace `<account-id>` with the output of the `aws sts get-caller-identity`
command above. The ECR repository `tamreena-backend` must already exist
in `eu-north-1` (`aws ecr create-repository --repository-name tamreena-backend --region eu-north-1`
if it doesn't yet).

**RAG models from S3:** the image does NOT contain the ~4.4GB RAG
embedding/reranker models (`data/models/`) — only the small exercise
media/DB and Qdrant data are baked in. `RAG_MODELS_S3_BUCKET` is set to
`fitness-app-models-prod-2026` and `RAG_MODELS_S3_PREFIX` to `workout`
(region `eu-north-1`) as an environment variable on whatever runs this
image (e.g. an ECS task definition), so they sync from S3 at container
startup. Leave `RAG_MODELS_S3_BUCKET` unset to skip the sync entirely —
`tools/rag/pipeline.py`'s existing HuggingFace-download fallback still
works in that case, just slower on first use. On ECS/Fargate, S3 read
access should come from the task's IAM role, not static credentials.
See `docs/AWS_SETUP.md` and `iam/rag-models-s3-policy.json` for the
least-privilege policy to attach.

**Known limitation:** `sessions/` (plan.md session state) is not
persistent across ECS task restarts by default — each task has its own
ephemeral filesystem. Making this durable in production would need EFS
or a data-store migration; that's an infrastructure decision beyond
this repo's Docker setup, not solved here.
