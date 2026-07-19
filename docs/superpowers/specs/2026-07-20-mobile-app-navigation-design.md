# Mobile App — Navigation, Screen Map & Localization Design

## Context

Tamreena is expanding from a single-flow web app (intake → InBody scan →
plan) into a React Native mobile app (iOS + Android) with a much larger
feature set: a Nutrition Agent, real-time computer-vision exercise form
correction, a post-workout feedback → plan-adjustment loop, progress
tracking via repeat InBody scans, user accounts, and subscriptions.

This spec covers the mobile app's **information architecture only** — the
tab structure, screen list, onboarding flow, and localization requirements.
It intentionally does NOT specify:
- The Auth & Accounts backend design
- The Subscription/IAP backend design
- The Nutrition Agent's inputs/outputs
- The CV Exercise-Correction system's technical architecture (on-device vs.
  server inference, model choice, per-exercise rule authoring)
- The Feedback → Adjustment agent's design

Each of those is its own sub-project with its own spec → plan → build
cycle, sequenced after this one. This doc exists so those sub-projects have
a settled screen/navigation contract to design against.

## Navigation structure

Bottom tab bar, 5 tabs: **Home, Workout, Nutrition, Progress, Profile**.
Plus a floating chat button (bottom-left, overlays the tab bar on every
main-tab screen) opening the app-guidance chatbot.

Visual design matches the existing Hevy-inspired light theme used on the
web frontend (`frontend/src/theme.css`, `frontend/src/base.css`) —
translated to React Native's styling, not a platform-native (Material/iOS
Human Interface) look.

## Pre-tab flow (onboarding)

Runs once, before the tab bar exists:

1. Splash screen
2. Sign Up / Log In — email+password, plus "Sign in with Apple" (required
   by App Store policy if any other social login is offered)
3. Intake form — same fields as the current web app: goal, days_per_week,
   experience, session_duration, injuries, priority, age, sleep_quality,
   job_type, current_program
4. InBody scan capture — reuses the existing quality-check → authenticity-
   check → upload flow (`frontend/src/components/CameraCapture.js` logic,
   ported to React Native camera APIs)
5. Processing — live agent progress, reusing the existing SSE-driven event
   stream (`agents/streaming.py`, `services/live_progress.py`)
6. First plan reveal → lands in the tab bar on Home

The free trial (see Monetization below) starts silently at signup — no
separate "start your trial" screen.

## Tabs

### Home
Today's workout preview, nutrition snapshot, trial/subscription status
banner, days-since-start + next-InBody-scan-due reminder, quick actions
(Start Today's Workout, View Full Plan).

### Workout
- This week's schedule, derived from the DAY MAP the Supervisor computes
- Today's session: exercise list with sets/reps/rest/RPE
- Per-exercise "Start Set" → launches the CV form-correction camera flow
  (user confirms/adjusts rep target, gets live correct/incorrect feedback
  + rep count) — detailed design deferred to the CV sub-project
- Workout history log
- Finishing a session auto-triggers the post-workout feedback prompt
  (see Feedback flow below)

### Nutrition
Displays the current plan from the Nutrition Agent, plus a
regenerate/adjust action. Exact inputs/outputs are deferred to the
Nutrition Agent's own design cycle — this screen just renders whatever
structured output that agent produces.

### Progress
- InBody scan timeline
- Scan-vs-scan comparison (SMM, body fat %, segmental lean mass,
  asymmetry flags resolved or not)
- "Time to next scan" reminder (monthly cadence)
- Start → current → goal journey view

### Profile
Account/intake info (editable), subscription management (routes to
OS-level subscription management — required by Apple/Google policy, not a
custom cancel flow), app settings (language, units, notifications),
support/help.

## Feedback flow

Auto-prompts immediately when the user marks today's workout done — a
screen asking about each exercise from that session before returning to
Home. If the response indicates an adjustment is needed, it calls the
plan-adjustment agent (design deferred to that sub-project).

## Floating chatbot

Bottom-left button, available on every main-tab screen (not during
onboarding). Opens the app-guidance RAG assistant — a separate, smaller
knowledge base scoped to "how to use Tamreena" (FAQ/help content), distinct
from the fitness-domain agents. Responds in whichever language the app UI
is currently set to (see Localization) — its purpose is navigational help,
not fitness content, so it follows the UI language rather than staying
fixed like plan/nutrition content.

## Monetization gating

Free trial of every feature at signup. Once the trial ends, any AI action
(plan regeneration, nutrition plan, CV correction, adjustments) that fails
an entitlement check routes to a single reusable paywall screen. The
paywall is also reachable proactively from Profile → Subscription.
Subscriptions are sold via Apple/Google in-app purchase (required by store
policy for this kind of digital content), most likely wired through
RevenueCat — confirmed as the payment approach, detailed backend design
deferred to the Subscriptions sub-project.

## Localization (English + Arabic)

- **App UI (chrome only)** — all navigation labels, buttons, form labels,
  static screen text — fully localized EN/AR.
- **Language selection** — auto-detected from device locale on first
  launch; manually overridable anytime in Profile > Settings.
- **RTL layout** — Arabic renders right-to-left: mirrored layout,
  right-aligned text, RTL-aware icons and flexbox direction
  (React Native's `I18nManager`).
- **AI-generated content is NOT translated.** Workout plans and nutrition
  plans always display in the language they were generated in
  (English — the exercise database and RAG corpus are English-only, see
  below), regardless of the app's current UI language. This applies even
  if a user switches app language after a plan already exists.
- **Exercise names** — English only for now. No `name_ar` column or
  bilingual exercise data in this phase; revisit as a fast-follow.
- **Chatbot** — the one exception to "content isn't translated": since its
  role is navigational help rather than fitness content, it responds in
  the current app UI language.

## Open questions / deferred to later sub-projects

- Auth & Accounts backend design (tokens, session model, password reset)
- Subscriptions/IAP backend design (RevenueCat wiring, entitlement checks,
  receipt validation, webhook handling)
- Nutrition Agent's inputs, outputs, and prompt design
- CV Exercise-Correction technical architecture (on-device vs. server
  inference, model choice, per-exercise rule authoring, rep-counting logic)
- Feedback → Plan-Adjustment agent design
- Whether/when Arabic exercise names get added
