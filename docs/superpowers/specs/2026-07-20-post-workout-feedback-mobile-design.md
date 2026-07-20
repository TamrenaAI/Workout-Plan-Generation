# Post-Workout Feedback — Mobile Flow Design

## Context

The backend side of the feedback → plan-adjustment loop already exists and
works: `POST /workouts/{session_id}/feedback` (`api/routes/workouts.py`)
records per-exercise feedback (`pipeline/workout_feedback.py`) and, if
anything was flagged `too_easy`, `too_hard`, or `pain`, dispatches the
standalone Plan Adjuster agent (`agents/plan_adjuster.py`, rules in
`prompts/plan_adjuster.md`) to revise the plan and return a plain-text
summary. None of that is new — it predates this spec and this spec makes no
changes to it.

What doesn't exist: any way for a user to actually trigger this from the
mobile app. `WorkoutScreen.tsx`'s "Start Set" button has no handler, there's
no "finish workout" action anywhere, and `mobile/src/api/` has no client for
this endpoint. This spec covers the mobile-side interaction only — the UI
that collects feedback and calls the existing endpoint.

This refines (does not contradict) the "Feedback flow" section of
`docs/superpowers/specs/2026-07-20-mobile-app-navigation-design.md`, which
described "a screen asking about each exercise from that session" at a
navigation-map level of detail, before the interaction itself was designed.
That earlier doc explicitly deferred "Feedback → Plan-Adjustment agent
design" as a separate sub-project — this spec deliberately keeps reusing
that agent as-is (see "Explicitly out of scope" below) and only designs the
mobile interaction in front of it.

## Goals

- Let a user close out a training day and, optionally, flag specific
  exercises that were too easy, too hard, or painful.
- Keep the common case (nothing wrong) to effectively zero extra taps.
- Reuse the existing backend contract exactly as it exists today — no
  backend, agent, or prompt changes.

## Non-goals / explicitly out of scope

- Any change to `agents/plan_adjuster.py` or `prompts/plan_adjuster.md` —
  confirmed to be reused as-is; a future redesign of the adjustment logic
  itself is a separate sub-project if it ever happens.
- Set-by-set logging, rest timers, or wiring up the existing (currently
  dead) "Start Set" button — that's the CV form-correction sub-project
  mentioned in the navigation design doc, unrelated to feedback.
- Any workout-occurrence/calendar tracking (i.e. knowing which real date
  "Day 1" was trained on a given week). The backend has no such concept
  today (`pipeline/workout_feedback.py` stores an unordered-by-week,
  append-only log per `session_id` + free-text `day_label`); this design
  doesn't need it because there's no "did you forget to give feedback"
  reminder state to track (see Flow below) — finishing a day always
  produces a submission immediately, so nothing is ever left pending.
- A feedback history view (e.g. "what did I say about Day 1 three weeks
  ago"). Only the Plan Adjuster agent reads feedback history back today;
  no mobile screen surfaces it. Flagged as a possible fast-follow, not
  built here.

## Flow

The exercise-browsing view (`WorkoutScreen.tsx`, today) never carries any
feedback UI — no icons, no per-row forms. The entire form lives on one
dedicated feedback screen, reached only via "Finish Workout." Per-exercise
flagging on that screen is optional; submitting is the one mandatory action,
and it always sends something — defaulting to "everything was fine" for any
exercise the user didn't touch.

This was a deliberate revision from an earlier version of this design that
put a flag affordance + inline expanding panel directly on each exercise
card in `WorkoutScreen.tsx`. That made the primary browsing list double as
a form, which is why it's called out here explicitly rather than left as
silent history.

```
WorkoutScreen — viewing a day's exercise list (unchanged from today, plus
one addition)
  [Finish Workout] — new button below the exercise list. Tapping it swaps
  in the feedback screen (see below) — a local view-state toggle, the same
  pattern OnboardingFlow.tsx already uses for its step sequence (a `step`
  useState switched between step components), not a new stack navigator.
  TabNavigator.tsx has no per-tab stack today and none is needed here.

WorkoutFeedbackScreen (new) — "How did today go?"
  Every exercise from the day is listed with:
    - 3-way pill group: Too Easy / Just Right / Too Hard (default: Just Right)
    - A separate "Painful" pill (off by default); turning it on reveals an
      optional short note field ("What hurt, and where?") for that exercise
  Rows never touched keep the Pydantic-matching defaults:
    completed=true, difficulty="just_right", pain=false

  [Submit Feedback] — always submits whatever's on screen
    -> POST /workouts/{session_id}/feedback
       day_label = activeSection.title (e.g. "Day 1 — Push: Chest Focus")
       exercises = the full list (flagged rows + defaulted rows)

    -> nothing flagged: fast response (no agent call server-side, since
       needs_adjustment() short-circuits) -> return to WorkoutScreen with a
       brief success toast
    -> something flagged: this call blocks on a real Plan Adjuster run
       (the route awaits agents/plan_adjuster.py synchronously today, no
       SSE/background task like /generate-plan has) -> show a spinner
       ("Adjusting your plan…") until the response arrives, then return to
       WorkoutScreen and show the returned `summary` in a confirmation card
```

A back action on the feedback screen returns to WorkoutScreen without
submitting anything — no partial state is ever sent.

## Exact payload shapes

Matches `WorkoutFeedbackRequest`/`ExerciseFeedback` in
`api/routes/workouts.py` exactly — no schema changes.

**Nothing flagged:**
```json
{
  "day_label": "Day 1 — Push: Chest Focus",
  "exercises": [
    { "name": "Incline DB Press", "completed": true, "difficulty": "just_right", "pain": false },
    { "name": "Cable Fly", "completed": true, "difficulty": "just_right", "pain": false }
  ]
}
```
Response: `{ "feedback_recorded": true, "adjustment_triggered": false, "summary": null }`

**One exercise flagged painful, one too easy:**
```json
{
  "day_label": "Day 1 — Push: Chest Focus",
  "exercises": [
    { "name": "Incline DB Press", "completed": true, "difficulty": "just_right", "pain": true, "note": "sharp pain in left shoulder at the top of the rep" },
    { "name": "Cable Fly", "completed": true, "difficulty": "too_easy", "pain": false }
  ]
}
```
Response includes a non-null `summary` (the adjuster's second-person
write-up) — shown in a confirmation card.

**Field sourcing (must match verbatim for the agent to find the exercise):**
- `day_label` = `activeSection.title`, from `useLatestPlan()`'s parsed plan
  sections (`mobile/src/lib/parsePlan.ts`) — the same string already shown
  as the screen's section heading.
- `exercise.name` = the exact strings already produced by
  `exercisesFromDay()` in `WorkoutScreen.tsx` (pulled from the plan
  markdown table's "Exercise" column) — reusing the same parsed values the
  screen already displays guarantees the names match what's in plan
  memory, which `prompts/plan_adjuster.md` requires ("if the feedback
  references an exercise name that isn't found anywhere in the plan
  memory, do not guess").
- `completed` — exposed as a "Skipped" checkbox alongside the 3-way
  toggle (sets `completed: false`). Per the adjuster's own rules this
  alone never triggers an adjustment (adherence signal only), but it's
  zero extra schema cost to capture since the field already exists.

## Loading state

`POST /workouts/{session_id}/feedback` is synchronous when an adjustment is
needed — `api/routes/workouts.py` awaits `agents/plan_adjuster.py`'s full
`deepagents` run (`recursion_limit=50`) directly inside the request
handler. That can plausibly take anywhere from a few seconds to over a
minute. The submit action needs a real loading state ("Adjusting your
plan…"), not just a toast, for any submission that flags something. This
mirrors `ProcessingStep.tsx`'s spinner-and-label pattern, but note this
endpoint has no SSE stream the way `/generate-plan` does — moving it to a
background-task + stream pattern is a possible future improvement, not
built here.

## File-by-file changes

| File | Change |
|---|---|
| `mobile/src/api/workouts.ts` | **New.** `submitWorkoutFeedback(sessionId, dayLabel, exercises)` calling `apiFetch('/workouts/{id}/feedback', { method: 'POST', body })`, matching the style of `mobile/src/api/plan.ts`. |
| `mobile/src/screens/WorkoutScreen.tsx` | Add a `view` state, either `'list'` or `'feedback'` (default `'list'`), and a "Finish Workout" button below the exercise list that sets it to `'feedback'`. When `'feedback'`, renders `WorkoutFeedbackScreen` in place of the list — mirrors `OnboardingFlow.tsx`'s `step` state pattern. No per-exercise UI is added to the list itself. |
| `mobile/src/screens/WorkoutFeedbackScreen.tsx` | **New.** The dedicated feedback screen: renders every exercise from the active day with its 3-way pill group + pain pill + conditional note field, holds the in-progress feedback as local state, and owns the submit/loading/summary states. Takes the day's exercises + `onDone`/`onBack` callbacks as props — it doesn't fetch anything itself. |
| Backend (`api/routes/workouts.py`, `agents/plan_adjuster.py`, `prompts/plan_adjuster.md`, `pipeline/workout_feedback.py`) | **No changes.** |

## Error handling

- Network/API failure on submit: surface the error (matching the
  `ApiError`/error-card pattern already used elsewhere, e.g.
  `ProcessingStep.tsx`) and let the user retry — the exercise-level flags
  they already set stay in local component state, not lost.
- `adjustment_triggered: false` (the common case): a lightweight success
  toast, no confirmation card needed.

## Open questions / deferred

- Whether `/workouts/{session_id}/feedback` should eventually move to the
  same background-task + SSE pattern `/generate-plan` uses, for
  consistency and to avoid a long blocking request on mobile networks.
- A feedback-history view on mobile (see Non-goals).
- Any future redesign of the Plan Adjuster's own adjustment logic — out of
  scope here by explicit choice; reused as-is.
