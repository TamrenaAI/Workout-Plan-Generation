# Code Map

Where things live, and why, so this stays easy to navigate as more agents
and features get added. For the full pipeline design (paradigms, DAY MAP,
RAG schema, etc.) see `tamrena_architecture_2.md` — this doc is just the
"what goes where" reference.

## Layers

```
api/        FastAPI routes, request/response schemas. HTTP-facing only —
            no agent logic or prompt engineering lives here.
              │
              ▼
agents/     One file per agent (model + tools + system prompt + name),
            plus the shared LLM client factory and the event-stream
            translator used to narrate live progress.
              │
              ▼
tools/      LangChain @tool-decorated functions that agents call during a
            run: shared plan memory/progress tracking, the exercise DB,
            the RAG stub, the InBody VLM pipeline.
              │
              ▼
pipeline/   Deterministic post-processing that runs AFTER the agent
            pipeline finishes. Not a tool any agent calls — called
            directly by the API route. Also holds per-user historical
            records the API route reads/writes around a pipeline run
            (e.g. inbody_history.py) — not agent tools either.

database/   One-off scripts (seeding).
services/   Cross-cutting infra that isn't business logic (the in-memory
            SSE progress event bus).
auth/       User accounts, Google Sign-In verification, this backend's own
            session JWTs, and session ownership (which user owns which
            generated-plan session_id). Not agent tools and not
            post-pipeline processing — foundational request-auth/authz
            infrastructure that api/ routes depend on directly via
            Depends(auth.dependencies.get_current_user).
prompts/    One .md system prompt per agent, same base name as its file
            in agents/ (supervisor.py ↔ supervisor.md, etc).
```

## The rule for `tools/` vs `pipeline/`

If an agent calls it as a tool during its run → `tools/`.
If it runs after the agent pipeline is done, without any agent invoking it →
`pipeline/`. `pipeline/plan_finalize.py` is the current example: the Plan
Assembler is *supposed* to self-trim over-budget days, but doesn't reliably
do it, so the API route deterministically re-checks and fixes it afterward.

## Adding a new agent

1. Write its system prompt: `prompts/<name>.md`.
2. Define it: `agents/<name>.py` — a dict of `model` / `tools` / `system_prompt`
   / `name` / `description` (see `agents/exercise_recommender.py` or
   `agents/plan_assembler.py` for the shape), or a `build_<name>()` function
   if it's the top-level Supervisor rather than a dispatched sub-agent.
3. If it needs new tool functions, add them to `tools/` (or a new file there)
   — one `@tool`-decorated function per capability.
4. Register it: add to the `sub_agents` list passed to `build_supervisor()`
   (currently wired in `api/routes/plan.py`), and add its dispatch rules to
   `prompts/supervisor.md`.
5. If it needs to know when other agents have finished, use the existing
   `tools/memory.py` progress tracker (`init_plan_progress` /
   `mark_step_done` / `get_plan_progress`) rather than inventing a new
   mechanism — every agent already reads/writes through it.
