# Plan Quality & Enforcement Fixes — Design

## Context

A real generated plan (session `e1d2d06e-e17d-4eca-a5d6-db380f9ce915` — hypertrophy,
beginner, 45min/day, 3 days/week, knee injury, chest priority, desk job, elevated
BF%) was compared against a better one from the same system and found to violate
its own stated parameters in eight distinct ways. This spec fixes those eight
issues without discarding the current architecture — the Supervisor / Exercise
Recommender / Plan Assembler pipeline and its existing deterministic
post-processing (`pipeline/plan_finalize.py`) are sound; specific gaps in them
are not.

All eight issues were individually reproduced and root-caused against the real
session before this spec was written (see each item below). This is not a
speculative list — item 1 in particular was confirmed by running
`enforce_volume_budget()` against a sandboxed copy of the actual session file and
observing it return `False` (no correction written) despite every day being
over its per-day budget.

## Goals

- Fix the confirmed parsing bug that lets `enforce_volume_budget()` silently
  no-op on a malformed but real LLM output, and make it recompute the Weekly
  Volume Summary from the real schedule unconditionally, not only when a day
  needed trimming.
- Close five prompt-content gaps (priority-muscle volume, push/pull balance on
  Full-Body days, beginner-appropriate exercise/rep selection, paradigm-independent
  injury guidance, honest BF%/PBF framing) and one prompt restructure
  (compound/isolation rep-range split).
- Keep the split established during design: deterministic code enforcement for
  numeric/structural constraints that have already been shown to fail silently
  under prompt-only instruction (volume budget, summary accuracy); prompt-content
  improvements for genuinely qualitative judgment calls that don't have — and
  don't warrant building — new deterministic backing data.

## Non-goals / explicitly out of scope

- Item 8 from the original punch list (asymmetry data not referenced) —
  investigated and found **not applicable** to the real session used for this
  spec: its InBody data shows no asymmetry flags at all (arm/leg/trunk all
  "NO"), and the existing `prompts/exercise_recommender.md` asymmetry rule
  ("if you were explicitly given an asymmetry flag... at least one exercise
  MUST be unilateral... if no asymmetry flag was given, do not apply unilateral
  prescription on your own initiative") reads as sound. No change made here.
- A new `movement_pattern` (push/pull/hinge/squat/carry) column on the exercise
  DB. Investigated: `tools/database.py`'s `exercises` table only has
  `movement_type` (`compound`/`isolation`/`unilateral`), and a `primary_muscle`-based
  heuristic would misclassify real cases (e.g. Close-Grip Bench Press is
  `primary_muscle=arms` but is a push-pattern lift). Building real push/pull
  data is a separate schema-and-backfill project; push/pull balance here stays
  an LLM-judgment prompt rule, not a deterministic check.
- Re-running or modifying `chunking.ipynb`/`vectordb_retrieval.ipynb` or the RAG
  ingestion pipeline — unrelated to this spec.
- Auto-fixing dropped exercises (e.g. the Pec Deck Machine that never made it
  into any day in the real session). Prescribing 4-5 exercises per muscle and
  having the assembler use a subset across the week is normal, expected
  behavior — distinguishing "consciously not used this week" from "silently
  forgotten" isn't reliably answerable from the data available, and isn't
  attempted here. The volume-summary-recompute fix (below) makes the resulting
  numbers honest either way, which is the part that actually matters.

## Architecture

Two independent tracks, touching four files:

```
pipeline/plan_finalize.py          <- code track (items 1, part of the honesty fix)
prompts/exercise_recommender.md    <- prompt track (items 4, 5, 6)
prompts/supervisor.md              <- prompt track (item 2)
prompts/plan_assembler.md          <- prompt track (item 3, wording touch-up for item 7's framing)
```

Nothing here changes the pipeline's call graph (`api/routes/plan.py:109`'s
`enforce_volume_budget(session_id)` call site is unchanged) or any tool contract
(`search_rag`, `search_exercise_db`, `read_plan_memory`, `write_plan_memory`,
`mark_step_done`, `validate_plan_completeness`, `validate_session_duration` all
keep their existing signatures). This is a targeted correctness/quality patch,
not a redesign.

## Component 1 — Parsing robustness (`pipeline/plan_finalize.py`)

**Confirmed root cause:** the real session's Weekly Schedule table cells
contain a literal ASCII DEL byte (`0x7F`) in place of "×" in every single
"Sets × Reps" cell across all 3 days (`'4\x7f12'`, not `'4×12'` or `'412'`).
`_extract_sets()`'s two existing regexes —

```python
_SETS_X_REPS = re.compile(r"(\d+)\s*[×xX]\s*(\d+(?:-\d+)?)")
_SETS_CONCAT = re.compile(r"^(\d)(\d+(?:-\d+)?)$")
```

— require either a recognized ×/x/X separator or *zero* characters between the
two digit groups. Neither matches "one unexpected non-digit byte in between",
so `_extract_sets()` returns `None` for every row, `enforce_volume_budget()`
computes `total = 0` for every day, `0 ≤ budget` always holds, and the function
returns `False` having changed nothing — even though every day in the real
session was 7-43% over its 14-set budget.

**Fix:** add a middle regex tier between the two existing ones:

```python
_SETS_UNKNOWN_SEP = re.compile(r"^(\d)\D+(\d+(?:-\d+)?)$")
```

Single-digit sets (matching `_SETS_CONCAT`'s existing single-digit convention,
which deliberately avoids the sets/reps ambiguity a `\d{1,2}` group would
reintroduce — e.g. misreading `"412"` as sets=41/reps=2), then **one or more**
non-digit characters, then reps. This is mutually exclusive with
`_SETS_CONCAT` (which requires *zero* separator characters), so there's no
ambiguity between the two tiers. `_extract_sets()`'s check order becomes:

1. `_SETS_X_REPS.search(cell)` — clean ×/x/X (unchanged)
2. `_SETS_UNKNOWN_SEP.match(cell.strip())` — new: any stray separator character(s)
3. `_SETS_CONCAT.match(cell.strip())` — fully collapsed, zero separator (unchanged)

**Second confirmed root cause (same component, found while verifying the fix
above against the real session):** fixing the parsing alone is not sufficient
to correct the real session's Day 1. Every exercise in Day 1 is its muscle
group's ordinal-1 pick (one exercise per muscle group, five muscle groups —
the natural shape of a Full-Body day), and the trim loop only ever removes
rows with `ordinal > 1` ("never remove the primary compound lift"). Verified
directly: replacing the stray byte with a clean `x` in a sandboxed copy of the
real session and re-running `enforce_volume_budget()` returns `True` (the
summary gets corrected), but Day 1 itself is left completely untouched —
still 5 exercises, still 20 sets, still 6 over its 14-set budget — because
`candidates = [r for r in rows if r["ordinal"] is not None and r["ordinal"] > 1]`
is empty and the loop breaks immediately.

**Fix:** add a second-tier fallback that reduces *set counts* rather than
removing whole exercises, for exactly the case where the ordinal-based pass
can't (or couldn't fully) bring the day within budget: while still over
budget, repeatedly reduce the set count of whichever remaining row has the
most sets, down to a floor of 2 sets per exercise (never removing the row,
never dropping a "primary compound lift" prescription to something
meaningless like 1 set). This requires `_extract_sets()`'s sibling —
extracting the *reps* half of the cell too (not currently captured anywhere)
— so a reduced row's cell text can be correctly rewritten (e.g. `4×12` →
`3×12`) instead of just having its set count silently drift out of sync with
its displayed text.

## Component 2 — Honest Weekly Volume Summary (`pipeline/plan_finalize.py`)

**Confirmed root cause:** `enforce_volume_budget()` already tallies
`muscle_week_totals` across every day unconditionally while it runs, but it
only reaches the summary-rewrite code path at all if `changed` is `True` —
and `changed` is only ever set when a day was found over its *per-day* budget
(`if total > budget: changed = True`). If every day is (incorrectly, per
Component 1's bug) computed as within budget, the function bails out at
`if not changed: return False` before ever checking whether the *summary
table itself* matches the real schedule. This is why the real session's saved
summary showed `chest: 14, back: 14, legs: 14` (over) and
`shoulders: 11, arms: 11` (met) when the actual scheduled totals for every
single muscle group were uniformly 11 — the assembler's own stale count was
never verified, let alone corrected.

**Fix:** decouple the two triggers. Compute `muscle_week_totals` as it already
does (now correctly, thanks to Component 1), then separately compare each
recomputed total against what the LAST written Weekly Volume Summary claims
for that muscle. If any value or status differs, that alone is sufficient to
trigger a rewrite — independent of whether any single day needed trimming.
Concretely: replace the single `changed` flag with two —
`any_day_trimmed` (existing meaning, drives whether day tables get rewritten)
and `summary_needs_correction` (new: true if any recomputed
muscle/sets/status triple differs from what's currently in the tail section).
The function proceeds to write a corrected section if *either* is true; each
half (day tables vs. summary tail) is only actually rewritten if its own flag
is true, so a day that's genuinely within budget is never touched just
because the summary elsewhere was wrong.

**Safety:** if `muscle_week_totals` ends up empty (e.g. no row in any day
could be matched back to a muscle group at all), no rewrite happens for the
summary regardless of `summary_needs_correction`'s value — an empty/partial
picture is never used to overwrite existing content. This preserves the
function's existing "don't touch what you can't confidently parse" contract.

## Component 3 — Priority-muscle volume (`prompts/supervisor.md`)

**Confirmed root cause:** `"priority"` appears in the prompt set exactly once
as a de-prioritization tiebreaker during trimming
(`plan_assembler.md`: "trim in this order (lowest priority first)"). Nothing
translates a stated `Priority focus: {muscle}` into *more* volume for that
muscle — every muscle group gets an identical weekly-volume target regardless.

**Fix:** in `supervisor.md`'s volume-target step (where it currently derives a
single `10-20 sets/week` — style range per muscle group from paradigm +
experience + BF%), add: when a muscle group matches the intake's stated
priority focus, target the *top* of that range rather than the model's own
unconstrained choice within it (e.g. beginner hypertrophy's 10-12 range
becomes "target 12, not 10" for the priority muscle specifically). This is a
concrete, checkable instruction, not "give it emphasis" vagueness.

## Component 4 — Push/pull balance on Full-Body days (`prompts/plan_assembler.md`)

**Confirmed root cause:** movement-pattern-balance guidance exists only for
the `general_fitness` paradigm (`supervisor.md`: "push/pull/hinge/squat/carry,
>=2x/week") and for *choosing* a Push/Pull/Legs split structure — nothing
governs the push/pull composition *within* a single Full-Body day, which is
what beginners (this session's experience level) are put on. The real
session's Day 1 had three pressing-pattern lifts (bench, overhead press,
close-grip bench) against one pulling lift (pull-up).

**Fix:** add a scheduling rule to `plan_assembler.md`'s existing "Scheduling
rules (mandatory)" section: within any single day, the count of
pressing-pattern exercises must not exceed the count of pulling-pattern
exercises by more than one; if it does, swap the lowest-priority press for
the best-fitting row/pull variant already prescribed for that muscle group in
plan memory (never introduce an exercise that wasn't already prescribed by
the Exercise Recommender). This stays LLM-judgment-based per the Non-goals
section — no new DB metadata backs it.

## Component 5 — Beginner-appropriate exercise/rep selection (`prompts/exercise_recommender.md`)

**Confirmed root cause:** the real session prescribed Pull-Up at 4×12 for a
stated beginner — the zone's numeric prescription (from the "medium"
hypertrophy intensity table) gets mechanically applied to whichever exercise
was selected, with no check for whether that's achievable at the stated
experience level, and no instruction to prefer a regressed variant for
bodyweight-loaded compounds.

**Fix:** add to the exercise-selection step: for beginners specifically, on
any bodyweight-loaded compound (pull-ups, dips, and similar), prefer an
assisted/regressed variant (lat pulldown, assisted pull-up, bench dip) unless
DB or RAG evidence indicates the specific movement is appropriate as
prescribed; cap the rep target at what's realistic for whichever variant is
actually selected rather than always using the zone's number verbatim.

## Component 6 — Compound/isolation rep-range split (`prompts/exercise_recommender.md`)

**Confirmed root cause:** every one of the 18 exercises prescribed across all
5 muscle groups in the real session is exactly "12" reps — the zone intensity
tables (e.g. hypertrophy "medium": 3-4 sets, 10-12 reps) give one rep number
per zone, with no axis for exercise role at all.

**Fix:** restructure each paradigm's intensity table to carry two rep ranges
per zone instead of one — a compound-lift range and an isolation range (e.g.
hypertrophy medium: compounds 8-10 reps, isolation 12-15 reps) — and instruct
the model to pick the range matching the exercise's own role, using the same
compound/isolation classification already available from
`tools/database.py`'s `movement_type` field.

## Component 7 — Injury/limitation guidance substance (`prompts/exercise_recommender.md`)

**Confirmed root cause:** the only injury-specific guidance anywhere in the
prompt set is gated behind the `rehabilitation` **paradigm** (a full goal
reclassification) — "pain-free range of motion is the primary constraint."
There is no rule for "an injury/limitation flag is present" under any *other*
paradigm, which is exactly this session's case (hypertrophy paradigm, knee
injury flag). The real output's only guidance was a label
("knee-safe exercises... considerations"), never a concrete cue or fallback.

**Fix:** add a paradigm-independent rule: whenever any injury/limitation flag
is present, regardless of paradigm, give (a) a concrete pain-monitoring cue
specific to the exercise (e.g. "stop short of pain; if depth provokes knee
pain, reduce range") and (b) a named fallback substitute exercise for any
selection that loads the affected joint (e.g. "if leg press aggravates the
knee, substitute hip thrust").

## Component 8 — Honest BF%/PBF framing (`prompts/plan_assembler.md`)

**Confirmed root cause:** `prompts/exercise_recommender.md`'s existing
Elevated BF% rule is already correctly framed as a "soft hint only — do not
treat as a fixed override" / "general lean" (verified: it never claims to
address body composition, only to prefer the upper end of the rep range).
The misleading claim is introduced downstream: the real session's Recovery
Notes state "Elevated body fat considerations addressed with moderate
intensity and machine use for isolation" — that text is the Plan Assembler's
own synthesis for its output template's `{any BF% or sleep-based adjustments
made}` line (`plan_assembler.md`'s "End of plan output" section), and the
assembler overclaims "addressed" where the recommender's own rule only ever
said "lean."

**Fix:** tighten the Recovery Notes template instruction in
`plan_assembler.md` to require framing any BF%-related note as what was
*leaned toward in rep selection*, never as body composition being
"addressed," "resolved," or "considered" as an outcome — and require an
explicit one-line statement that body composition change itself is a
nutrition/energy-balance outcome outside this program's scope.

## Error Handling

- Component 1/2 (code): unparseable input at any stage (day map, marker,
  table structure) results in `enforce_volume_budget()` returning `False`
  with no write — this existing fail-safe behavior is unchanged. The new
  summary-correction path additionally never writes with an empty
  `muscle_week_totals`, even if `summary_needs_correction` would otherwise be
  true.
- Components 3-8 (prompts): no deterministic backstop, by design — this is
  the accepted residual risk for judgment calls that don't have (and don't
  warrant building) deterministic backing data, matching the existing
  precedent of `plan_assembler.md`'s own max_sets self-trim instruction.

## Testing

- **Component 1:** unit tests against a matrix of malformed cells — clean
  `"4×12"`/`"4x12"`, the literal `"4\x7f12"` byte, a different stray character
  (e.g. `"4?12"`) to confirm the fix isn't narrowly hardcoded to `0x7F`
  specifically, fully-collapsed `"412"`, and a genuinely unparseable cell
  (e.g. `"n/a"`) that must still return `None`. Plus a fixture reproducing the
  real session's exact Day 1 shape (every exercise at ordinal 1 for its
  muscle group, all over budget) asserting the set-reduction fallback brings
  the day within budget without removing any row, and a fixture where even
  the reduction floor can't reach the budget (asserting it stops at the floor
  rather than looping forever or going non-positive).
- **Component 2:** a fixture `plan.md` reproducing the exact real-world shape —
  every day within its per-day budget, but the Weekly Volume Summary tail
  showing numbers that don't match the real per-day tables — asserting
  `enforce_volume_budget()` now returns `True` and corrects the summary even
  though no day needed trimming.
- **Components 3-8:** not unit-testable (non-deterministic LLM output).
  Verified by regenerating a plan from the *exact same real intake* used to
  diagnose these issues (hypertrophy, beginner, 45min, 3 days/week, knee
  injury, chest priority, desk job, elevated BF%, same InBody scan) once the
  prompt changes land, and manually checking the fresh output against each of
  the six qualitative fixes — the same forensic method used to diagnose them
  in the first place.

## Open questions / deferred

- Whether `movement_pattern` (push/pull/hinge/squat/carry) should become real
  exercise-DB metadata in a future project, replacing Component 4's
  LLM-judgment rule with a deterministic check — deferred per Non-goals.
- Whether Component 3's "target the top of the range" rule is sufficient
  priority emphasis, or whether a priority muscle should also get an extra
  exercise slot (not just higher reps/sets on existing slots) — left to the
  prompt wording during implementation; both are reasonable readings of "top
  of the range" and can be decided when writing the exact instruction text.
