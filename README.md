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
  models.py                  ← users table (SQLite, same data/tamreena.db) + get_or_create_user_by_google
  google_oauth.py             ← verifies Google ID tokens from the mobile app's native sign-in
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
  routes/auth.py               ← POST /auth/google, GET /auth/me, POST /auth/dev-login (see below)
  routes/plan.py               ← POST /validate-image, POST /plan (aliased as /generate-plan, requires
                                  login), GET /generate-plan/stream/{id} (ownership-checked),
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

mobile/                          ← React Native (Expo + TypeScript) app — the actual product going
                                    forward. See mobile/README (Expo default) for run instructions and
                                    docs/superpowers/specs/2026-07-20-mobile-app-navigation-design.md
                                    for the design this implements.
  App.tsx                        ← AuthProvider + NavigationContainer; shows LoginScreen, then
                                    OnboardingFlow if the signed-in user has zero sessions yet,
                                    else TabNavigator
  src/config.ts                  ← API_BASE_URL / GOOGLE_WEB_CLIENT_ID (see .env.example)
  src/api/client.ts               ← apiFetch() (JSON) / apiFetchForm() (multipart, no Content-Type
                                    override) — both attach the session JWT, throw ApiError on failure
  src/api/{auth,sessions,progress,plan}.ts ← typed wrappers per backend resource, incl.
                                    validateImage()/generatePlan() (multipart uploads)
  src/onboarding/                 ← linear wizard mirroring frontend/'s intake->capture->processing
                                    flow (no back-navigation, matching the web app's own convention):
    OnboardingFlow.tsx             ← step state machine, accumulates IntakeData across steps
    steps/IntakeStep{1,2,3}.tsx     ← goal+days / experience+duration / optional details — PillSelect
                                    options are constrained to values the backend already validates
    steps/CaptureStep.tsx           ← expo-image-picker (camera or library — works in Expo Go,
                                    unlike Google Sign-In) + POST /validate-image, retry on failure
    steps/ProcessingStep.tsx        ← POST /generate-plan then live progress via react-native-sse
                                    (pure-JS EventSource polyfill — RN has no built-in EventSource)
  src/auth/AuthContext.tsx        ← Google Sign-In (native, NOT Expo Go-compatible — see below),
                                    session persistence via src/lib/storage.ts
  src/lib/storage.ts               ← wraps expo-secure-store with a localStorage fallback on web
                                    (SecureStore has no web implementation) — see auth note below
  src/lib/parsePlan.ts            ← ports frontend/src/pages/plan.js's markdown parser (headings/
                                    tables/notes/lists) to a typed block structure — RN has no raw-
                                    HTML rendering. Groups blocks by heading into PlanSections; a
                                    "Day {N}" heading sets dayNumber (backend has no real-calendar-
                                    date mapping for training days, so screens let the user pick one)
  src/hooks/useLatestPlan.ts       ← shared by Home/Workout: fetches the most recent session's
                                    persisted plan (GET /sessions/{id}/plan) and parses it once
  src/theme.ts                   ← design tokens ported from frontend/src/theme.css / design-system.md
  src/components/                ← Card, Badge, PrimaryButton/GhostButton, StatTile, ChatButton,
                                    StepHeader, PillSelect, TextField — mirror the web app's
                                    .t-card/.t-badge/.pill/.t-input/etc. classes
  src/navigation/TabNavigator.tsx ← bottom tabs (Home/Workout/Nutrition/Progress/Profile) + floating
                                    ChatButton overlay
  src/screens/                   ← LoginScreen (real), Profile (real user + logout), Progress (real
                                    scan history/comparison), Workout (real session history + real,
                                    tappable day-strip and per-exercise cards parsed from the actual
                                    plan), Home (real "Next Workout" summary + real days-since-signup).
                                    Nutrition and the trial/subscription badge stay mock — Nutrition
                                    Agent integration is on hold, Subscriptions/IAP isn't built yet.
```

**Mobile auth note:** `@react-native-google-signin/google-signin` requires custom native
code and does NOT run in Expo Go. Testing the actual "Sign in with Google" button needs a
dev-client build (`eas build --profile development`, or a local `expo run:android`/`expo
run:ios` if you set up Android Studio/Xcode) plus real Google Cloud OAuth credentials — a
"Web application" client ID for `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` / the backend's
`GOOGLE_OAUTH_CLIENT_ID` (same value, both must match), and platform-specific client IDs
(with Android SHA-1 fingerprints) wired into the `@react-native-google-signin/google-signin`
config plugin in `app.json`. `tsc --noEmit` and `expo export` are verified clean, but the
sign-in flow itself is unverified until that build exists.

**Previewing without a phone or a build:** `cd mobile && npx expo start --web` opens the
app in a regular browser tab on the dev machine — no phone, no Expo Go, no EAS build.
Everything renders (react-native-web + react-dom + @expo/metro-runtime are installed);
the only thing that won't work is "Sign in with Google" (shows a clean error, same as in
Expo Go — no native module on web either). `src/lib/storage.ts` exists specifically to
make this possible: `expo-secure-store` (used to persist the session token) has no web
implementation at all — confirmed against Expo's own SDK 57 docs, not assumed — so this
wraps it with a `localStorage` fallback on `Platform.OS === 'web'`. Session persistence
via this fallback is real on web too, just less protected than the native OS keychain
(acceptable — that's inherent to any web app's storage, not a downgrade this introduced).

**Getting past the login wall without a build:** since every backend endpoint requires a
real session JWT, and neither web preview nor Expo Go can produce one via real Google
Sign-In, there is a **dev-only bypass**: `POST /auth/dev-login` mints a session for a
fixed test account (`dev@tamreena.local`) with no credential at all. It's disabled by
default — returns a plain 404, not even confirming it exists — unless the server operator
sets `ALLOW_DEV_LOGIN=true` in `.env`. **Never set that true anywhere but a local dev
machine** — it lets anyone with network access to that server sign in with nothing. On
the client, the "Continue as Test User (dev only)" button on `LoginScreen` only renders
when React Native's `__DEV__` global is true (always false in a release build), so it's a
two-layer gate: client-side visibility AND server-side opt-in, either of which alone
would block it in production.

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

## Retrieval (RAG) — hardcoded stub, by design at this stage

`tools/rag.py` returns static training principles and muscle-specific notes
per muscle group. **This is intentional and unchanged from the notebooks** —
the real pipeline (two Qdrant collections, `BAAI/bge-m3` dense + BM25 sparse
hybrid search fused with RRF, reranked locally with `BAAI/bge-reranker-v2-m3`)
is designed in `tamrena_architecture_2.md` Section 7 but is pending the RAG
team's ingestion pipeline. Swapping the stub for the real implementation
should only touch `tools/rag.py` — `search_rag(muscle_group, query)` is the
only contract the rest of the system depends on.

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
| RAG (Qdrant hybrid search) | Hardcoded stub (`tools/rag.py`) — real pipeline pending RAG team |
| FastAPI endpoints (`/health`, `/validate-image`, `/plan`, `/generate-plan`) | Implemented (`api/`) |
| Frontend (vanilla JS/CSS, mounted at `/`) | Implemented (`frontend/`, see `FRONTEND.md`) |
| `/ingest` (RAG document ingestion) | Not built — no ingestion pipeline exists yet since RAG is a stub |
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
