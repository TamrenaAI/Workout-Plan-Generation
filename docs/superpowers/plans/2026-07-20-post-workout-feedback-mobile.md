# Post-Workout Feedback (Mobile) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a mobile user close out a training day, optionally flag specific exercises as too easy/too hard/painful, and have that trigger the existing Plan Adjuster agent — reusing the backend exactly as it is today.

**Architecture:** A new dedicated screen (`WorkoutFeedbackScreen`) swapped in by `WorkoutScreen` via local view-state (the same pattern `OnboardingFlow.tsx` already uses for its step sequence — no new navigator). The exercise-browsing list stays completely untouched; all form UI lives only on the new screen. One new API client function calls the existing `POST /workouts/{session_id}/feedback`.

**Tech Stack:** React Native + Expo (TypeScript), existing `apiFetch` client, existing `PillSelect`/`Card`/`Badge`/`TextField`/`GhostButton` components.

## Global Constraints

- No backend changes of any kind — `api/routes/workouts.py`, `agents/plan_adjuster.py`, `prompts/plan_adjuster.md`, and `pipeline/workout_feedback.py` are reused exactly as they are today (spec's explicit non-goal).
- Payload must match `WorkoutFeedbackRequest`/`ExerciseFeedback` exactly: `{ day_label: string, exercises: [{ name, completed, difficulty: "too_easy"|"just_right"|"too_hard", pain, note? }] }`.
- `day_label` must be the exact section title string already shown on screen (e.g. `"Day 1 — Push: Chest Focus"`); `exercise.name` must be the exact string already parsed from the plan markdown table — both must match plan memory verbatim or the Plan Adjuster refuses to act on them (spec's "Field sourcing" section).
- No new npm dependencies. This codebase has **no test infrastructure in `mobile/`** at all (confirmed: zero `.test.*`/`__tests__` files under `mobile/src`, no test runner in `package.json`/devDependencies) — matching that established convention, verification in this plan is manual (`npm run web` + concrete click-throughs), not automated tests. Do not add Jest/RNTL as a side effect of this feature.
- Reuse existing components before writing new UI primitives: `PillSelect`, `Card`, `Badge`, `TextField`, `GhostButton`, `PrimaryButton` — do not hand-roll new pill/badge/card styling (this was tried and explicitly rejected during design review for not matching the app's real components).
- Known limitation, not fixed by this plan: `tools/memory.py`'s `read_weekly_schedule()` only recognizes `## Weekly Schedule`/`## Full Workout Plan` headings. The Plan Adjuster writes its change under a `## Plan Adjustment — {day_label}` heading, which `find_last_schedule_marker` does not match — so `GET /sessions/{id}/plan` keeps returning the **original**, unadjusted schedule text even after a successful adjustment. The confirmation card's `summary` text is the only place the change is visible today; the exercise list itself will not show the swapped/adjusted exercise. This is a pre-existing backend behavior, out of scope per the spec's "no backend changes" constraint — do not attempt to fix it here.

---

## File Structure

| File | Responsibility |
|---|---|
| `mobile/src/components/PillSelect.tsx` | *Modify.* Add an optional `variant` prop (`'accent'` default, `'danger'`) so the pain toggle can render in the app's existing danger color instead of only ever blue. Backward compatible — every existing call site is unaffected. |
| `mobile/src/api/workouts.ts` | *New.* One function, `submitWorkoutFeedback`, calling the existing feedback endpoint. Mirrors `mobile/src/api/plan.ts`'s style. |
| `mobile/src/hooks/useLatestPlan.ts` | *Modify.* Expose a `reload()` function so `WorkoutScreen` can refresh after returning from feedback. |
| `mobile/src/screens/WorkoutFeedbackScreen.tsx` | *New.* The dedicated feedback screen — per-exercise pill selections, conditional note field, submit/loading/error states. Pure props in, callback out; does no data fetching of its own. |
| `mobile/src/screens/WorkoutScreen.tsx` | *Modify.* Add a `view` state (`'list' \| 'feedback'`) and a "Finish Workout" button. Renders `WorkoutFeedbackScreen` in place of the list when `view === 'feedback'`. Shows a confirmation card or a system alert when returning, depending on whether an adjustment ran. |

---

### Task 1: `PillSelect` danger variant

**Files:**
- Modify: `mobile/src/components/PillSelect.tsx`

**Interfaces:**
- Produces: `PillSelect<T>({ label, options, value, onChange, variant? })` where `variant?: 'accent' | 'danger'` (default `'accent'`) — every later task that renders a pain toggle uses `variant="danger"`.

- [ ] **Step 1: Replace the file with the variant-aware version**

Read the current file first (`mobile/src/components/PillSelect.tsx`) to confirm it still matches this plan's assumption before editing — if `pillActive`/`pillTextActive` style names differ, adjust the replacement below to match the real names instead of guessing.

```tsx
import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';

import { colors, radii } from '../theme';

type Variant = 'accent' | 'danger';

/** Mirrors the web app's .pill-group/.pill pattern. Single-select — value
 * is one of `options[].value`, or null if nothing's picked yet.
 * `variant="danger"` renders the active pill in the app's danger color
 * instead of the default accent blue (used for the pain toggle — see
 * WorkoutFeedbackScreen.tsx). Every existing call site omits `variant`
 * and is unaffected. */
export function PillSelect<T extends string>({
  label,
  options,
  value,
  onChange,
  variant = 'accent',
}: {
  label: string;
  options: { label: string; value: T }[];
  value: T | null;
  onChange: (value: T) => void;
  variant?: Variant;
}) {
  const activePillStyle = variant === 'danger' ? styles.pillActiveDanger : styles.pillActive;
  const activeTextStyle = variant === 'danger' ? styles.pillTextActiveDanger : styles.pillTextActive;

  return (
    <View style={styles.container}>
      <Text style={styles.label}>{label}</Text>
      <View style={styles.group}>
        {options.map((opt) => {
          const active = opt.value === value;
          return (
            <TouchableOpacity
              key={opt.value}
              style={[styles.pill, active && activePillStyle]}
              activeOpacity={0.7}
              onPress={() => onChange(opt.value)}
            >
              <Text style={[styles.pillText, active && activeTextStyle]}>{opt.label}</Text>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginBottom: 24 },
  label: { fontSize: 13, color: colors.textMuted, marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: '600' },
  group: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  pill: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: radii.badge,
    borderWidth: 1,
    borderColor: colors.borderDefault,
    backgroundColor: colors.bgInput,
  },
  pillActive: { borderColor: colors.accentPrimary, backgroundColor: colors.accentTint },
  pillActiveDanger: { borderColor: colors.danger, backgroundColor: colors.bgInput },
  pillText: { fontSize: 13, fontWeight: '500', color: colors.textSecondary },
  pillTextActive: { color: colors.accentPrimary, fontWeight: '600' },
  pillTextActiveDanger: { color: colors.danger, fontWeight: '700' },
});
```

- [ ] **Step 2: Typecheck**

Run: `cd mobile && npx tsc --noEmit`
Expected: no new errors. (There is no test runner to invoke here — see Global Constraints.)

- [ ] **Step 3: Manually verify existing call sites are unaffected**

Run: `cd mobile && npm run web`
Open the onboarding intake flow (Goal/Experience step) in the browser preview. Confirm the existing pill selectors still render and behave exactly as before (blue tint on the selected option) — this task must not visibly change anything on any screen that doesn't pass `variant="danger"`.

- [ ] **Step 4: Commit**

```bash
git add mobile/src/components/PillSelect.tsx
git commit -m "Add optional danger variant to PillSelect for the pain toggle"
```

---

### Task 2: Workouts API client

**Files:**
- Create: `mobile/src/api/workouts.ts`

**Interfaces:**
- Consumes: `apiFetch<T>(path, options)` from `mobile/src/api/client.ts` (signature: `apiFetch<T>(path: string, options?: Omit<RequestInit,'body'> & {body?: unknown}): Promise<T>`).
- Produces: `Difficulty` type, `ExerciseFeedbackInput` interface, `WorkoutFeedbackResult` interface, `submitWorkoutFeedback(sessionId, dayLabel, exercises): Promise<WorkoutFeedbackResult>` — consumed by Task 4's `WorkoutFeedbackScreen`.

- [ ] **Step 1: Create the file**

```ts
import { apiFetch } from './client';

export type Difficulty = 'too_easy' | 'just_right' | 'too_hard';

export interface ExerciseFeedbackInput {
  name: string;
  completed: boolean;
  difficulty: Difficulty;
  pain: boolean;
  note?: string;
}

export interface WorkoutFeedbackResult {
  feedback_recorded: boolean;
  adjustment_triggered: boolean;
  summary: string | null;
}

/** Calls the existing POST /workouts/{session_id}/feedback (api/routes/workouts.py) —
 * no backend changes accompany this client. If nothing in `exercises` is flagged
 * (all just_right/no pain), the backend responds fast with adjustment_triggered:
 * false and no agent runs; otherwise this call blocks on a real Plan Adjuster
 * run and can take from a few seconds to over a minute. */
export function submitWorkoutFeedback(
  sessionId: string,
  dayLabel: string,
  exercises: ExerciseFeedbackInput[],
): Promise<WorkoutFeedbackResult> {
  return apiFetch<WorkoutFeedbackResult>(`/workouts/${sessionId}/feedback`, {
    method: 'POST',
    body: { day_label: dayLabel, exercises },
  });
}
```

- [ ] **Step 2: Typecheck**

Run: `cd mobile && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Manually verify against the running backend**

Start the backend (`python main.py` from the repo root, or however it's currently run in this environment) and confirm `/workouts/{session_id}/feedback` is registered:

Run: `curl -s -X POST http://localhost:8001/workouts/does-not-exist/feedback -H "Content-Type: application/json" -d "{\"day_label\":\"x\",\"exercises\":[]}"`
Expected: a 401 (missing auth) or 404 (unknown session), **not** a 404 "Not Found" for the route itself / a connection error — confirms the route exists and this client is pointed at the right path and method. Exact status code doesn't matter here, only that it's a real application-level response, not "no such route."

- [ ] **Step 4: Commit**

```bash
git add mobile/src/api/workouts.ts
git commit -m "Add mobile API client for POST /workouts/{session_id}/feedback"
```

---

### Task 3: Expose `reload()` from `useLatestPlan`

**Files:**
- Modify: `mobile/src/hooks/useLatestPlan.ts`

**Interfaces:**
- Produces: the hook's return type gains `reload: () => void`, callable any time after the initial mount to re-fetch — consumed by Task 5's `WorkoutScreen`.

- [ ] **Step 1: Replace the file**

```ts
import { useCallback, useEffect, useState } from 'react';

import { ApiError } from '../api/client';
import { fetchSessionPlan } from '../api/plan';
import { fetchSessions, PlanSession } from '../api/sessions';
import { parsePlanMarkdown, PlanSection } from '../lib/parsePlan';

interface LatestPlanState {
  isLoading: boolean;
  error: string | null;
  session: PlanSession | null;
  status: 'ready' | 'pending' | null;
  /** Day sections only (dayNumber !== null), in the order they appear in the plan. */
  days: PlanSection[];
}

const INITIAL_STATE: LatestPlanState = {
  isLoading: true,
  error: null,
  session: null,
  status: null,
  days: [],
};

/** Shared by HomeScreen and WorkoutScreen — both need "the current plan's
 * training days," just for different amounts of detail. Fetches the most
 * recently generated session and parses its persisted weekly schedule
 * (GET /sessions/{id}/plan) rather than duplicating this fetch+parse in
 * each screen. Exposes `reload` so a caller can re-fetch after an action
 * that might have changed server state (e.g. WorkoutScreen after
 * submitting post-workout feedback) — see Global Constraints for why the
 * re-fetched schedule may still look unchanged even after a real
 * adjustment ran. */
export function useLatestPlan(): LatestPlanState & { reload: () => void } {
  const [state, setState] = useState<LatestPlanState>(INITIAL_STATE);

  const load = useCallback(async () => {
    try {
      const sessions = await fetchSessions();
      if (sessions.length === 0) {
        setState({ ...INITIAL_STATE, isLoading: false });
        return;
      }

      const latest = sessions[0];
      const response = await fetchSessionPlan(latest.session_id);
      const days = response.plan
        ? parsePlanMarkdown(response.plan).filter((s) => s.dayNumber !== null)
        : [];

      setState({ isLoading: false, error: null, session: latest, status: response.status, days });
    } catch (err) {
      setState({
        ...INITIAL_STATE,
        isLoading: false,
        error: err instanceof ApiError ? err.message : 'Could not load your plan.',
      });
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!cancelled) await load();
    })();
    return () => {
      cancelled = true;
    };
  }, [load]);

  return { ...state, reload: load };
}
```

Note: the cancellation guard is looser here than the original (it no longer prevents a `setState` after unmount mid-flight on the very first load), which matches how `reload()` itself has no cancellation either — acceptable for this hook's actual usage (screens that call it stay mounted for the app's lifetime inside the tab navigator).

- [ ] **Step 2: Typecheck**

Run: `cd mobile && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Manually verify existing consumers are unaffected**

Run: `cd mobile && npm run web`
Open the Home tab and the Workout tab. Both must still load and display the current plan exactly as before — this task only adds a new returned field, it must not change existing behavior.

- [ ] **Step 4: Commit**

```bash
git add mobile/src/hooks/useLatestPlan.ts
git commit -m "Expose reload() from useLatestPlan"
```

---

### Task 4: `WorkoutFeedbackScreen`

**Files:**
- Create: `mobile/src/screens/WorkoutFeedbackScreen.tsx`

**Interfaces:**
- Consumes: `submitWorkoutFeedback` (Task 2), `PillSelect` with `variant` (Task 1), and existing `Card` (`mobile/src/components/Card.tsx`), `TextField` (`mobile/src/components/TextField.tsx`), `PrimaryButton`/`GhostButton` (`mobile/src/components/Buttons.tsx`), `colors`/`spacing` (`mobile/src/theme.ts`), `ApiError` (`mobile/src/api/client.ts`).
- Produces: `WorkoutFeedbackScreenProps` (below) and the exported `WorkoutFeedbackScreen` component — consumed by Task 5's `WorkoutScreen`.

```ts
export interface FeedbackExercise {
  name: string;
  sets: string;
}

export interface WorkoutFeedbackScreenProps {
  sessionId: string;
  dayLabel: string;
  exercises: FeedbackExercise[];
  onBack: () => void;
  onDone: (result: { adjustmentTriggered: boolean; summary: string | null }) => void;
}
```

- [ ] **Step 1: Create the file**

```tsx
import React, { useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ApiError } from '../api/client';
import { Difficulty, ExerciseFeedbackInput, submitWorkoutFeedback } from '../api/workouts';
import { Card } from '../components/Card';
import { PillSelect } from '../components/PillSelect';
import { GhostButton, PrimaryButton } from '../components/Buttons';
import { TextField } from '../components/TextField';
import { colors, spacing } from '../theme';

export interface FeedbackExercise {
  name: string;
  sets: string;
}

export interface WorkoutFeedbackScreenProps {
  sessionId: string;
  dayLabel: string;
  exercises: FeedbackExercise[];
  onBack: () => void;
  onDone: (result: { adjustmentTriggered: boolean; summary: string | null }) => void;
}

interface RowState {
  difficulty: Difficulty;
  pain: boolean;
  note: string;
  completed: boolean;
}

const DIFFICULTY_OPTIONS: { label: string; value: Difficulty }[] = [
  { label: 'Too Easy', value: 'too_easy' },
  { label: 'Just Right', value: 'just_right' },
  { label: 'Too Hard', value: 'too_hard' },
];

const PAIN_OPTIONS: { label: string; value: 'no' | 'yes' }[] = [
  { label: 'No pain', value: 'no' },
  { label: 'Painful', value: 'yes' },
];

const DEFAULT_ROW: RowState = { difficulty: 'just_right', pain: false, note: '', completed: true };

/**
 * Dedicated screen for post-workout feedback — deliberately NOT inline on
 * WorkoutScreen (see docs/superpowers/specs/2026-07-20-post-workout-feedback-mobile-design.md's
 * "Flow" section for why an earlier per-exercise-inline version was rejected).
 * Pure props in, callback out — this component never fetches session/plan
 * data itself.
 */
export function WorkoutFeedbackScreen({ sessionId, dayLabel, exercises, onBack, onDone }: WorkoutFeedbackScreenProps) {
  const [rows, setRows] = useState<RowState[]>(() => exercises.map(() => ({ ...DEFAULT_ROW })));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateRow(index: number, patch: Partial<RowState>) {
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const payload: ExerciseFeedbackInput[] = exercises.map((ex, i) => {
        const row = rows[i];
        const entry: ExerciseFeedbackInput = {
          name: ex.name,
          completed: row.completed,
          difficulty: row.difficulty,
          pain: row.pain,
        };
        if (row.pain && row.note.trim()) entry.note = row.note.trim();
        return entry;
      });

      const result = await submitWorkoutFeedback(sessionId, dayLabel, payload);
      onDone({ adjustmentTriggered: result.adjustment_triggered, summary: result.summary });
    } catch (err) {
      setSubmitting(false);
      setError(err instanceof ApiError ? err.message : 'Could not submit feedback — try again.');
    }
  }

  if (submitting) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={colors.accentPrimary} />
          <Text style={styles.loadingLabel}>Adjusting your plan…</Text>
          <Text style={styles.loadingHint}>This can take a moment if anything needs adjusting.</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <TouchableOpacity style={styles.backBtn} onPress={onBack} activeOpacity={0.7}>
            <Text style={styles.backBtnText}>‹</Text>
          </TouchableOpacity>
          <Text style={styles.title}>How did today go?</Text>
        </View>
        <Text style={styles.subtitle}>{dayLabel} · leave anything untouched to mark it fine</Text>

        {error ? (
          <Card style={styles.errorCard}>
            <Text style={styles.errorText}>{error}</Text>
          </Card>
        ) : null}

        {exercises.map((ex, i) => {
          const row = rows[i];
          return (
            <Card key={`${ex.name}-${i}`}>
              <Text style={styles.exerciseName}>
                {ex.name} <Text style={styles.exerciseSets}>· {ex.sets}</Text>
              </Text>
              <PillSelect
                label="How did it feel?"
                options={DIFFICULTY_OPTIONS}
                value={row.difficulty}
                onChange={(difficulty) => updateRow(i, { difficulty })}
              />
              <PillSelect
                label="Anything hurt?"
                variant="danger"
                options={PAIN_OPTIONS}
                value={row.pain ? 'yes' : 'no'}
                onChange={(v) => updateRow(i, { pain: v === 'yes' })}
              />
              {row.pain ? (
                <TextField
                  label="Note (optional)"
                  placeholder="What hurt, and where?"
                  value={row.note}
                  onChangeText={(note) => updateRow(i, { note })}
                  multiline
                  numberOfLines={2}
                />
              ) : null}
              <TouchableOpacity
                style={styles.skipRow}
                onPress={() => updateRow(i, { completed: !row.completed })}
                activeOpacity={0.7}
              >
                <View style={[styles.checkbox, !row.completed && styles.checkboxChecked]} />
                <Text style={styles.skipLabel}>I skipped this exercise</Text>
              </TouchableOpacity>
            </Card>
          );
        })}

        <PrimaryButton label="Submit Feedback" onPress={handleSubmit} style={{ marginTop: spacing.gapCards }} />
        <GhostButton label="Back" onPress={onBack} style={{ marginTop: spacing.gapInner, marginBottom: 20 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.bgPrimary },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: spacing.screenPad },
  loadingLabel: { fontSize: 15, fontWeight: '600', color: colors.textPrimary, marginTop: 20, textAlign: 'center' },
  loadingHint: { fontSize: 12, color: colors.textMuted, marginTop: 8, textAlign: 'center' },
  content: { padding: spacing.screenPad, paddingBottom: 60 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 4 },
  backBtn: {
    width: 30, height: 30, borderRadius: 10, borderWidth: 1, borderColor: colors.borderDefault,
    backgroundColor: colors.bgCardAlt, alignItems: 'center', justifyContent: 'center',
  },
  backBtnText: { fontSize: 18, color: colors.textPrimary, marginTop: -2 },
  title: { fontSize: 20, fontWeight: '700', color: colors.textPrimary },
  subtitle: { fontSize: 12.5, color: colors.textMuted, marginBottom: 16 },
  errorCard: { borderColor: colors.danger },
  errorText: { fontSize: 13, color: colors.danger },
  exerciseName: { fontSize: 15, fontWeight: '600', color: colors.textPrimary, marginBottom: 14 },
  exerciseSets: { fontSize: 13, fontWeight: '400', color: colors.textMuted },
  skipRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 },
  checkbox: { width: 16, height: 16, borderRadius: 4, borderWidth: 1.5, borderColor: colors.borderDefault },
  checkboxChecked: { backgroundColor: colors.accentPrimary, borderColor: colors.accentPrimary },
  skipLabel: { fontSize: 12, color: colors.textSecondary },
});
```

- [ ] **Step 2: Typecheck**

Run: `cd mobile && npx tsc --noEmit`
Expected: no errors. If `TextField`'s props type doesn't accept `multiline`/`numberOfLines`, open `mobile/src/components/TextField.tsx` and confirm it spreads `...rest: TextInputProps` (it does, per the file read during design) — those are standard `TextInputProps` fields, no change needed there.

- [ ] **Step 3: Commit**

```bash
git add mobile/src/screens/WorkoutFeedbackScreen.tsx
git commit -m "Add WorkoutFeedbackScreen: dedicated post-workout feedback form"
```

(Manual, end-to-end verification of this screen happens in Task 5, once `WorkoutScreen` actually renders it with real data — there's no value in mounting it standalone first.)

---

### Task 5: Wire it up in `WorkoutScreen`

**Files:**
- Modify: `mobile/src/screens/WorkoutScreen.tsx`

**Interfaces:**
- Consumes: `WorkoutFeedbackScreen` + `WorkoutFeedbackScreenProps`/`FeedbackExercise` (Task 4), `reload` from `useLatestPlan()` (Task 3), `Badge` (`mobile/src/components/Badge.tsx`, not previously imported in this file).

- [ ] **Step 1: Add the new imports and view-state**

In `mobile/src/screens/WorkoutScreen.tsx`, add to the existing import block:

```tsx
import { Alert } from 'react-native';
```
(add `Alert` to the existing `import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';` line rather than a second import statement)

```tsx
import { Badge } from '../components/Badge';
import { FeedbackExercise, WorkoutFeedbackScreen } from './WorkoutFeedbackScreen';
```

Inside the `WorkoutScreen` function body, alongside the existing `useState` calls, add:

```tsx
const [view, setView] = useState<'list' | 'feedback'>('list');
const [confirmation, setConfirmation] = useState<{ summary: string } | null>(null);
```

And destructure `reload` from the existing hook call:

```tsx
const { isLoading, error, status, days, reload } = useLatestPlan();
```

- [ ] **Step 2: Add the feedback-screen branch and the done handler**

In the original file, hook/state declarations run in this order: `useLatestPlan()`, `selectedDay`, an effect, `activeSection`/`exercises`, then `sessions`/`historyError` and the effect that calls `fetchSessions()` — **only after all of that** does the file reach its final `return (`. The new code below reads `sessions`, so it must go after the `fetchSessions()` effect and before that final `return (` — not right after the `exercises` line (inserting it earlier would reference `sessions` before its `const` declaration and fail to compile).

Immediately before the final `return (` that renders the main JSX (i.e. right after the closing `}, []);` of the existing `useEffect(() => { fetchSessions()... }, [])` block), add:

```tsx
function handleFeedbackDone(result: { adjustmentTriggered: boolean; summary: string | null }) {
  setView('list');
  reload();
  if (result.adjustmentTriggered && result.summary) {
    setConfirmation({ summary: result.summary });
  } else {
    Alert.alert('Feedback saved');
  }
}

if (view === 'feedback' && activeSection) {
  const feedbackExercises: FeedbackExercise[] = exercises.map((ex) => ({ name: ex.name, sets: ex.sets }));
  return (
    <WorkoutFeedbackScreen
      sessionId={sessions?.[0]?.session_id ?? ''}
      dayLabel={activeSection.title}
      exercises={feedbackExercises}
      onBack={() => setView('list')}
      onDone={handleFeedbackDone}
    />
  );
}
```

Note: `sessions` here is the same state this file already populates via `fetchSessions()` in its existing `useEffect` — the session being viewed on this screen is always `sessions[0]` (the most recently generated plan), consistent with how `useLatestPlan` itself picks `sessions[0]` as "the latest."

- [ ] **Step 3: Render the confirmation card and the Finish Workout button**

Inside the main JSX, immediately after `<Text style={styles.title}>Workout</Text>` and before the `isLoading ? (...)` conditional, add:

```tsx
{confirmation ? (
  <Card>
    <Badge label="Plan updated" variant="success" />
    <Text style={styles.confirmationBody}>{confirmation.summary}</Text>
    <GhostButton label="Got it" onPress={() => setConfirmation(null)} style={{ marginTop: spacing.gapInner }} />
  </Card>
) : null}
```

(This requires adding `GhostButton` to the existing `import { PrimaryButton } from '../components/Buttons';` line → `import { GhostButton, PrimaryButton } from '../components/Buttons';`.)

Then, immediately after the closing of the `exercises.length > 0 ? (...) : (...)` block (i.e. right after its closing `)}`, still inside the same `<>...</>` fragment, before `<Text style={styles.sectionTitle}>Workout History</Text>`), add:

```tsx
{exercises.length > 0 ? (
  <PrimaryButton label="Finish Workout" onPress={() => setView('feedback')} style={{ marginTop: spacing.gapCards, marginBottom: spacing.gapCards }} />
) : null}
```

- [ ] **Step 4: Add the new style**

In the `StyleSheet.create({...})` call at the bottom of the file, add:

```ts
confirmationBody: { fontSize: 13, lineHeight: 1.55 * 13, color: colors.textPrimary, marginTop: 10 },
```

- [ ] **Step 5: Typecheck**

Run: `cd mobile && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Manual end-to-end verification**

Run: `cd mobile && npm run web`

Walk through, using a session that already has a generated plan (generate one first via the onboarding flow if none exists):

1. Open the Workout tab. Confirm the exercise list renders exactly as before, with a new "Finish Workout" button below it.
2. Tap "Finish Workout". Confirm the screen swaps to "How did today go?" showing every exercise from the active day, each with a "How did it feel?" pill row (defaulting to "Just Right") and an "Anything hurt?" pill row (defaulting to "No pain").
3. Leave everything at its default and tap "Submit Feedback". Confirm: a brief loading state appears, then the screen returns to the Workout tab and a "Feedback saved" alert appears (the no-adjustment path — confirms `needs_adjustment()` correctly short-circuited server-side, since this returned fast rather than blocking on an agent run).
4. Tap "Finish Workout" again. This time, on one exercise, tap "Too Hard" and toggle "Anything hurt?" to "Painful" — confirm a "Note (optional)" field appears only on that exercise's card. Type a note. Tap "Submit Feedback".
5. Confirm a real loading wait occurs this time (the Plan Adjuster agent actually running server-side — expect anywhere from several seconds to over a minute, per the spec's Loading State section) before returning to the Workout tab with a "Plan updated" confirmation card showing the agent's summary text. Confirm the exercise list itself still shows the original (pre-adjustment) exercise names — this is the documented, out-of-scope limitation from Global Constraints, not a bug in this implementation.
6. Tap "Got it" on the confirmation card and confirm it dismisses.

- [ ] **Step 7: Commit**

```bash
git add mobile/src/screens/WorkoutScreen.tsx
git commit -m "Wire Finish Workout into WorkoutScreen, opening the feedback screen"
```

---

## Self-Review

**Spec coverage:**
- "Workout screen stays untouched while browsing, Finish Workout opens a dedicated screen" → Task 5 (adds only the button + view-state branch, no per-row UI).
- "Every exercise gets a 3-way pill + pain pill + conditional note, defaults apply to untouched rows" → Task 4.
- "Skipped checkbox, zero extra schema cost" → Task 4's `skipRow`/`completed` handling.
- "Exact payload shapes, day_label/exercise.name sourcing" → Task 2's types + Task 5's `activeSection.title`/`exercisesFromDay`-derived names (unchanged from existing code, just passed through).
- "Loading state for a real agent run, not just a toast" → Task 4's `submitting` branch.
- "Error handling: surface and allow retry, don't lose state" → Task 4's `error` state (kept alongside `rows`, not cleared on failure).
- "No backend changes" → confirmed nowhere in this plan touches `api/`, `agents/`, `prompts/`, or `pipeline/`.
- "Reuse plan_adjuster as-is" → confirmed, only the client-side call changed.

**Placeholder scan:** No TBD/TODO; every step has complete code, not descriptions of code.

**Type consistency:** `Difficulty`, `ExerciseFeedbackInput`, `WorkoutFeedbackResult` (Task 2) are the exact names imported and used in Task 4. `FeedbackExercise`/`WorkoutFeedbackScreenProps` (Task 4) are the exact names imported and used in Task 5. `reload` (Task 3) is the exact name destructured in Task 5. `variant` (Task 1) is the exact prop name used in Task 4's danger `PillSelect`.

**Not built here (explicitly, per spec's own Non-goals):** feedback-history view, workout-occurrence/calendar tracking, any change to `plan_adjuster`'s own logic, moving the endpoint to a background-task+SSE pattern.
