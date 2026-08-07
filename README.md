# Tamrena AI — Personalized Workout Plan Generation Platform

Tamrena is an AI-powered fitness platform that replaces static gym program
templates with a fully personalized, multi-agent plan-generation pipeline.
Instead of picking from a handful of generic templates, it reads a user's
actual body-composition scan (InBody) plus their goals, experience level,
and constraints, and generates a training plan unique to that person —
split, muscle emphasis, exercise selection, and set/rep/rest prescription
all decided individually, then adapted over time from real workout
feedback and monthly progress reviews.

Built end-to-end: LLM agent orchestration, retrieval-augmented generation,
computer-vision-based document parsing, a FastAPI backend, DynamoDB
persistence, JWT auth, a Docker/AWS deployment pipeline, and a test suite —
all in a single production-structured codebase.

---

## What it does

1. **Ingests a body-composition scan.** A user uploads an InBody scan
   (photo or PDF). A vision pipeline validates image quality and
   authenticity, extracts structured body-composition data via a VLM, and
   deterministically computes clinical flags (muscle asymmetry, elevated
   body fat, trunk underdevelopment) in pure Python — the model extracts
   raw numbers, it never gets to decide the flags itself.
2. **Generates a personalized plan.** A supervisor agent classifies the
   user's goal into a training paradigm, decides a split and per-day set
   budget, and routes only the relevant body-composition flags to the
   muscle groups they actually affect. Specialist agents then prescribe
   exercises per muscle group — pulling from a hybrid dense+sparse
   retrieval system over real exercise-science literature, plus a curated
   exercise database — before a final assembly agent builds the weekly
   schedule and enforces session-duration limits.
3. **Streams progress live.** Plan generation runs as a background task
   while the client watches real-time progress over Server-Sent Events.
4. **Learns from feedback.** After a workout, users can flag exercises as
   too easy, too hard, or painful. A dedicated adjustment agent reads the
   plan and feedback and rewrites the affected portion — logged as a
   structured, matchable adjustment record, not just prose.
5. **Reviews monthly progress.** Once a plan has run for 30+ days, a
   deterministic aggregation step computes adherence, rep quality, and
   body-composition change, and an LLM narrates the result before a fresh
   plan is generated for the next cycle.

---

## Architecture

```
User intake + InBody scan
        │
        ▼
InBody vision pipeline
  quality check → authenticity check → VLM extraction → deterministic flags
        │
        ▼
Supervisor agent  (LangGraph / deepagents)
  classifies goal → training paradigm
  decides split + per-day set budget (DAY MAP)
  routes body-composition flags to relevant muscle groups
        │
        ▼
Exercise Recommender agent  (dispatched once per muscle group, sequentially)
  hybrid RAG search (dense + sparse + reranking) over exercise-science literature
  exercise database lookup
  prescribes exercises within the day's set budget
        │
        ▼
Plan Assembler agent
  builds the full weekly schedule
  enforces recovery + session-duration rules
        │
        ▼
Deterministic post-processor
  hard-enforces the volume budget the LLM was asked (but not guaranteed) to respect
        │
        ▼
Final plan — streamed live via SSE, persisted per session
```

Every agent in a session communicates through one shared, append-only
markdown file rather than message-passing — each agent reads the full
history before acting, giving a built-in audit trail and eliminating
context-sync bugs between agents. A parallel structured progress file
tracks step completion, since early testing showed relying on parsing
free-form agent prose to track state was unreliable.

---

## Tech stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph / `deepagents`, LangChain |
| LLM | Azure OpenAI (`ChatOpenAI` via Azure-compatible endpoint) |
| Retrieval-augmented generation | Qdrant (hybrid dense + BM25 sparse search, RRF fusion), sentence-transformers, cross-encoder reranking |
| Computer vision | OpenCV, PyMuPDF, VLM-based structured extraction |
| Backend API | FastAPI, Uvicorn, Server-Sent Events for live streaming |
| Database | DynamoDB (`boto3`), region `eu-north-1`, tables named `workout_<name>` |
| Auth | JWT (HS256), FastAPI dependency-based route protection |
| Frontend | Vanilla JS/CSS SPA (hash router, no build step) |
| Testing | Pytest (unit + integration coverage across agents, pipeline, RAG, and auth) |
| Deployment | Docker, AWS ECR/ECS, AWS S3 (model artifact sync) |

---

## Project structure

```
main.py                  Application entry point (uvicorn)
config.py                Environment loading, shared paths

agents/                  LLM agent definitions (supervisor, exercise recommender,
                          plan assembler, plan adjuster, progress analyst) + streaming
prompts/                 System prompts driving each agent's behavior
tools/                   LangChain tools agents call at runtime (RAG search, exercise DB,
                          InBody vision pipeline, session memory, DynamoDB access)
pipeline/                Deterministic, non-agent post-processing (volume-budget
                          enforcement, plan parsing, feedback recording, progress aggregation)
rag_pipeline/            Offline RAG ingestion, chunking, evaluation, and experimentation toolkit
api/                     FastAPI application, routes, and request/response schemas
auth/                    JWT verification, route protection, session-ownership checks
frontend/                Vanilla JS/CSS single-page application
tests/                   Pytest suite covering agents, pipeline, RAG, and auth
scripts/                 CLI utilities for running and inspecting pipeline sessions
```

---

## Running it locally

```bash
pip install -r requirements.txt
cp .env.example .env      # fill in Azure OpenAI credentials, AWS credentials, JWT secret

python main.py             # starts the API + frontend at http://localhost:8001
```

```
GET  /health                          liveness/readiness probe
POST /validate-image                  InBody scan quality/authenticity pre-check
POST /generate-plan                   upload scan + intake form, generates a plan
GET  /generate-plan/stream/{id}       live plan-generation progress (SSE)
GET  /sessions/{id}/plan              fetch a generated plan
POST /workouts/{id}/feedback          record post-workout feedback, triggers adjustment
POST /plan/{id}/monthly-review        run a monthly progress review
```

```bash
python scripts/run_pipeline.py --list     # run a reference profile end-to-end from the CLI
python scripts/run_pipeline.py --case 1
pytest                                     # run the test suite
```

---

## Deployment

Containerized with Docker (CPU-only build, RAG models baked in at build
time for a self-contained image) and deployable to AWS ECR/ECS. See the
codebase's `docs/` directory for deployment notes.

---

## About this project

Tamrena was built to explore how far multi-agent LLM orchestration can go
in a domain that demands both personalization and reliability — a wrong
training prescription has real consequences, so every place an LLM's
output could silently drift (volume budgets, body-composition flags,
progress numbers) is backed by a deterministic check rather than trusted
outright. The result is a system where agents handle judgment and
language, and plain Python handles anything that has to be *correct*.
