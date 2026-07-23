# Tamrena AI — Workout Plan Generation System
## Architecture & Development Reference

---

## 1. Project Overview

Tamrena is an AI-powered workout plan generation system that replaces
deterministic gym program templates with a personalized multi-agent
pipeline. Instead of picking a template based on 3-4 generic inputs,
the system reads the user's actual body composition data (InBody scan)
combined with their goals and constraints to generate a plan that is
unique to them.

**Core difference from existing gym software:**
Existing software picks a split (PPL, Upper/Lower, etc.) and fills it
with the same exercises for everyone who selected the same goal. Tamrena
picks the split AND makes every exercise decision based on the individual's
InBody data, asymmetries, experience, and constraints.

---

## 2. System Flow — Start to Finish

```
[1] User fills intake form
          │
          ▼
[2] InBody scan uploaded → VLM extracts structured fitness data
          │
          ▼
[3] Supervisor agent reads form + InBody output
    - Decides which split (Full Body / PPL / Upper-Lower / etc.)
    - Decides which muscle groups to train
    - Assigns intensity per group (hard / medium / soft)
    - Calculates weekly volume per group
    - Writes plan to shared MD memory file
    - Creates todo list
          │
          ▼
[3b] Supervisor computes DAY MAP  ← NEW
     - Assigns each muscle group to a specific day slot
     - Calculates per-day set budget from session_duration
     - Writes DAY MAP to shared MD memory file
     - Routes each InBody flag to only the muscle groups it applies to
     (This must complete before any exercise-recommender is dispatched)
          │
          ▼
[4] For each muscle group in plan (sequential, not parallel):
    Exercise Recommender sub-agent runs
    - Reads shared MD memory file (sees plan + DAY MAP + what previous agents did)
    - Receives only the InBody flags relevant to its muscle group
    - Receives max_sets budget for its assigned day
    - Queries RAG: principles namespace + muscle_specific namespace
    - Queries exercise database (MongoDB) for matching movements
    - Decides 3-5 exercises with full prescription (sets/reps/rest/RPE)
    - Must not exceed max_sets budget for its day
    - Writes results to shared MD memory file
    - Returns prescription to supervisor
          │
          ▼
[5] Plan Assembler sub-agent runs
    - Reads shared MD memory file (has all prescriptions + DAY MAP)
    - Arranges exercises into weekly schedule
    - Applies recovery rules (no same muscle on consecutive days)
    - Checks each day against its max_sets budget from DAY MAP
    - Trims over-budget days (specific trim order defined in 4d)
    - Calls validate_session_duration to confirm all days pass
    - Writes final plan to MD memory file
    - Returns structured plan to supervisor
          │
          ▼
[6] Supervisor synthesises final response to user
```

---

## 3. Input Schema

### 3a. User Intake Form

**Must have — plan cannot be generated without these:**

| Field | Type | Options |
|---|---|---|
| goal | free text | User-stated goal in any phrasing. Supervisor classifies to a programming paradigm before planning begins (see Section 4e). Closed enum removed — an unrecognized goal no longer crashes the pipeline. |
| days_per_week | int | 2 / 3 / 4 / 5 / 6 |
| experience | enum | beginner (<1yr) / intermediate (1-3yr) / advanced (3yr+) |
| session_duration | enum | 45min / 60min / 90min |

**Should have — changes exercise selection and volume:**

| Field | Type | Notes |
|---|---|---|
| injuries | text | Body part + what it limits. "Left shoulder — no overhead pressing." Not just yes/no. |
| priority | text | What they want to focus on. "I want bigger arms" / "my back is lagging" |
| age | int | Affects recovery calculation, mainly matters 35+ |

**Nice to have — refines volume tolerance:**

| Field | Type | Options |
|---|---|---|
| sleep_quality | enum | good / average / poor |
| job_type | enum | desk / light_physical / heavy_physical |
| current_program | text | What they've been doing — avoids giving same thing |

**Do NOT collect — InBody covers these more accurately:**
- Weight / height (InBody gives lean mass, fat mass, segmental data)
- Exact 1RMs (RPE-based prescription handles this)

**Do NOT collect — out of scope:**
- Diet / nutrition
- Supplement use

### 3b. InBody Data

Raw InBody scan uploaded by user (PDF or image). VLM extracts:

```
Skeletal Muscle Mass     → overall development level
Body Fat %               → soft hint toward higher rep ranges (see flag below)
BMR                      → informational only
Segmental lean mass:
  Right arm / Left arm   → arm asymmetry flag if >200g difference
  Right leg / Left leg   → leg asymmetry flag if >500g difference
  Trunk                  → chest/back development context
```

**Flags derived from InBody (used by sub-agents):**
- ARM_ASYMMETRY → back pull day and arm days must include unilateral movements
- LEG_ASYMMETRY → leg days prioritise unilateral, start sets on weaker side
- ELEVATED_BF (>18% male, >25% female) → SOFT HINT: prefer upper end of rep range,
  not a fixed override. Rep range is determined by exercise type and load, not body fat.
- TRUNK_UNDERDEVELOPED → chest/back volume gets priority

**Flag routing — which muscle groups each flag applies to:**

| Flag | Applies to | Do NOT send to |
|---|---|---|
| ARM_ASYMMETRY | back_vertical, back_horizontal, biceps, triceps | quads, hamstrings, glutes, calves, chest, shoulders |
| LEG_ASYMMETRY | quads, hamstrings, glutes, calves | back, chest, arms, shoulders |
| ELEVATED_BF | all groups | — |
| TRUNK_UNDERDEVELOPED | chest, back_horizontal | legs, arms |

Supervisor must only include relevant flags in each exercise-recommender's task prompt.
Sending ARM_ASYMMETRY to legs, or LEG_ASYMMETRY to back, causes incorrect
unilateral prescriptions on balanced muscle groups.

Equipment is NOT collected. System assumes full commercial gym access.

---

## 4. Agent Architecture

### 4a. VLM / InBody Parser (Tool, not agent)

Called by supervisor as its first action. Not a sub-agent — a tool function.

```
Input:  raw InBody scan text (OCR output or PDF extract)
Output: structured fitness-relevant analysis with FLAGS
Model:  Azure OpenAI gpt-4.1-mini with vision
API:    Azure OpenAI (only LLM call in this step)
```

Returns structured text that supervisor and all sub-agents can reason about.
Flags section is the most important part — it tells sub-agents what to do differently.

### 4b. Supervisor Agent

```
Model:  Azure OpenAI gpt-4.1-mini (via AzureChatOpenAI instance)
Tools:  parse_inbody, write_todos, task (built-in deepagents tools)
Memory: reads/writes shared MD session file
```

Responsibilities:
0. Classify goal to programming paradigm (see Section 4e) — FIRST action, before
   calling parse_inbody. Map the user's raw goal text to one of 7 paradigms:
   hypertrophy / strength / fat_loss / general_fitness / athletic_performance /
   endurance_complement / rehabilitation.
   If goal is ambiguous or unrecognized → default to general_fitness and write
   a note in the plan header: "Paradigm: general_fitness (original goal: '{text}'
   — defaulted to general fitness paradigm)".
   Write the classified paradigm to the User Profile section of the plan file.
   All subsequent steps use the paradigm, not the raw goal string.
1. Call parse_inbody → get structured InBody data
2. Read user intake form
3. Decide split type based on days_per_week + experience + paradigm
4. Decide intensity zone per muscle group based on paradigm rules (Section 4e) + InBody + stated priority
5. Calculate weekly volume per muscle group based on paradigm rules (Section 4e) + experience + recovery factors
5b. Compute DAY MAP — assign each muscle group to a day slot + calculate per-day
    set budget from session_duration. Write DAY MAP to shared MD memory file.
    This must happen BEFORE the first exercise-recommender is dispatched.
5c. Route InBody flags — for each exercise-recommender task prompt, include ONLY
    the flags from the "Applies to" column in the flag routing table (Section 3b).
5d. Initialize the progress tracker — call `init_plan_progress(session_id, muscle_groups)`
    with the authoritative list of muscle groups this plan requires (e.g.
    ["chest", "back", "shoulders", "arms", "legs"]). This must happen before any
    exercise-recommender is dispatched. See Section 5d.
6. Write full plan to shared MD memory file
7. Create todo list with one entry per muscle group + final assembly
8. Dispatch exercise-recommender for each muscle group (sequential), including
   max_sets budget and scoped flags in each task prompt.
   After each task() call returns, call `get_plan_progress(session_id)` and confirm
   the muscle group just dispatched now appears in "completed". Do not advance to
   the next muscle group until this is confirmed — a task() return with no matching
   progress update means the recommender did not complete correctly and must be retried.
9. Dispatch plan-assembler only when `get_plan_progress(session_id)` reports
   `all_done: true`. If any muscle group is still in "remaining", do not dispatch
   the assembler — re-dispatch the missing muscle group(s) first.
10. Synthesise final response

**Volume reduction factors the supervisor applies:**
- poor sleep → -20% volume
- heavy physical job → -20% volume
- InBody asymmetry flag → affected group gets unilateral focus, not extra volume

Volume base targets, intensity zones, rep windows, and rest periods are all
defined per-paradigm in Section 4e. Apply the correct paradigm table first,
then apply the reduction factors above on top of it.

Hypertrophy sets/week reference (default paradigm):
- beginner: 10-12 | intermediate: 14-18 | advanced: 18-22
All other paradigms: see Section 4e for their specific volume metrics.

**DAY MAP computation:**

After deciding split and intensity, Supervisor computes a per-day set budget
before dispatching any exercise-recommender.

Set budget formula:
```
Parse session_duration to minutes (e.g. "75min" → 75)
Subtract 10 minutes for warmup
Divide by average time per set based on paradigm + intensity zone:

  hypertrophy / fat_loss / general_fitness / endurance_complement:
    hard   (RPE 8+): 3.5 min per set (set ~45s + rest 2-3 min)
    medium (RPE 7):  2.5 min per set (set ~45s + rest 90s)
    mixed session:   3.0 min per set

  strength / athletic_performance:
    heavy zone:      6.0 min per set (set ~30-45s + rest 4-5 min)
    volume zone:     4.0 min per set (set ~45s + rest 3 min)
    speed zone:      3.5 min per set (set ~30s + rest 3 min)
    mixed session:   5.0 min per set average

  rehabilitation:
    all sessions:    3.0 min per set (slower, controlled execution)

Round down (floor)

Example — 4-day Upper/Lower, 75 min sessions:
  Day 1 Pull (hard):   floor((75-10) / 3.5) = 18 sets max
  Day 2 Legs (medium): floor((75-10) / 2.5) = 26 sets max
  Day 3 Push (medium): floor((75-10) / 2.5) = 26 sets max
  Day 4 Legs (medium): floor((75-10) / 2.5) = 26 sets max

Example — 45 min sessions, medium day:
  floor((45-10) / 2.5) = 14 sets max

Example — 90 min sessions, hard day:
  floor((90-10) / 3.5) = 22 sets max
```

DAY MAP is written to the plan file immediately after the Training Plan section.
All exercise-recommenders read it before deciding on set counts.
Plan Assembler reads it when enforcing session duration budgets.

**Leg day differentiation for 4-day plans:**

When the split produces two leg days, the Supervisor must give each a
different muscle emphasis brief. Do not dispatch the same task prompt twice.

For 4-day Upper/Lower (Option A):
  Leg Day A task prompt: "focus quad development as primary, hamstrings as secondary"
  Leg Day B task prompt: "focus hamstring and glute development as primary, quads as secondary"

This ensures the exercise-recommender selects different exercises for each day
(e.g. squat-pattern on Day A, RDL-pattern on Day B) without any code change.

### 4c. Exercise Recommender Sub-agent

One agent definition, called once per muscle group. Not separate agents per muscle.

```
Name:   exercise-recommender
Model:  Azure OpenAI gpt-4.1-mini (via AzureChatOpenAI instance)
Tools:  search_rag, search_exercise_db, read_plan_memory, write_plan_memory, mark_step_done
```

Receives from supervisor (via task prompt):
- Which muscle group and intensity level
- Pointer to read the shared MD memory file for full context
- max_sets budget for this muscle group on its assigned day
- ONLY the InBody flags relevant to this muscle group (scoped by Supervisor)

Process (in order):
1. Call read_plan_memory → gets full InBody, plan, DAY MAP, previous prescriptions
2. Build targeted RAG query based on muscle + intensity + InBody flags
3. Search principles namespace for relevant training science
4. Search muscle_specific namespace filtered by this muscle group
5. Search MongoDB exercise collection for matching movements
6. Select 3-5 exercises justified by RAG evidence
7. Prescribe sets/reps/rest/RPE based on intensity level
8. Confirm total sets across all exercises does not exceed max_sets budget
9. Write prescription to shared MD memory file
9b. Call `mark_step_done(session_id, muscle_group)` — this is the recommender's own
    confirmation that it finished this muscle group. Must be the last tool call
    before returning. See Section 5d.
10. Return prescription to supervisor

**Intensity prescription rules (paradigm-conditional):**

Read the `Paradigm:` field from the plan file (written by Supervisor step 0)
before applying any intensity rule. Use the matching table below.

*Paradigm: hypertrophy (default)*
| Zone   | Sets | Reps  | Rest    | RPE | Focus |
|--------|------|-------|---------|-----|-------|
| hard   | 4    | 6-8   | 2-3 min | 8-9 | heavy compound first |
| medium | 3-4  | 10-12 | 90s     | 7   | compound + isolation |
| soft   | 3    | 15+   | 60s     | 5-6 | corrective / unilateral |

*Paradigm: strength*
| Zone   | Sets | Reps       | Rest    | RPE  | Focus |
|--------|------|------------|---------|------|-------|
| heavy  | 4    | 1-5 main   | 4-8 min | 9+   | primary movement anchor, named explicitly |
| volume | 3-4  | 3-8 suppl  | 3-5 min | 7-8  | same movement pattern, reduced load |
| speed  | 3-4  | 2-4        | 3 min   | 6-7  | 60-70% 1RM, technique / bar speed focus |
Primary movement must be named in the DAY MAP and placed first. Rep windows:
main 1-5 / supplemental 3-8 / accessories 6-12.

*Paradigm: fat_loss*
| Zone     | Sets | Reps  | Rest  | RPE | Focus |
|----------|------|-------|-------|-----|-------|
| circuit  | 3-4  | 15-20 | 45s   | 7-8 | density, superset-friendly |
| moderate | 3    | 12-15 | 60-75s| 6-7 | compound movements, full ROM |
| low      | 2-3  | 15+   | 45s   | 5-6 | corrective / finisher |

*Paradigm: general_fitness*
| Zone     | Sets | Reps  | Rest    | RPE | Focus |
|----------|------|-------|---------|-----|-------|
| moderate | 3-4  | 8-15  | 60-120s | 6-8 | movement pattern coverage |
Session anchor is movement pattern (push/pull/hinge/squat/carry), not isolated
muscle group. All days use moderate zone — no hard or soft distinction needed.

*Paradigm: athletic_performance*
| Zone         | Sets | Reps  | Rest    | RPE | Focus |
|--------------|------|-------|---------|-----|-------|
| power        | 3-4  | 3-6   | 2-4 min | 8-9 | explosive, sport-relevant movement |
| strength     | 3-4  | 5-10  | 2-3 min | 7-8 | compound patterns |
| conditioning | 3-4  | 12-20 | 60-90s  | 6-7 | muscular endurance, sport carry-over |

*Paradigm: endurance_complement*
| Zone  | Sets | Reps  | Rest  | RPE | Focus |
|-------|------|-------|-------|-----|-------|
| light | 2-3  | 15-25 | 30-60s| 5-7 | muscular endurance, no heavy loading |
Leg volume is conservatively capped — running/cycling already loads legs.
Total external fatigue (weekly cardio km/hours) must be noted in plan header.

*Paradigm: rehabilitation*
| Zone        | Sets | Reps  | Rest    | RPE | Focus |
|-------------|------|-------|---------|-----|-------|
| corrective  | 2-3  | 10-15 | 60-90s  | 4-6 | pain-free ROM only, slow tempo |
| progressive | 3    | 10-20 | 60-90s  | 5-7 | gradual load increase, movement quality |
No hard zone permitted. Session anchor is injury site / movement pattern.

**Asymmetry rule:** if the Supervisor included an asymmetry flag for this muscle
group in the task prompt, at least one exercise must be unilateral.
Always start sets on weaker side. If no asymmetry flag was sent, do not apply
unilateral prescription — legs and arms are independent flags.

**BF% elevated rule (soft hint only):** prefer the upper end of the rep range.
Prefer 8 over 6 for hard sessions, prefer 12 over 10 for medium sessions.
This is not a fixed override — rep ranges should still vary across exercises
within a session. Hypertrophy rep range is determined by load and exercise type,
not by body fat percentage. Do not interpret this flag as "always use 12 reps."

### 4d. Plan Assembler Sub-agent

```
Name:   plan-assembler
Model:  Azure OpenAI gpt-4.1-mini (via AzureChatOpenAI instance)
Tools:  read_plan_memory, write_plan_memory, validate_session_duration,
        validate_plan_completeness, format_plan_session
```

Receives from supervisor (via task prompt):
- User's available training days
- Pointer to read the shared MD memory file for all prescriptions

The Supervisor only dispatches the Plan Assembler once `get_plan_progress` reports
`all_done: true` (Section 5d) — but the Assembler re-checks this itself via
`validate_plan_completeness` rather than trusting the Supervisor's dispatch decision
alone, since it is the last agent to run before the plan is final.

Process:
0. Call validate_plan_completeness(session_id) → if any expected muscle group is
   missing, STOP and report the gap. Do not assemble a plan around a missing group.
1. Call read_plan_memory → gets all muscle group prescriptions + DAY MAP
2. Apply scheduling rules:
   - Never train same muscle group on consecutive days
   - Hardest session placed where recovery time is longest after it
   - If upper/lower split, alternate upper and lower days
2b. Read max_sets budget per day from the DAY MAP section of the plan file
3. Format each session with warm-up note specific to that muscle group
3b. For each day, count total working sets scheduled
3c. If total_sets > max_sets for that day, trim in this order (lowest priority first):
    a. Isolation exercises that duplicate stimulus already in the session
       (e.g. two bicep curl variations — keep the one with stronger RAG justification)
    b. Accessory / corrective exercises beyond the first per session
    c. Additional sets from the lowest-RPE exercise in the day
    Never remove: primary compound lift for any muscle group,
                  any unilateral exercise flagged for asymmetry correction
3d. Call validate_session_duration tool — it checks every day against the budget.
    If any day still fails, repeat 3c for that day before proceeding.
4. Calculate total weekly volume per muscle group
5. Write final weekly plan to shared MD memory file
6. Return structured plan to supervisor

### 4e. Programming Paradigms

The paradigm is the ruleset the agents operate under. It is derived from the
user's raw goal text by the Supervisor (step 0) and written to the plan file
before any other planning work begins. All downstream agents read the paradigm
field from the plan file — they never re-derive it from the raw goal string.

**Why this abstraction exists:**
Mapping goal directly to agent behavior means every new or unexpected goal
type crashes the pipeline or silently applies hypertrophy defaults. The
paradigm layer decouples user language from agent rules. An unrecognized goal
gets classified as general_fitness and continues without error. New goal phrasings
require no code change — only the classification mapping below is updated.
See Section 13 for the full design rationale.

---

**Goal → Paradigm classification mapping (Supervisor step 0):**

```
"hypertrophy / muscle / mass / bulk / size / get bigger"      → hypertrophy
"strength / powerlifting / 1RM / big 3 / get stronger"        → strength
"fat loss / weight loss / cutting / lean / burn / lose weight" → fat_loss
"fitness / health / general / maintain / active / wellness"    → general_fitness
"sport / explosive / power / athletic / speed / performance"   → athletic_performance
"endurance / marathon / running / cycling / cardio complement" → endurance_complement
"rehab / corrective / recovery / post-surgery / injury"        → rehabilitation

Ambiguous or unrecognized → general_fitness (default, never crash)
```

---

**Paradigm 1 — hypertrophy** *(current default)*
```
Volume metric:    sets/week per muscle group (MEV/MAV/MRV landmarks)
                  beginner: 10-12 | intermediate: 14-18 | advanced: 18-22
Rep window:       6-20 (majority 8-15)
Rest:             60-180s
Session anchor:   muscle group
DAY MAP time/set: hard 3.5 min | medium 2.5 min | mixed 3.0 min
Intensity zones:  hard / medium / soft
```

**Paradigm 2 — strength**
```
Volume metric:    primary lift frequency (2-3x/week per Big 3 movement)
                  NOT sets/week per muscle group
Rep window:       main 1-5 | supplemental 3-8 | accessories 6-12
Rest:             main 4-8 min | accessories 2-3 min
Session anchor:   primary movement — must be named explicitly in DAY MAP
                  (e.g. "barbell squat", "bench press", "conventional deadlift")
DAY MAP time/set: heavy 6.0 min | volume 4.0 min | speed 3.5 min | avg 5.0 min
Intensity zones:  heavy / volume / speed (NOT hard/medium/soft)
Day types must vary — do not assign the same zone to all days.
```

**Paradigm 3 — fat_loss**
```
Volume metric:    sets/week per muscle group, density-optimised
                  (superset pairing preferred, shorter rest drives caloric expenditure)
                  beginner: 10-14 | intermediate: 14-18 | advanced: 16-20
Rep window:       12-20 (metabolic stimulus)
Rest:             45-75s
Session anchor:   muscle group
DAY MAP time/set: circuit 1.75 min | moderate 2.0 min
Intensity zones:  circuit / moderate / low
```

**Paradigm 4 — general_fitness**
```
Volume metric:    movement pattern coverage per week
                  (push / pull / hinge / squat / carry — at least 2x each)
Rep window:       8-15 (mixed, accessible)
Rest:             60-120s
Session anchor:   movement pattern (NOT isolated muscle group)
DAY MAP time/set: 2.5 min (all sessions moderate)
Intensity zones:  moderate only — no heavy/soft split needed
Fallback for:     any unrecognized or ambiguous goal
```

**Paradigm 5 — athletic_performance**
```
Volume metric:    power exposure frequency + movement quality sessions per week
Rep window:       power 3-6 | strength-endurance 8-15
Rest:             power 2-4 min | conditioning 60-90s
Session anchor:   sport-relevant movement pattern
DAY MAP time/set: power session 4.0 min | conditioning 2.0 min | mixed 3.5 min
Intensity zones:  power / strength / conditioning
Exercise selection prioritises multi-joint, sport-transferable movements.
```

**Paradigm 6 — endurance_complement**
```
Volume metric:    session frequency + total external fatigue budget
                  External fatigue (weekly run/cycle km) reduces lifting volume:
                  <30km/week: standard volume | 30-60km/week: -20% | 60km+: -35%
Rep window:       15-25 (muscular endurance)
Rest:             30-60s
Session anchor:   muscle group (bias toward posterior chain + injury prevention)
DAY MAP time/set: 1.75 min
Intensity zones:  light only — no heavy loading on top of cardio base
Leg volume capped conservatively — running already provides leg stimulus.
Total weekly cardio load must be written to plan header for all agents to read.
```

**Paradigm 7 — rehabilitation**
```
Volume metric:    ROM progression + movement quality (not sets/week)
Rep window:       10-20 (controlled, pain-free range only)
Rest:             60-90s
Session anchor:   injury site / movement pattern
DAY MAP time/set: 3.0 min (slower, controlled execution)
Intensity zones:  corrective / progressive (hard zone never permitted)
Exercise selection requires contraindication check on every exercise.
Pain-free ROM is the primary constraint — load is secondary.
```

---

## 5. Shared MD Memory File

The memory mechanism between agents. No shared state, no database.
All agents read from and append to a single markdown file per session.

File is created fresh for each user session. Path: `sessions/{session_id}/plan.md`

### 5a. File structure (built progressively during the run)

```markdown
# Tamrena Session — {user_name}
Generated: {timestamp}

## User Profile
Goal: {goal}
Paradigm: {classified_paradigm}   ← written by Supervisor step 0, read by all agents
Experience: {experience}
Days per week: {days}
Session duration: {duration}
Injuries: {injuries or "none"}
Priority focus: {priority or "none"}

## InBody Analysis
{full output from parse_inbody tool}

## Training Plan
[ ] Step 1: {muscle_group_1} — {intensity}
[ ] Step 2: {muscle_group_2} — {intensity}
[ ] Step 3: {muscle_group_3} — {intensity}
[ ] Step 4: Assemble weekly schedule
Split: {split_name}
Volume target: {sets_per_week} sets per muscle group

DAY MAP:
Day 1 — {label}: muscles [{list}] | max_sets: {n} | intensity: {level}
Day 2 — {label}: muscles [{list}] | max_sets: {n} | intensity: {level}
Day 3 — {label}: muscles [{list}] | max_sets: {n} | intensity: {level}
Day 4 — {label}: muscles [{list}] | max_sets: {n} | intensity: {level}

← Supervisor writes everything above (including DAY MAP) before dispatching
  any exercise-recommender. All sub-agents read this section first.

---

## {MUSCLE_GROUP_1} — {INTENSITY} ✓
1. {Exercise}  {sets}×{reps} | Rest {time} | RPE {n}
   → {why this exercise / key technique cue}
2. ...
Evidence: {1 sentence from RAG}

---
← agent 1 writes above, supervisor dispatches step 2

## {MUSCLE_GROUP_2} — {INTENSITY} ✓
(same structure, this agent saw muscle_group_1 results above it)

---
## {MUSCLE_GROUP_3} — {INTENSITY} ✓
(saw both previous prescriptions)

---
## Weekly Schedule ✓
{formatted plan from assembler}
```

### 5b. Why this approach

- No shared memory database needed
- Every agent reads exactly the same file, no context sync issues
- File is the audit trail — you can open it and see every decision
- Sequential execution means no concurrent write conflicts
- Supervisor's task() prompts stay short — just tell agent to read the file
- DAY MAP in the file means every agent knows the day structure before running

### 5c. Tools that access the file

```python
import os

SESSION_DIR = "sessions"

def read_plan_memory(session_id: str) -> str:
    """All agents call this first. Returns full file content."""
    path = f"{SESSION_DIR}/{session_id}/plan.md"
    if not os.path.exists(path):
        return "(plan file not created yet)"
    with open(path, "r") as f:
        return f.read()

def write_plan_memory(session_id: str, section_title: str, content: str) -> str:
    """Each agent calls this when done. Appends only, never overwrites."""
    path = f"{SESSION_DIR}/{session_id}/plan.md"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(f"\n\n## {section_title}\n{content}\n\n---")
    return f"Written to plan memory: {section_title}"

def validate_session_duration(session_id: str) -> str:
    """
    Plan Assembler calls this after scheduling to verify no day exceeds
    the session duration limit. Parses the assembled schedule from the
    plan file and returns any violations with excess set counts.

    Returns "PASS" if all days are within budget.
    Returns a violation report with excess set counts per day if any day fails.
    Plan Assembler must trim and retry if this returns violations.
    """
    content = read_plan_memory(session_id)

    # parse session_duration from User Profile section
    duration_min = 75  # fallback default
    for line in content.splitlines():
        if "Session duration" in line:
            raw = line.split(":")[-1].strip()     # e.g. "75min"
            duration_min = int("".join(filter(str.isdigit, raw)))
            break

    # parse DAY MAP — read max_sets budget per day label
    day_budgets = {}
    in_day_map = False
    for line in content.splitlines():
        if "DAY MAP:" in line:
            in_day_map = True
            continue
        if in_day_map and line.startswith("Day "):
            if "max_sets:" in line:
                day_label = line.split("—")[0].strip()   # e.g. "Day 1"
                max_sets = int(line.split("max_sets:")[1].split("|")[0].strip())
                day_budgets[day_label] = max_sets
        if in_day_map and line.strip() == "":
            in_day_map = False

    # count scheduled sets per day from the Weekly Schedule section
    # looks for table rows with a "sets×reps" pattern e.g. "4×8"
    day_set_counts = {}
    current_day = None
    for line in content.splitlines():
        if line.startswith("### Day"):
            current_day = line.split("—")[0].replace("###", "").strip()  # "Day 1"
            day_set_counts[current_day] = 0
        if current_day and "|" in line and "×" in line:
            parts = line.split("|")
            for part in parts:
                if "×" in part:
                    try:
                        sets = int(part.strip().split("×")[0])
                        day_set_counts[current_day] = (
                            day_set_counts.get(current_day, 0) + sets
                        )
                    except ValueError:
                        pass

    # check each day against its budget
    violations = []
    for day, scheduled_sets in day_set_counts.items():
        budget = day_budgets.get(day)
        if budget and scheduled_sets > budget:
            excess = scheduled_sets - budget
            violations.append(
                f"  {day}: {scheduled_sets} sets scheduled, "
                f"budget is {budget} ({excess} sets over — trim {excess} sets)"
            )

    if not violations:
        return "PASS — all days within session duration budget."

    return (
        "VIOLATIONS — trim before writing final plan:\n"
        + "\n".join(violations)
        + "\n\nTrim lowest-priority exercises first (see plan_assembler.md step 3c)."
    )
```

### 5d. Progress Tracking — separate structured file, not parsed from the MD prose

**Why this exists:** the shared MD file (5a-5c) is free-form text written by an LLM.
Regex-parsing it to answer "which muscle groups are done, and what's next" is fragile —
formatting can drift (a missing `✓`, a muscle group name spelled differently than the
DAY MAP), and by the time there are 8-10 sequential dispatches the Supervisor cannot
reliably re-derive its position from prose alone. See Section 14 v1.2 for a real
run where this exact gap caused a fully-planned muscle group (back) to be silently
dropped with no error.

Progress state lives in its own file: `sessions/{session_id}/progress.json`.
It is written only by tool functions with structured parameters — never by an LLM
composing text that later needs to be parsed back out.

```python
import json

def progress_path(session_id: str) -> str:
    return f"{SESSION_DIR}/{session_id}/progress.json"

def init_plan_progress(session_id: str, muscle_groups: list) -> str:
    """Supervisor calls this once, immediately after computing the DAY MAP —
    before any exercise-recommender is dispatched. `muscle_groups` is the
    authoritative, complete list this plan requires (e.g. from the DAY MAP)."""
    progress = {"expected": muscle_groups, "completed": []}
    with open(progress_path(session_id), "w") as f:
        json.dump(progress, f)
    return f"Progress tracker initialized: {len(muscle_groups)} muscle groups expected."

def mark_step_done(session_id: str, muscle_group: str) -> str:
    """Exercise-recommender calls this as its last action, right after
    write_plan_memory. Structured parameter — not free text, so nothing
    needs to be parsed back out of prose later."""
    path = progress_path(session_id)
    progress = json.load(open(path))

    if muscle_group not in progress["expected"]:
        return (f"WARNING: '{muscle_group}' is not in the expected muscle group "
                f"list for this session ({progress['expected']}). Not recorded.")
    if muscle_group in progress["completed"]:
        return f"WARNING: '{muscle_group}' was already marked done — possible duplicate dispatch."

    progress["completed"].append(muscle_group)
    with open(path, "w") as f:
        json.dump(progress, f)

    remaining = [g for g in progress["expected"] if g not in progress["completed"]]
    return f"Marked done: {muscle_group}. Remaining: {remaining or 'none — all groups complete'}"

def validate_plan_completeness(session_id: str) -> str:
    """Plan Assembler calls this before doing any scheduling work — a hard
    gate, not a note in a summary table. Returns PASS only if every expected
    muscle group has a recorded prescription."""
    progress = get_plan_progress(session_id)
    if progress["all_done"]:
        return "PASS — all expected muscle groups have prescriptions."
    return (
        "INCOMPLETE — cannot assemble plan. Missing prescriptions for: "
        f"{progress['remaining']}. Dispatch the exercise-recommender for these "
        "muscle groups before calling the assembler."
    )

def get_plan_progress(session_id: str) -> dict:
    """Supervisor calls this after every task() return, before deciding the
    next dispatch, and again before dispatching the plan-assembler. Returns a
    structured answer — the Supervisor never has to count or infer from text."""
    progress = json.load(open(progress_path(session_id)))
    remaining = [g for g in progress["expected"] if g not in progress["completed"]]
    return {
        "expected":  progress["expected"],
        "completed": progress["completed"],
        "remaining": remaining,
        "next":      remaining[0] if remaining else None,
        "all_done":  len(remaining) == 0,
    }
```

**Rules:**
- `init_plan_progress` is called exactly once, by the Supervisor, right after the DAY MAP
  is written — this is the single authoritative source for what "done" means for this session.
- `mark_step_done` is called by the exercise-recommender itself, not the Supervisor —
  it is the natural last step of the same tool sequence that already ends in
  `write_plan_memory`, so it adds no extra round trip.
- The Supervisor does not trust the mark blindly — it calls `get_plan_progress`
  after every `task()` return specifically to confirm the muscle group it just
  dispatched is the one that got marked. A mismatch (or no change) means the
  recommender failed silently and must be retried, not skipped.
- The Plan Assembler must never be dispatched while `all_done` is `false`.
  This is the check that would have caught the missing-back bug in Section 14 v1.2 —
  a 0-sets muscle group in the Weekly Volume Summary is a symptom; `all_done: false`
  is the cause, caught before the final plan is ever written.

---

## 6. Plan Types the System Outputs

Supervisor selects split based on days_per_week + experience + goal.

### 2 days/week
```
Full Body A / Full Body B
All major muscle groups every session, A and B have exercise variation.
Who: beginners, time-constrained, returning from break.
Muscle groups: chest, back, legs, shoulders (arms as secondary)
```

### 3 days/week
```
Option A — Full Body × 3
All muscles every session, variation across A/B/C.
Who: beginners wanting frequency.

Option B — Push / Pull / Legs  (most common for intermediates)
Push: chest, shoulders, triceps
Pull: back (vertical + horizontal), biceps, rear delts
Legs: quads, hamstrings, glutes, calves
Who: intermediate, most common 3-day format.

Option C — Upper / Lower / Full
Upper A: chest, back, shoulders, arms
Lower: quads, hamstrings, glutes
Full: compound movements only, lighter load
Who: intermediate wanting frequency + focus mix.
```

### 4 days/week
```
Option A — Upper Lower Upper Lower  (recommended for most)

Upper A: back (vertical + horizontal) + biceps, strength focus (6-8 reps, heavy compound)
Upper B: chest + shoulders + triceps, hypertrophy focus (10-12 reps)
Lower A: quads as primary, hamstrings as secondary — quad-pattern exercises first
Lower B: hamstrings + glutes as primary, quads as secondary — hip-hinge exercises first

IMPORTANT: Lower A and Lower B must receive different exercise-recommender briefs.
The Supervisor dispatches two separate task prompts for the two leg days with
explicitly different muscle emphasis. This produces different exercise selections
(e.g. squat patterns on Lower A, RDL patterns on Lower B) without any code change.
Do NOT dispatch the same leg brief twice.

Who: intermediates, best balance of frequency and volume.

Option B — Body Part 4-day
Day 1: chest + triceps
Day 2: back + biceps
Day 3: legs (single leg day, comprehensive)
Day 4: shoulders + arms
Who: intermediate to advanced, focused sessions.
```

### 5 days/week
```
Option A — PPL + Upper + Lower
Push / Pull / Legs / Upper / Lower
Who: advanced, high recovery capacity.

Option B — Body Part 5-day
Chest / Back / Legs / Shoulders / Arms — one per day
Who: advanced, bodybuilding focus.
```

### 6 days/week
```
PPL × 2
Push A / Pull A / Legs A / Push B / Pull B / Legs B
A sessions: strength focus (lower reps, heavier)
B sessions: hypertrophy focus (higher reps, more isolation)
Who: advanced, very high recovery capacity.
```

### Muscle group targets across all plans

Complete list of muscle groups the exercise-recommender will ever handle:
```
chest
back_vertical     (lats, teres major — lat pulldown movements)
back_horizontal   (mid/upper traps, rhomboids — rowing movements)
shoulders
rear_delts
triceps
biceps
quads
hamstrings
glutes
calves
core
```

---

## 7. RAG Architecture

### 7a. Two collections in Qdrant

Qdrant does not have namespaces. The equivalent is separate collections.
Each collection holds its own points (documents), vectors, and payload.

```
collection: tamrena_principles
  Content: recovery science, progressive overload, periodization,
           rep range research, deload protocols, injury prevention
  Who queries: every sub-agent queries this on every call
  Filtering: none — all principles apply to everyone

collection: tamrena_muscle_specific
  Content: exercise mechanics, muscle anatomy, movement pattern guides,
           compound and isolation exercise documentation
  Who queries: exercise-recommender sub-agent
  Filtering: payload filter on "muscle" field before search runs
```

Qdrant naming map vs Pinecone:
```
Pinecone           →   Qdrant
─────────────────────────────
Index              →   Collection
Namespace          →   Collection (separate)
Vector/Record      →   Point
Metadata           →   Payload
metadata filter    →   payload filter (Filter + FieldCondition)
top_k              →   limit
alpha (hybrid)     →   Fusion.RRF (Reciprocal Rank Fusion)
dotproduct metric  →   Distance.COSINE (for bge-m3)
```

### 7b. Why two collections and not one per muscle group

Compound movements (Romanian Deadlift, Barbell Row, etc.) cover multiple
muscle groups. One collection per muscle group forces duplication.

Solution: one `tamrena_muscle_specific` collection with payload tags on
every point. The document lives once. Multiple agents find it through
their own payload filter.

```
Romanian Deadlift point
  payload: {"muscle": ["hamstrings", "glutes", "lower_back"]}
  → legs agent finds it via hamstrings filter
  → back agent finds it via lower_back filter
  → same point, no duplication
```

Qdrant requires a payload index on the `muscle` field for fast filtering.
Created once at collection setup time — not per-query:

```python
from qdrant_client.models import PayloadSchemaType

client.create_payload_index(
    collection_name="tamrena_muscle_specific",
    field_name="muscle",
    field_schema=PayloadSchemaType.KEYWORD,
)
```

### 7c. Point payload schema

Every point in `tamrena_muscle_specific` collection:
```json
{
  "content":    "...",
  "muscle":     ["chest", "triceps"],
  "collection": "muscle_specific"
}
```

Every point in `tamrena_principles` collection (no muscle tag needed):
```json
{
  "content":    "...",
  "topic":      "progressive_overload",
  "applies_to": "all"
}
```

### 7d. Local models used for RAG (no API calls)

All embedding and reranking runs locally. Zero API calls in the RAG pipeline.

**Dense embeddings — BAAI/bge-m3**
```
Model:     BAAI/bge-m3
Library:   sentence-transformers
Dimension: 1024
Why:       Strong multilingual model, handles exercise science terminology well.
           Supports long contexts (up to 8192 tokens).
Download:  automatic on first use via sentence-transformers
```

**Sparse embeddings — BM25**
```
Library:  pinecone-text  (BM25Encoder class)
Why:      Fully local, no API — the library is just BM25 math, it does not
          require a Pinecone account or any network connection.
          BM25 is critical for exact exercise name matching
          ("Bulgarian Split Squat" must match exactly, not just semantically).
          Output format (indices + values) converts directly to Qdrant SparseVector.
Fit:      Run once on full corpus at ingestion time → save params to disk.
          Load params at query time — do not refit on every query.
Qdrant:   BM25Encoder output → wrap in SparseVector(indices=..., values=...)
          before passing to Qdrant prefetch query.
```

**Reranker — BAAI/bge-reranker-v2-m3**
```
Model:   BAAI/bge-reranker-v2-m3
Library: sentence-transformers  (CrossEncoder class)
Why:     Pairs naturally with bge-m3 dense model. Local cross-encoder,
         no API call. Reranks top 20 hybrid results → returns top 5.
Download: automatic on first use via sentence-transformers
```

### 7e. Search pipeline per agent call

```
RAG QUERY (called twice per agent — once per collection)

collection: tamrena_muscle_specific
  1. Payload filter: muscle contains current_muscle_group
     → Qdrant applies this before any vector search runs
     → uses the keyword index created at setup time (fast)

  2. Hybrid search via Prefetch + RRF fusion
     → Prefetch A: sparse BM25 query, limit=20
     → Prefetch B: dense bge-m3 query, limit=20
     → Qdrant fuses both result sets using Reciprocal Rank Fusion (RRF)
     → RRF rewards documents that rank well in BOTH sparse and dense results
     → returns top 20 fused candidates

  3. Reranker (bge-reranker-v2-m3, local CrossEncoder)
     → scores each of the 20 candidates against the original query
     → returns top 5 in relevance order

collection: tamrena_principles
  1. No payload filter — all principles relevant to every agent
  2. Same Prefetch + RRF hybrid search
  3. Same reranker → returns top 3

Agent receives: top 5 from tamrena_muscle_specific
              + top 3 from tamrena_principles
Total context passed to agent: 8 document chunks
```

Qdrant hybrid search code:

```python
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Prefetch, FusionQuery, Fusion,
    Filter, FieldCondition, MatchAny,
    SparseVector,
)
from sentence_transformers import SentenceTransformer, CrossEncoder
from pinecone_text.sparse import BM25Encoder

# loaded once at startup — not per query
dense_model   = SentenceTransformer("BAAI/bge-m3")
reranker      = CrossEncoder("BAAI/bge-reranker-v2-m3")
bm25_encoder  = BM25Encoder().load("models/bm25_params.json")
qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))

def search_rag(query: str, muscle_group: str = None) -> str:
    # encode query locally — no API call
    dense_vector  = dense_model.encode(query).tolist()
    sparse_output = bm25_encoder.encode_queries(query)
    sparse_vector = SparseVector(
        indices=sparse_output["indices"],
        values=sparse_output["values"],
    )

    results = []

    # ── tamrena_muscle_specific ──────────────────────────────────
    muscle_results = qdrant_client.query_points(
        collection_name="tamrena_muscle_specific",
        prefetch=[
            Prefetch(query=sparse_vector, using="sparse", limit=20),
            Prefetch(query=dense_vector,  using="dense",  limit=20),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=20,
        query_filter=Filter(
            must=[FieldCondition(
                key="muscle",
                match=MatchAny(any=[muscle_group])
            )]
        ) if muscle_group else None,
    ).points

    # ── tamrena_principles ───────────────────────────────────────
    principles_results = qdrant_client.query_points(
        collection_name="tamrena_principles",
        prefetch=[
            Prefetch(query=sparse_vector, using="sparse", limit=20),
            Prefetch(query=dense_vector,  using="dense",  limit=20),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=20,
    ).points

    # ── rerank both result sets ──────────────────────────────────
    def rerank(candidates: list, top_n: int) -> list:
        if not candidates:
            return []
        pairs = [(query, p.payload["content"]) for p in candidates]
        scores = reranker.predict(pairs)
        ranked = sorted(zip(scores, candidates), reverse=True)
        return [c for _, c in ranked[:top_n]]

    top_muscle     = rerank(muscle_results,     top_n=5)
    top_principles = rerank(principles_results, top_n=3)

    # ── format for agent ─────────────────────────────────────────
    all_chunks = top_muscle + top_principles
    return "\n\n---\n\n".join(p.payload["content"] for p in all_chunks)
```

### 7f. Corpus ingestion pipeline

Source: fitness/exercise science book(s) + curated exercise documents

```
book PDF
  → pymupdf4llm converts to markdown (preserves headings and structure)
  → RecursiveCharacterTextSplitter
      chunk_size=800
      chunk_overlap=150   ← prevents concepts being cut mid-thought
  → for each chunk:
      Azure OpenAI gpt-4.1-mini labels muscle groups  ← only API call here
      → assigns namespace: principles or muscle_specific
      → assigns metadata: muscle tags, movement_type, experience_level
  → bge-m3 creates dense vector (local, no API)
  → BM25Encoder creates sparse vector (local, no API)
  → upsert to Qdrant collection as a Point with named vectors + payload
```

Run once to build corpus. Re-run only when adding new books or documents.

**Qdrant collection setup (run once before any ingestion):**
```python
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, SparseVectorParams, SparseIndexParams,
    Distance, PayloadSchemaType,
)

client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))

for collection_name in ["tamrena_muscle_specific", "tamrena_principles"]:
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config={
            "dense": VectorParams(size=1024, distance=Distance.COSINE),
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(
                index=SparseIndexParams(on_disk=False)
            ),
        },
    )

# payload index on muscle field — required for fast filtering
client.create_payload_index(
    collection_name="tamrena_muscle_specific",
    field_name="muscle",
    field_schema=PayloadSchemaType.KEYWORD,
)
```

**Upserting a point:**
```python
import uuid
from qdrant_client.models import PointStruct, SparseVector

dense_vector  = dense_model.encode(chunk_text).tolist()
sparse_output = bm25_encoder.encode_documents([chunk_text])[0]

client.upsert(
    collection_name=collection_name,   # tamrena_muscle_specific or tamrena_principles
    points=[
        PointStruct(
            id=str(uuid.uuid4()),
            vector={
                "dense":  dense_vector,
                "sparse": SparseVector(
                    indices=sparse_output["indices"],
                    values=sparse_output["values"],
                ),
            },
            payload={
                "content":    chunk_text,
                "muscle":     muscle_labels,   # [] for principles collection
                "collection": collection_name,
            },
        )
    ],
)
```

**Folder structure for manually curated documents:**
```
corpus/
  muscle_specific/
    chest/
    back/
    legs/
    shoulders/
    arms/
    compounds/        ← multi-muscle docs, labeled with all relevant muscles
  principles/
    recovery/
    programming/
    periodization/
```

Folder name becomes the muscle payload tag automatically during ingestion.

**BM25 fitting and saving (run once at ingestion, load at query time):**
```python
from pinecone_text.sparse import BM25Encoder

# at ingestion time — fit on entire corpus text
encoder = BM25Encoder()
encoder.fit(all_document_texts)
encoder.dump("models/bm25_params.json")

# at query time — load saved params, do not refit
encoder = BM25Encoder()
encoder.load("models/bm25_params.json")
```

---

## 8. Exercise Database (MongoDB)

MongoDB collection. Queried directly by exercise-recommender sub-agent
via a tool function. No MCP wrapper needed for MVP.

### 8a. Collection schema

```python
# each document in the exercises collection
{
    "name":               "Bulgarian Split Squat",
    "primary_muscle":     "quads",
    "secondary_muscles":  ["glutes", "hamstrings"],
    "movement_type":      "unilateral",      # compound / isolation / unilateral
    "equipment":          "dumbbell",         # barbell / dumbbell / cable / machine / bodyweight
    "difficulty":         "intermediate",     # beginner / intermediate / advanced
    "bilateral":          False,              # False = unilateral movement
    "contraindications":  []                  # e.g. ["knee_pain", "lower_back"]
}
```

### 8b. How sub-agent queries it

```python
from pymongo import MongoClient

client = MongoClient(os.getenv("MONGODB_URI"))
exercises = client["tamrena"]["exercises"]

def search_exercise_db(
    muscle_group: str,
    movement_type: str = "all",
    exclude_contraindication: str = None
) -> str:
    query = {"primary_muscle": muscle_group}
    if movement_type != "all":
        query["movement_type"] = movement_type
    if exclude_contraindication:
        query["contraindications"] = {"$nin": [exclude_contraindication]}

    results = exercises.find(query, {"_id": 0, "name": 1, "equipment": 1, "difficulty": 1})
    items = list(results)
    if not items:
        return f"No exercises found for [{muscle_group}] [{movement_type}]"
    return (
        f"DB results — muscle: [{muscle_group}] | type: [{movement_type}]\n"
        + "\n".join(f"  • {r['name']} ({r['equipment']}, {r['difficulty']})" for r in items)
    )
```

Source: 1,324 exercises dataset from GitHub. Seed script loads them into MongoDB on first run.

---

## 9. Tech Stack & Libraries

### LLM — Azure OpenAI (only external API)
```
langchain-openai       pip install langchain-openai
                       AzureChatOpenAI — supervisor + all sub-agents
                       Model: gpt-4.1-mini via Azure deployment
```

**Important:** pass an initialized AzureChatOpenAI instance to deepagents,
not a model string. Model strings only work for direct OpenAI, not Azure.

```python
from langchain_openai import AzureChatOpenAI

llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    temperature=0.3,
)

# used in create_deep_agent and in every sub-agent dict
create_deep_agent(model=llm, ...)
EXERCISE_RECOMMENDER = {"model": llm, ...}
```

### Agent framework
```
deepagents             pip install deepagents
python-dotenv          pip install python-dotenv
```

### Vector store
```
qdrant-client          pip install qdrant-client
langchain-qdrant       pip install langchain-qdrant
pinecone-text          pip install pinecone-text
                       BM25Encoder only — used for sparse vector math locally.
                       No Pinecone account needed. Output converts to
                       Qdrant SparseVector(indices=..., values=...).
```

Qdrant runs locally via Docker. Two collections, each with named vectors
"dense" (Distance.COSINE, size=1024) and "sparse" (SparseVectorParams).
No cloud account. No API key. Data stored in local qdrant_storage/ folder.

**Run Qdrant locally:**
```bash
docker run -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage:z \
  qdrant/qdrant
```

Port 6333 is the REST + gRPC API. Port 6334 is the web dashboard UI
(http://localhost:6334) — useful for inspecting collections during development.

### Local embedding model (no API)
```
sentence-transformers  pip install sentence-transformers
torch                  pip install torch
                       Model: BAAI/bge-m3
                       Downloaded once, stored locally in models/
                       Dimension: 1024
```

### Local reranker model (no API)
```
sentence-transformers  (same install as above)
                       CrossEncoder class
                       Model: BAAI/bge-reranker-v2-m3
                       Downloaded once, stored locally in models/
```

### Exercise database
```
pymongo                pip install pymongo
                       MongoDB connection for exercise collection
```

### Document processing
```
pymupdf4llm            pip install pymupdf4llm
                       PDF → markdown, preserves heading structure

langchain              pip install langchain
                       RecursiveCharacterTextSplitter
```

### API layer
```
fastapi                pip install fastapi
uvicorn                pip install "uvicorn[standard]"
python-multipart       pip install python-multipart
                       Required for UploadFile / Form() to work in FastAPI
```

### Monitoring & observability
```
langsmith              pip install langsmith
                       Set env vars — tracing is automatic through LangChain
                       Every agent step, tool call, and sub-agent dispatch is logged
```

---

## 10. Environment Variables

```dotenv
# ── LLM (only external API call) ─────────────────────────────
AZURE_OPENAI_API_KEY=your_key_here
AZURE_OPENAI_ENDPOINT=https://itiworkshop2026aifoundry.services.ai.azure.com/openai/v1
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4.1-mini
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# ── Vector store (Qdrant local) ───────────────────────────────
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_MUSCLE=tamrena_muscle_specific
QDRANT_COLLECTION_PRINCIPLES=tamrena_principles

# ── Exercise database ─────────────────────────────────────────
MONGODB_URI=mongodb+srv://...

# ── Monitoring ────────────────────────────────────────────────
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT=tamrena
```

No Pinecone key. No Cohere key. No OpenAI key. No HuggingFace token (bge models are public).
Qdrant runs fully local — no account, no API key, no network dependency.

---

## 11. Project File Structure

```
tamrena/
│
├── prompts/                          ← agent system prompts as MD files
│   ├── supervisor.md                 ← UPDATED: DAY MAP computation + flag routing table
│   ├── exercise_recommender.md       ← UPDATED: max_sets budget enforcement + BF% soft hint
│   └── plan_assembler.md             ← UPDATED: session duration enforcement + trim rules
│
├── agents/
│   ├── supervisor.py                 ← build_supervisor() — creates AzureChatOpenAI + agent
│   ├── subagents.py                  ← UPDATED: validate_session_duration added to Plan Assembler tools
│   └── inbody_parser.py              ← VLM tool (Azure OpenAI vision call)
│
├── tools/
│   ├── memory.py                     ← UPDATED: read_plan_memory, write_plan_memory,
│   │                                            validate_session_duration,
│   │                                            init_plan_progress, mark_step_done,
│   │                                            get_plan_progress,
│   │                                            validate_plan_completeness (new)
│   ├── rag.py                        ← search_rag (Qdrant + local models)
│   └── database.py                   ← search_exercise_db (MongoDB)
│
├── rag/
│   ├── ingest.py                     ← full pipeline: PDF → split → label → embed → store
│   ├── label.py                      ← Azure OpenAI labels each chunk with muscle metadata
│   └── embed.py                      ← local bge-m3 dense + BM25 sparse vectors
│
├── models/                           ← local model storage (not committed to git)
│   ├── bge-m3/                       ← downloaded by sentence-transformers on first run
│   ├── bge-reranker-v2-m3/           ← downloaded by sentence-transformers on first run
│   └── bm25_params.json              ← BM25 fitted on corpus, saved here, loaded at runtime
│
├── corpus/
│   ├── muscle_specific/
│   │   ├── chest/
│   │   ├── back/
│   │   ├── legs/
│   │   ├── shoulders/
│   │   ├── arms/
│   │   └── compounds/        ← multi-muscle docs, labeled with all relevant muscles
│   └── principles/
│       ├── recovery/
│       ├── programming/
│       └── periodization/
│
├── database/
│   └── seed.py                       ← loads 1,324 exercises from dataset into MongoDB
│
├── api/                              ← FastAPI application
│   ├── main.py                       ← FastAPI app, router mounting, uvicorn entry point
│   ├── routes/
│   │   ├── health.py                 ← GET /health — liveness + readiness probe
│   │   ├── ingest.py                 ← POST /ingest — document ingestion (background task)
│   │   └── plan.py                   ← POST /plan — workout plan generation
│   ├── schemas/
│   │   ├── request.py                ← Pydantic models for request validation
│   │   └── response.py               ← Pydantic models for response shapes
│   └── dependencies.py               ← shared FastAPI deps (DB clients, model singletons)
│
├── sessions/                         ← created at runtime, gitignored
│   └── {session_id}/
│       └── plan.md                   ← shared MD memory file for this run
│
├── requirements.txt
├── .env                              ← gitignored
└── .env.example
```

---

## 12. API Endpoints (FastAPI)

Three endpoints. The agent pipeline and RAG pipeline are internal — these
are the only surfaces exposed to the outside.

### 12a. Endpoint overview

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | /health | Liveness + readiness probe | Used by pod/container orchestration |
| POST | /ingest | Upload document into RAG pipeline | Background task, returns job_id |
| POST | /plan | Generate personalised workout plan | Main product endpoint |

### 12b. GET /health

Used by Kubernetes liveness and readiness probes in production.
Checks every dependency the system needs to function.

```python
# routes/health.py

from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter()

@router.get("/health")
async def health_check():
    """
    Liveness + readiness probe.
    Returns 200 if all dependencies are reachable and models are loaded.
    Returns 503 if any critical dependency is down.
    """
    results = {}
    overall = "healthy"

    # MongoDB
    try:
        client.admin.command("ping")
        results["mongodb"] = "healthy"
    except Exception as e:
        results["mongodb"] = f"unhealthy: {str(e)}"
        overall = "unhealthy"

    # Qdrant
    try:
        qdrant_client.get_collections()
        results["qdrant"] = "healthy"
    except Exception as e:
        results["qdrant"] = f"unhealthy: {str(e)}"
        overall = "unhealthy"

    # Dense model (bge-m3) — check it is loaded in memory
    try:
        _ = dense_model.encode("test")
        results["dense_model"] = "healthy"
    except Exception as e:
        results["dense_model"] = f"unhealthy: {str(e)}"
        overall = "unhealthy"

    # Reranker (bge-reranker-v2-m3)
    try:
        _ = reranker.predict([("test query", "test passage")])
        results["reranker"] = "healthy"
    except Exception as e:
        results["reranker"] = f"unhealthy: {str(e)}"
        overall = "unhealthy"

    # BM25 encoder — check params file is loaded
    try:
        _ = bm25_encoder.encode_queries("test")
        results["bm25_encoder"] = "healthy"
    except Exception as e:
        results["bm25_encoder"] = f"unhealthy: {str(e)}"
        overall = "unhealthy"

    status_code = 200 if overall == "healthy" else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
            "dependencies": results,
        }
    )
```

**Response example — all healthy:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00Z",
  "version": "1.0.0",
  "dependencies": {
    "mongodb":     "healthy",
    "qdrant":      "healthy",
    "dense_model": "healthy",
    "reranker":    "healthy",
    "bm25_encoder":"healthy"
  }
}
```

**Response example — one dependency down (returns 503):**
```json
{
  "status": "unhealthy",
  "timestamp": "2025-01-15T10:30:00Z",
  "version": "1.0.0",
  "dependencies": {
    "mongodb":     "unhealthy: connection timed out",
    "qdrant":      "healthy",
    "dense_model": "healthy",
    "reranker":    "healthy",
    "bm25_encoder":"healthy"
  }
}
```

### 12c. POST /ingest

Accepts a PDF or text document and pushes it through the full RAG
ingestion pipeline: extract → split → label → embed → store in Qdrant.

Runs as a FastAPI `BackgroundTask` because ingestion is slow (seconds
to minutes depending on document size). Returns a `job_id` immediately.
Status can be checked by looking at the job log.

```python
# routes/ingest.py

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks
from typing import Optional
import uuid, tempfile, os

router = APIRouter()

@router.post("/ingest")
async def ingest_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    namespace: str = Form(...),              # "principles" or "muscle_specific"
    muscle_group: Optional[str] = Form(None) # required if namespace=muscle_specific
):
    """
    Upload a PDF or text document into the RAG pipeline.

    The file is saved to a temp path and the ingestion pipeline runs
    in the background. Returns immediately with a job_id.

    namespace=muscle_specific requires muscle_group to be set.
    namespace=principles does not need muscle_group.
    """
    # validate
    if namespace == "muscle_specific" and not muscle_group:
        raise HTTPException(
            status_code=422,
            detail="muscle_group is required when namespace is muscle_specific"
        )

    allowed_types = ["application/pdf", "text/plain", "text/markdown"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type}"
        )

    # save upload to temp file so background task can read it after response
    job_id = str(uuid.uuid4())
    suffix = ".pdf" if file.content_type == "application/pdf" else ".txt"
    tmp_path = f"/tmp/{job_id}{suffix}"

    contents = await file.read()
    with open(tmp_path, "wb") as f:
        f.write(contents)

    # fire and forget
    background_tasks.add_task(
        run_ingestion_pipeline,
        file_path=tmp_path,
        namespace=namespace,
        muscle_group=muscle_group,
        job_id=job_id,
        original_filename=file.filename,
    )

    return {
        "job_id":      job_id,
        "status":      "processing",
        "filename":    file.filename,
        "namespace":   namespace,
        "muscle_group": muscle_group,
        "message":     "Document received. Ingestion running in background."
    }

async def run_ingestion_pipeline(
    file_path: str,
    namespace: str,
    muscle_group: Optional[str],
    job_id: str,
    original_filename: str,
):
    """
    Background task. Full pipeline:
      PDF → markdown → split → LLM label → embed (local) → Qdrant upsert
    """
    try:
        from rag.ingest import ingest_file
        chunk_count = ingest_file(
            file_path=file_path,
            namespace=namespace,
            muscle_group=muscle_group,
        )
        print(f"[{job_id}] Ingested {original_filename}: {chunk_count} chunks → {namespace}")
    except Exception as e:
        print(f"[{job_id}] Ingestion failed for {original_filename}: {e}")
    finally:
        os.remove(file_path)   # clean up temp file
```

**Request (multipart/form-data):**
```
file          required    PDF or text file to ingest
namespace     required    "principles" or "muscle_specific"
muscle_group  optional    required only when namespace=muscle_specific
                          one of: chest / back / legs / shoulders / arms /
                                  rear_delts / triceps / biceps / compounds
```

**Response (immediate, 200):**
```json
{
  "job_id":       "a1b2c3d4-...",
  "status":       "processing",
  "filename":     "hypertrophy_guide.pdf",
  "namespace":    "muscle_specific",
  "muscle_group": "chest",
  "message":      "Document received. Ingestion running in background."
}
```

### 12d. POST /plan

Main product endpoint. Accepts the InBody scan file and all user form
fields. Runs the full agent pipeline and returns the workout plan.

This call is synchronous — it waits for the full agent pipeline to
complete before returning. Agent pipeline typically takes 30–90 seconds.
Frontend should show a loading/progress state.

```python
# routes/plan.py

from fastapi import APIRouter, UploadFile, File, Form
from typing import Optional
import uuid, os, base64

router = APIRouter()

@router.post("/plan")
async def generate_plan(
    # InBody scan — image or PDF
    inbody_file: UploadFile = File(...),

    # Required fields
    goal: str = Form(...),              # hypertrophy/strength/fat_loss/general_fitness
    days_per_week: int = Form(...),     # 2-6
    experience: str = Form(...),        # beginner/intermediate/advanced
    session_duration: str = Form(...),  # 45min/60min/90min

    # Should-have fields
    injuries: Optional[str] = Form(None),   # free text, e.g. "left shoulder — no overhead"
    priority: Optional[str] = Form(None),   # free text, e.g. "I want bigger arms"
    age: Optional[int] = Form(None),

    # Nice-to-have fields
    sleep_quality: Optional[str] = Form(None),    # good/average/poor
    job_type: Optional[str] = Form(None),          # desk/light_physical/heavy_physical
    current_program: Optional[str] = Form(None),   # what they've been doing
):
    """
    Generate a personalised workout plan.

    Accepts the InBody scan (image or PDF) plus the user intake form fields.
    Runs the full multi-agent pipeline:
      1. VLM parses InBody scan
      2. Supervisor creates plan + computes DAY MAP
      3. Exercise recommender runs per muscle group (with budget + scoped flags)
      4. Plan assembler builds weekly schedule + enforces session duration
    
    Returns the complete workout plan. Takes 30-90 seconds.
    """
    # validate enum fields
    valid_goals = ["hypertrophy", "strength", "fat_loss", "general_fitness"]
    valid_experience = ["beginner", "intermediate", "advanced"]
    valid_durations = ["45min", "60min", "90min"]

    if goal not in valid_goals:
        raise HTTPException(422, f"goal must be one of {valid_goals}")
    if not (2 <= days_per_week <= 6):
        raise HTTPException(422, "days_per_week must be between 2 and 6")
    if experience not in valid_experience:
        raise HTTPException(422, f"experience must be one of {valid_experience}")
    if session_duration not in valid_durations:
        raise HTTPException(422, f"session_duration must be one of {valid_durations}")

    # read InBody file — agent will receive it as base64 for VLM
    inbody_bytes = await inbody_file.read()
    inbody_b64 = base64.b64encode(inbody_bytes).decode("utf-8")
    inbody_content_type = inbody_file.content_type   # image/jpeg, image/png, application/pdf

    # build user query string the supervisor will read
    user_query = _build_user_query(
        goal=goal,
        days_per_week=days_per_week,
        experience=experience,
        session_duration=session_duration,
        injuries=injuries,
        priority=priority,
        age=age,
        sleep_quality=sleep_quality,
        job_type=job_type,
        current_program=current_program,
    )

    # create session folder for the shared MD memory file
    session_id = str(uuid.uuid4())
    os.makedirs(f"sessions/{session_id}", exist_ok=True)

    # run the agent pipeline
    from agents.supervisor import build_supervisor
    supervisor = build_supervisor()

    result = supervisor.invoke({
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": inbody_content_type,
                        "data": inbody_b64,
                    }
                },
                {
                    "type": "text",
                    "text": f"SESSION_ID: {session_id}\n\n{user_query}"
                }
            ]
        }]
    })

    final_plan = result["messages"][-1].content

    return {
        "session_id":     session_id,
        "plan":           final_plan,
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "session_file":   f"sessions/{session_id}/plan.md",
    }


def _build_user_query(**fields) -> str:
    """Formats all form fields into the structured query the supervisor reads."""
    lines = [
        "USER INTAKE FORM",
        "─────────────────────────────────────",
        f"Goal             : {fields['goal']}",
        f"Days per week    : {fields['days_per_week']}",
        f"Experience       : {fields['experience']}",
        f"Session duration : {fields['session_duration']}",
    ]
    if fields.get("injuries"):
        lines.append(f"Injuries/limits  : {fields['injuries']}")
    if fields.get("priority"):
        lines.append(f"Priority focus   : {fields['priority']}")
    if fields.get("age"):
        lines.append(f"Age              : {fields['age']}")
    if fields.get("sleep_quality"):
        lines.append(f"Sleep quality    : {fields['sleep_quality']}")
    if fields.get("job_type"):
        lines.append(f"Job type         : {fields['job_type']}")
    if fields.get("current_program"):
        lines.append(f"Current program  : {fields['current_program']}")
    return "\n".join(lines)
```

**Request (multipart/form-data):**
```
inbody_file      required    InBody scan — image (jpg/png) or PDF
goal             required    hypertrophy / strength / fat_loss / general_fitness
days_per_week    required    integer 2–6
experience       required    beginner / intermediate / advanced
session_duration required    45min / 60min / 90min
injuries         optional    free text — body part + what it limits
priority         optional    free text — what they want to focus on
age              optional    integer
sleep_quality    optional    good / average / poor
job_type         optional    desk / light_physical / heavy_physical
current_program  optional    free text — what they have been doing
```

**Response (after full pipeline completes):**
```json
{
  "session_id": "a1b2c3d4-...",
  "plan": "## Your Personalised Workout Plan\n\n### Day 1 — Monday: Chest...",
  "generated_at": "2025-01-15T10:35:42Z",
  "session_file": "sessions/a1b2c3d4-.../plan.md"
}
```

### 12e. App entry point

```python
# api/main.py

from fastapi import FastAPI
from api.routes import health, ingest, plan

app = FastAPI(
    title="Tamrena AI",
    description="Personalised workout plan generation via multi-agent pipeline",
    version="1.0.0",
)

app.include_router(health.router, tags=["health"])
app.include_router(ingest.router, prefix="/ingest", tags=["ingestion"])
app.include_router(plan.router, prefix="/plan", tags=["plan"])

# run: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 13. Key Design Decisions (for Claude Code reference)

**Why sequential not parallel sub-agents:**
Each exercise-recommender reads the shared MD file which contains previous
agents' output. If they ran in parallel they would write to the file
simultaneously and corrupt each other's output. Sequential is intentional.

**Why one exercise-recommender not one per muscle group:**
The agent is called with a different task prompt each time — the muscle group,
intensity, and context are in the prompt not in the agent definition.
Adding shoulders to the plan next month requires no code change.

**Why MD file for memory not deepagents virtual filesystem:**
deepagents built-in filesystem (write_file / read_file) is per-agent and
not shared between supervisor and sub-agents. Real Python file I/O on the
host filesystem is shared because all agent tool functions run as Python
functions on the same machine.

**Why metadata filter before hybrid search:**
Without the filter, BM25 might score a back document high on a chest query
because both documents contain words like "pressing" and "compound".
The filter eliminates non-relevant muscle groups before search runs,
giving hybrid search a clean pool to work on.

**Why chunk_overlap=150 in the splitter:**
Exercise science content often discusses a concept across 2-3 paragraphs.
A 0-overlap split can cut a programming recommendation mid-thought.
150 token overlap ensures concepts that span chunk boundaries are captured
in at least one complete chunk.

**Why BAAI/bge-m3 for dense embeddings:**
Strong performance on technical domain content. Multilingual (relevant
if exercise science sources include non-English content). 1024 dimensions
gives good retrieval accuracy. The paired reranker (bge-reranker-v2-m3)
is trained to complement it, so dense retrieval + reranking stay consistent.

**Why BM25 matters here specifically:**
Exercise names are exact terms — "Bulgarian Split Squat", "Romanian Deadlift".
Semantic search alone will drift to synonyms. BM25 anchors exact name
matching. Hybrid is critical for this domain more than general text retrieval.

**Why AzureChatOpenAI instance not model string:**
deepagents model strings like "openai:gpt-4.1-mini" call OpenAI directly.
Azure OpenAI uses a different endpoint and auth flow. You must pass an
initialized AzureChatOpenAI object so LangChain routes through Azure.

**Why DAY MAP is the Supervisor's responsibility, not the Plan Assembler's:**
The Supervisor is the only agent that knows both the split structure and
the session_duration at the same time. If the Plan Assembler computed
the budget, it would have to re-derive the split logic from the MD file,
duplicating the Supervisor's reasoning. The Supervisor writes the budget
once as the authoritative source; all subsequent agents just read it.
The DAY MAP also constrains exercise-recommenders before they run — not
just the assembler after the fact.

**Why validate_session_duration is a Python tool function, not a prompt rule:**
A prompt rule asking the Plan Assembler to "check session duration" relies
on the LLM doing arithmetic correctly on every call. A Python function does
the arithmetic deterministically: it parses the scheduled sets from the MD
file, runs the formula, and returns a pass/fail with exact numbers. The LLM
cannot silently miscalculate a tool function result the way it can with
in-context arithmetic.

**Why flag routing is in the Supervisor prompt, not the exercise-recommender prompt:**
The exercise-recommender has no way to know which flags are relevant to it
without re-reading the InBody analysis and reasoning about anatomy. That
reasoning would happen on every recommender call (N times per plan).
The Supervisor does it once during dispatch, filters the flags, and passes
only what's relevant. This also prevents the bug where ARM_ASYMMETRY gets
applied to leg exercises — the recommender never sees that flag if it is
not in its task prompt.

**Why a paradigm abstraction layer instead of expanding the goal enum:**
Mapping goal directly to agent behavior is whack-a-mole — every new phrasing
or goal type requires a code change, and an unrecognized goal silently applies
hypertrophy defaults (or crashes). The paradigm layer decouples user language
from agent rules. The Supervisor translates the raw goal into one of 7 paradigms
at step 0, writes the paradigm to the plan file, and all downstream agents read
that field. An unknown goal defaults to general_fitness with a logged note —
no crash, no silent wrong output. Adding support for a new goal phrasing
requires only updating the classification mapping in supervisor.md; the agent
logic, tools, and plan structure are unchanged. The paradigm is also a first-
class audit field in the plan file — LangSmith traces show misclassifications
across sessions, making it easy to tune the mapping over time.

**Why strength sessions use different DAY MAP time-per-set values:**
The 3.5 min/set formula for "hard" sessions assumes 2-3 min rest between sets —
correct for hypertrophy. Strength training at 85-95% 1RM requires 4-5 min rest
between primary movement sets. Using 3.5 min gives a set budget of 22 for a
90-min session, which is a hypertrophy number. A realistic strength session at
90 min produces 12-15 working sets. Using the correct 6.0 min/set for heavy
zones and 5.0 min average prevents the exercise-recommender receiving an
inflated budget that it cannot fill with meaningful strength work.

**Why BF% elevated is a soft hint and not a fixed rep override:**
Rep ranges for hypertrophy are determined by mechanical tension, metabolic
stress, and load — not by body fat percentage. The original design used
ELEVATED_BF as a hard flag that forced 12 reps on every medium exercise.
This produced a flat, monotonous rep scheme and caused the back agent to
ignore its hard-intensity prescription (which should use 6-8 reps) and use
12 reps instead. The flag now expresses a preference (prefer the upper end
of the range) without overriding the intensity prescription rules.

**Why leg days need different task prompts for 4-day Upper/Lower:**
The exercise-recommender is one agent called with different prompts. If the
same prompt is sent twice for two leg days, the agent has no reason to select
different exercises — it will produce identical prescriptions. The Supervisor
must explicitly state a different primary muscle emphasis in each leg day task
prompt. This produces genuine variation (squat-pattern vs RDL-pattern days)
without any code change to the recommender.

**Why progress tracking is a separate JSON file, not parsed from the MD prose:**
Early designs planned to have the Supervisor re-read the shared MD file and count
`✓` markers to know how many muscle groups were done. That relies on an LLM
correctly formatting a marker in free text every time, and another LLM correctly
counting/parsing it back out — both are avoidable failure points. `progress.json`
is written and read only via tool functions with structured parameters
(`mark_step_done(muscle_group)`, `get_plan_progress()`), so there is nothing for
either side to mis-format or miscount. See Section 5d and Section 14 v1.2.

**Why the exercise-recommender marks its own completion, not the Supervisor:**
`mark_step_done` is called by the recommender as the natural last step after
`write_plan_memory` — no extra round trip, since the Supervisor already receives
the recommender's output synchronously via the blocking `task()` call. The
Supervisor does not trust this mark blindly, though: it independently confirms via
`get_plan_progress` that the muscle group it just dispatched is the one that got
marked, before advancing. Self-reported completion plus an independent
cross-check catches a recommender that fails silently — self-reporting alone
would not.

**Why python-multipart is needed:**
FastAPI's `UploadFile` and `Form()` do not work without it. It must be
installed even though it is never imported directly — FastAPI uses it
internally to parse multipart/form-data requests. Forgetting it causes
a silent 422 error on every file upload endpoint.

**Why /plan is synchronous not async:**
The agent pipeline takes 30–90 seconds. Making it async with a polling
endpoint adds complexity without benefit at this stage. The frontend
holds the connection open and shows a loading state. If this becomes
a problem at scale, convert to a job queue pattern (return job_id,
poll GET /plan/{job_id}/status) — same pattern as /ingest.

**Build order for Claude Code:**
1. MongoDB seed (exercises dataset → MongoDB collection)
2. Local model loader (download bge-m3 + reranker, verify they run)
3. RAG ingestion pipeline (corpus → Qdrant)
4. Tool functions (memory.py — includes validate_session_duration, rag.py, database.py)
5. Agent definitions (subagents.py with updated Plan Assembler tools, supervisor.py)
6. Prompt files (supervisor.md with DAY MAP + flag routing,
                  exercise_recommender.md with budget enforcement + BF% soft hint,
                  plan_assembler.md with session enforcement + trim rules)
7. FastAPI app (api/main.py + routes + schemas)
8. Smoke test: hit /health, then /plan with a sample InBody

---

## 14. Change Log

This section records architectural changes made after initial design.
Reference when reviewing diffs or testing updated behaviour.

### v1.1 — Session duration enforcement + flag routing fixes

**Problem diagnosed:**
A test run with a 4-day Upper/Lower plan and 75-minute sessions produced
a Day 3 with 48 sets (Arms + Chest + Shoulders combined) estimated at
~145 minutes — nearly double the session limit. Two additional bugs:
ARM_ASYMMETRY flag was incorrectly applied to leg exercises (legs are
balanced per InBody segmental data), and both leg days received identical
exercise prescriptions.

**Files changed:**

| File | Change |
|---|---|
| `prompts/supervisor.md` | Added DAY MAP computation (step 5b), flag routing table (step 5c), leg day differentiation rule |
| `prompts/exercise_recommender.md` | Added max_sets budget check (step 8), updated BF% rule to soft hint |
| `prompts/plan_assembler.md` | Added DAY MAP read (step 2b), session enforcement + trim logic (steps 3b–3d), validate_session_duration call (step 3d) |
| `tools/memory.py` | Added `validate_session_duration()` function |
| `agents/subagents.py` | Added `validate_session_duration` to Plan Assembler tools list |

**What did NOT change:**
All RAG code (rag.py, ingest.py, embed.py, label.py), MongoDB code (database.py),
all API routes, all environment variables, agent model definitions, Qdrant setup.

**Root cause:**
Constraints flowed bottom-up (specialist agents generated volume freely →
assembler tried to schedule it all). Fix: constraints now flow top-down
(Supervisor computes budget and assigns muscles to days → specialists work
within that budget → assembler enforces it with a tool function check).

**How to verify the fix works:**
1. Run /plan with session_duration=75min and days_per_week=4
2. Open sessions/{session_id}/plan.md after the run
3. Confirm DAY MAP section exists with max_sets per day
4. Confirm no day in the Weekly Schedule exceeds its max_sets budget
5. Confirm validate_session_duration returned PASS before final plan was written
6. Confirm ARM_ASYMMETRY note appears only in back/biceps/triceps sections, not legs
7. Confirm Leg Day A and Leg Day B have different primary exercises

### v1.2 — Progress tracking to prevent silently dropped muscle groups

**Problem diagnosed:**
A test run (session `8b6d0834-067e-4816-a175-739cd0eccd0d`, 4-day Upper/Lower,
intermediate, priority "bigger arms, lagging back") planned 5 muscle groups —
chest, back, shoulders, arms, legs — and set Back to `hard` intensity at
18 sets/week in the Training Plan Decisions section (it was the user's stated
priority). Only 4 exercise-recommender sections were ever written to `plan.md`
(Legs, Chest, Shoulders, Arms). Back was never dispatched, or its output was
never written — nothing in the pipeline caught this. The Plan Assembler ran
anyway, recorded "Back | 0 | 14-18 | under" in the Weekly Volume Summary, and
still labeled Day 1 and Day 3 headers "Upper Body (..., Back, ...)" despite zero
back exercises appearing in either day's table. The final plan was returned to
the user as complete.

**Root cause:**
There was no structured way for the Supervisor to know, independent of its own
running memory, which muscle groups had actually completed. Position tracking
relied on the Supervisor either remembering its own dispatch history or
re-parsing free-form prose in `plan.md` — both are lossy over a 5+ step
sequential loop with near-identical steps. The Plan Assembler had no gate
preventing it from assembling a plan around a missing muscle group; a 0-sets
row in a summary table was treated as informational, not a hard failure.

**Files changed:**

| File | Change |
|---|---|
| `prompts/supervisor.md` | Added step 5d (initialize progress tracker after DAY MAP), updated step 8 (cross-check `get_plan_progress` after every `task()` return), updated step 9 (only dispatch assembler when `all_done: true`) |
| `prompts/exercise_recommender.md` | Added step 9b (`mark_step_done` as last action before returning) |
| `prompts/plan_assembler.md` | Added step 0 (`validate_plan_completeness` hard gate before any scheduling work) |
| `tools/memory.py` | Added `init_plan_progress()`, `mark_step_done()`, `get_plan_progress()`, `validate_plan_completeness()` — see Section 5d |
| `agents/subagents.py` | Added `mark_step_done` to Exercise Recommender tools; added `validate_plan_completeness` to Plan Assembler tools |

**What did NOT change:**
The shared MD file format and content (Sections 5a-5c), RAG code, MongoDB code,
all API routes, all environment variables, agent model definitions, Qdrant setup.
Progress tracking is an additive, separate file (`progress.json`) alongside
`plan.md`, not a replacement for it.

**How to verify the fix works:**
1. Re-run the same inputs that produced session `8b6d0834-...` (4-day Upper/Lower,
   priority "bigger arms, lagging back", the sample InBody in Section 2 of
   `notebooks/Agent_exploration.ipynb`)
2. Open `sessions/{session_id}/progress.json` — confirm `expected` lists all 5
   muscle groups before any dispatch, and `completed` grows by exactly one entry
   per successful dispatch
3. Confirm the Supervisor's dispatch loop halts and retries if `get_plan_progress`
   ever shows a mismatch between the muscle group just dispatched and what got marked
4. Confirm the Plan Assembler refuses to run (returns the `INCOMPLETE` message from
   `validate_plan_completeness`) if a muscle group is deliberately skipped in a test
5. Confirm the final `plan.md` has a `##` prescription section for every muscle
   group named in the Training Plan Decisions section — no muscle group with a
   stated intensity/volume target should ever end up with 0 scheduled sets

### v1.3 — Programming paradigm abstraction layer

**Problem diagnosed:**
Case 03 test (advanced, strength goal, 5-day PPL+Upper+Lower) produced a plan
that applied hypertrophy logic throughout — MEV/MAV/MRV sets/week volume metric,
hard/medium/soft intensity zones with 6-8 rep ranges, 2-3 min rest, and a DAY
MAP budget of 22 sets/session calculated at 3.5 min/set. For a strength goal,
the correct metrics are: primary lift frequency (not sets/week), intensity zones
of heavy/volume/speed (not hard/medium/soft), rep windows of 1-5 main / 3-8
supplemental / 6-12 accessories, rest of 4-8 min for primary movements, and a
realistic session budget of 12-15 sets at ~5.0 min/set average. Additionally,
any unrecognized goal (e.g. athletic performance, endurance complement,
rehabilitation) would silently default to hypertrophy or crash — the closed enum
provided no fallback.

**Root cause:**
The goal field mapped directly to agent behavior with no translation layer.
The Supervisor had one volume/intensity framework (hypertrophy) and applied it
regardless of the goal field value. No goal-switching logic existed in any prompt.

**Files changed:**

| File | Change |
|---|---|
| `prompts/supervisor.md` | Added step 0 (goal → paradigm classification before parse_inbody); updated steps 3-5 to reference paradigm; updated volume table to be paradigm-conditional; updated DAY MAP time/set values to be paradigm-conditional |
| `prompts/exercise_recommender.md` | Replaced single intensity table with paradigm-conditional tables (7 paradigms × their zones) |
| `tamrena_architecture_2.md` | Added Section 4e (7 programming paradigms with full rule tables); updated Section 3a (goal field now free text); updated Section 5a (plan.md template adds Paradigm field); updated Section 13 (two new design decisions) |

**What did NOT change:**
All tool functions (memory.py, rag.py, database.py), all agent definitions
(supervisor.py, subagents.py), all API routes, all environment variables,
Qdrant setup, MongoDB setup, progress tracking. The paradigm layer is a
prompt-only change plus a new written field in the plan.md file — zero
code changes required.

**How to verify the fix works:**
1. Run /plan with goal="I want to get stronger" and days_per_week=5
2. Open sessions/{session_id}/plan.md — confirm "Paradigm: strength" appears
   in the User Profile section (written by Supervisor step 0)
3. Confirm DAY MAP shows heavy/volume/speed zones (not hard/medium/soft)
4. Confirm DAY MAP max_sets is 12-15 range (not 22) for 90-min sessions
5. Confirm primary movement is named explicitly in each day's DAY MAP entry
6. Run /plan with goal="I want to run a marathon and complement my training"
7. Confirm "Paradigm: endurance_complement" appears in plan header
8. Confirm leg volume is capped and cardio load is noted in plan header
9. Run /plan with goal="xyzabc123" (nonsense goal)
10. Confirm "Paradigm: general_fitness" with the original goal text logged —
    pipeline completes without error
