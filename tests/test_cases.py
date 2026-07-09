# =============================================================================
# Tamrena AI — Multi-Agent System Test Cases
# =============================================================================
# Purpose: Verify agent collaboration, RAG trigger accuracy, and plan structure
#          across diverse user profiles.
#
# RAG Triggers to validate (from architecture):
#   [T1] Injury / Active Pain Flag
#   [T2] Muscle Imbalance Detected
#   [T3] Plateau Detected
#   [T4] Conflicting Contraindications
#   [T5] Extreme or Atypical InBody Values
#   [T6] Special Population Flags
#   [T7] Multi-Flag Combination
#
# Each case documents:
#   - What the agent should produce
#   - Which RAG triggers should fire
#   - What specific collaboration points to validate
# =============================================================================


# ──────────────────────────────────────────────
# CASE 01 — BASELINE (your original, clean path)
# Expected RAG triggers: NONE
# Tests: Happy path — no edge cases, clean collaboration
# ──────────────────────────────────────────────
CASE_01_INTAKE = """USER INTAKE FORM
─────────────────────────────────────
Goal             : hypertrophy
Days per week    : 4
Experience       : intermediate
Session duration : 75min
Injuries/limits  : none
Priority focus   : bigger arms, lagging back
Age              : 27
Sleep quality    : average
Job type         : desk"""

CASE_01_INBODY = """
InBody 570 Result Sheet
Name: Ahmed Al-Rashidi   Age: 27   Gender: Male

Body Composition Analysis
  Weight: 84.3 kg
  Skeletal Muscle Mass: 38.2 kg
  Body Fat Mass: 18.6 kg
  Body Fat %: 22.1%
  BMR: 1910 kcal

Segmental Lean Analysis (kg)
  Right Arm: 3.82   Left Arm: 3.41
  Right Leg: 10.95  Left Leg: 11.02
  Trunk: 28.7
"""

CASE_01_META = {
    "id": "case_01_baseline",
    "description": "Clean intermediate hypertrophy — no triggers, validates happy path",
    "expected_rag_triggers": [],
    "validate": [
        "4-day split is structured correctly (e.g. Upper/Lower or Push/Pull/Legs variant)",
        "Arm + back volume is elevated above MEV due to priority flags",
        "Load prescription uses SMM (38.2kg) and BF% (22.1%) correctly",
        "No RAG call is made — all handled by structured DB",
    ]
}


# ──────────────────────────────────────────────
# CASE 02 — BEGINNER FEMALE, FAT LOSS
# Expected RAG triggers: NONE (clean beginner path)
# Tests: Goal ≠ hypertrophy; female; beginner volume/intensity logic;
#        low session count (3 days); fat-loss split structure
# ──────────────────────────────────────────────
CASE_02_INTAKE = """USER INTAKE FORM
─────────────────────────────────────
Goal             : fat loss
Days per week    : 3
Experience       : beginner
Session duration : 50min
Injuries/limits  : none
Priority focus   : full body toning
Age              : 24
Sleep quality    : good
Job type         : active (nurse)"""

CASE_02_INBODY = """
InBody 570 Result Sheet
Name: Sara Hassan   Age: 24   Gender: Female

Body Composition Analysis
  Weight: 68.4 kg
  Skeletal Muscle Mass: 22.1 kg
  Body Fat Mass: 21.8 kg
  Body Fat %: 31.9%
  BMR: 1410 kcal

Segmental Lean Analysis (kg)
  Right Arm: 2.12   Left Arm: 2.08
  Right Leg: 7.84   Left Leg: 7.91
  Trunk: 18.6
"""

CASE_02_META = {
    "id": "case_02_beginner_female_fatloss",
    "description": "Beginner female, fat loss, 3 days — validates goal-specific split and beginner volume caps",
    "expected_rag_triggers": [],
    "validate": [
        "3-day full-body split is chosen (not PPL or Upper/Lower)",
        "Volume stays at or near MEV — beginner does not need MAV",
        "Intensity kept in 60–70% 1RM range (hypertrophy-fat loss overlap)",
        "Active job (nurse) is factored into recovery — volume is not inflated",
        "BMR (1410) is passed correctly to nutrition agent for caloric deficit calc",
    ]
}


# ──────────────────────────────────────────────
# CASE 03 — ADVANCED STRENGTH / POWERLIFTING
# Expected RAG triggers: NONE on clean run; [T3] if plateau logic fires
# Tests: Strength goal changes exercise selection (compounds first);
#        5-day frequency; high SMM drives heavier loading
# ──────────────────────────────────────────────
CASE_03_INTAKE = """USER INTAKE FORM
─────────────────────────────────────
Goal             : strength
Days per week    : 5
Experience       : advanced
Session duration : 90min
Injuries/limits  : none
Priority focus   : squat, bench, deadlift numbers
Age              : 31
Sleep quality    : good
Job type         : manual labor"""

CASE_03_INBODY = """
InBody 570 Result Sheet
Name: Karim Mansour   Age: 31   Gender: Male

Body Composition Analysis
  Weight: 97.6 kg
  Skeletal Muscle Mass: 46.4 kg
  Body Fat Mass: 18.9 kg
  Body Fat %: 19.4%
  BMR: 2190 kcal

Segmental Lean Analysis (kg)
  Right Arm: 4.81   Left Arm: 4.74
  Right Leg: 12.60  Left Leg: 12.44
  Trunk: 33.1
"""

CASE_03_META = {
    "id": "case_03_advanced_strength",
    "description": "Advanced powerlifter, 5 days — validates strength periodization, compound-first logic",
    "expected_rag_triggers": [],
    "validate": [
        "Split prioritizes Big 3 — squat/bench/deadlift appear in primary slots",
        "Rep ranges shift to 1–6 (strength), not 8–12 (hypertrophy)",
        "Advanced trainees get more frequent plan restructuring cadence flagged",
        "Manual labor job reduces accessory volume (higher external fatigue)",
        "High SMM (46.4kg) drives load prescription into heavier absolute weights",
    ]
}


# ──────────────────────────────────────────────
# CASE 04 — MULTIPLE ACTIVE INJURIES
# Expected RAG triggers: [T1] + [T4] + possibly [T7]
# Tests: Two simultaneous contraindications that may conflict;
#        shoulder impingement vs knee meniscus — different muscle groups
#        but compound movements (squats, overhead press) intersect both
# ──────────────────────────────────────────────
CASE_04_INTAKE = """USER INTAKE FORM
─────────────────────────────────────
Goal             : hypertrophy
Days per week    : 4
Experience       : intermediate
Session duration : 60min
Injuries/limits  : left shoulder impingement, right knee meniscus tear (partial, non-surgical)
Priority focus   : chest, legs
Age              : 34
Sleep quality    : poor
Job type         : desk"""

CASE_04_INBODY = """
InBody 570 Result Sheet
Name: Youssef Nabil   Age: 34   Gender: Male

Body Composition Analysis
  Weight: 81.2 kg
  Skeletal Muscle Mass: 36.5 kg
  Body Fat Mass: 17.1 kg
  Body Fat %: 21.1%
  BMR: 1870 kcal

Segmental Lean Analysis (kg)
  Right Arm: 3.64   Left Arm: 3.20
  Right Leg: 10.82  Left Leg: 10.11
  Trunk: 27.4
"""

CASE_04_META = {
    "id": "case_04_multi_injury",
    "description": "Two simultaneous injuries (shoulder + knee) that create conflicting exercise constraints",
    "expected_rag_triggers": ["T1_injury_pain_flag", "T4_conflicting_contraindications"],
    "validate": [
        "Shoulder impingement correctly blocks: overhead press, upright rows, behind-neck pull-downs",
        "Knee meniscus correctly blocks: deep squats, leg press (full ROM), lunges",
        "Chest exercises use flat/incline DB (not barbell overhead) to protect shoulder",
        "Leg exercises route to leg curls, hip hinges, step-ups — no deep knee flexion",
        "RAG is queried for overlap: exercises that stress BOTH shoulder + knee are excluded",
        "Poor sleep reduces total volume budget — recovery note generated",
        "Left arm lean deficiency (3.20 vs 3.64) is noted but not classified as imbalance trigger",
    ]
}


# ──────────────────────────────────────────────
# CASE 05 — SEVERE SEGMENTAL IMBALANCE
# Expected RAG triggers: [T2] Muscle Imbalance Detected
# Tests: Significant arm asymmetry (right arm 59% heavier than left arm)
#        and meaningful leg asymmetry — system must unilateralize programming
# ──────────────────────────────────────────────
CASE_05_INTAKE = """USER INTAKE FORM
─────────────────────────────────────
Goal             : hypertrophy
Days per week    : 4
Experience       : intermediate
Session duration : 70min
Injuries/limits  : left arm had fracture 18 months ago (fully healed)
Priority focus   : balanced physique, arms
Age              : 29
Sleep quality    : good
Job type         : desk"""

CASE_05_INBODY = """
InBody 570 Result Sheet
Name: Omar Farouk   Age: 29   Gender: Male

Body Composition Analysis
  Weight: 76.1 kg
  Skeletal Muscle Mass: 34.8 kg
  Body Fat Mass: 13.0 kg
  Body Fat %: 17.1%
  BMR: 1810 kcal

Segmental Lean Analysis (kg)
  Right Arm: 4.21   Left Arm: 2.63
  Right Leg: 10.74  Left Leg: 9.18
  Trunk: 26.8
"""

CASE_05_META = {
    "id": "case_05_severe_imbalance",
    "description": "Severe arm asymmetry (1.58kg gap) + notable leg asymmetry — RAG must fire for imbalance",
    "expected_rag_triggers": ["T2_muscle_imbalance_detected"],
    "validate": [
        "Arm imbalance (1.58kg gap, 60% discrepancy) triggers T2",
        "Leg imbalance (1.56kg gap) also contributes to T2 flag",
        "Unilateral exercises prioritized: DB curls before barbell, single-leg work",
        "Weaker side leads all unilateral sets (left arm/leg starts first)",
        "RAG retrieves literature on imbalance correction protocols",
        "History of fracture passed to contraindication layer (even if healed)",
        "Volume on weak limb is equal or slightly higher (corrective bias)",
    ]
}


# ──────────────────────────────────────────────
# CASE 06 — OBESE BEGINNER, HIGH BF%
# Expected RAG triggers: [T5] Extreme InBody Values + [T6] Special Population
# Tests: 41.3% BF is above standard InBody healthy range;
#        high body weight stresses joints — system must reduce impact;
#        beginner + obese combination is a special population
# ──────────────────────────────────────────────
CASE_06_INTAKE = """USER INTAKE FORM
─────────────────────────────────────
Goal             : fat loss
Days per week    : 3
Experience       : beginner
Session duration : 45min
Injuries/limits  : knee discomfort during stairs (not diagnosed)
Priority focus   : losing weight, building basic fitness
Age              : 38
Sleep quality    : poor
Job type         : desk"""

CASE_06_INBODY = """
InBody 570 Result Sheet
Name: Tarek Ibrahim   Age: 38   Gender: Male

Body Composition Analysis
  Weight: 117.8 kg
  Skeletal Muscle Mass: 31.4 kg
  Body Fat Mass: 48.6 kg
  Body Fat %: 41.3%
  BMR: 2290 kcal

Segmental Lean Analysis (kg)
  Right Arm: 3.41   Left Arm: 3.36
  Right Leg: 11.08  Left Leg: 10.94
  Trunk: 24.9
"""

CASE_06_META = {
    "id": "case_06_obese_beginner",
    "description": "High BF% (41.3%) + high body weight + beginner — extreme InBody + special population flags",
    "expected_rag_triggers": ["T5_extreme_inbody_values", "T6_special_population_flag"],
    "validate": [
        "BF% (41.3%) exceeds typical thresholds — T5 fires",
        "High body weight (117.8kg) + knee discomfort — impact exercises excluded",
        "No running, box jumps, or jump squats — replaced with low-impact cardio",
        "Beginner + obese classified as T6 special population",
        "RAG queries literature on exercise prescription for obese beginners",
        "Volume is ultra-conservative (below standard MEV) to preserve adherence",
        "Poor sleep + obesity combination noted in recovery notes",
        "BMR (2290) is high due to mass — nutrition agent gets accurate baseline",
    ]
}


# ──────────────────────────────────────────────
# CASE 07 — VERY LEAN ATHLETE, MUSCLE BUILDING
# Expected RAG triggers: [T5] Extreme InBody Values (low BF%)
# Tests: 6.8% BF is clinically low for a non-competition context;
#        system must flag this and adjust nutrition agent coordination
# ──────────────────────────────────────────────
CASE_07_INTAKE = """USER INTAKE FORM
─────────────────────────────────────
Goal             : muscle building
Days per week    : 6
Experience       : advanced
Session duration : 80min
Injuries/limits  : none
Priority focus   : upper body mass, chest thickness
Age              : 26
Sleep quality    : good
Job type         : athlete / personal trainer"""

CASE_07_INBODY = """
InBody 570 Result Sheet
Name: Hamza Younis   Age: 26   Gender: Male

Body Composition Analysis
  Weight: 74.2 kg
  Skeletal Muscle Mass: 40.3 kg
  Body Fat Mass: 5.1 kg
  Body Fat %: 6.8%
  BMR: 1990 kcal

Segmental Lean Analysis (kg)
  Right Arm: 4.38   Left Arm: 4.31
  Right Leg: 10.62  Left Leg: 10.58
  Trunk: 29.2
"""

CASE_07_META = {
    "id": "case_07_very_lean_advanced",
    "description": "Very low BF% (6.8%) athlete — T5 fires, nutrition agent coordination critical",
    "expected_rag_triggers": ["T5_extreme_inbody_values"],
    "validate": [
        "BF% (6.8%) below essential fat threshold — T5 fires",
        "RAG retrieves literature on programming for very lean athletes",
        "Nutrition agent is explicitly flagged: aggressive bulk recommended",
        "6-day advanced split is structured (PPL x2 or similar)",
        "Volume is at MAV/MRV boundary — advanced athlete justification",
        "Recovery emphasis increased (note: 6 days + advanced + low BF = high risk)",
        "High SMM (40.3kg) / body weight ratio noted as positive indicator",
    ]
}


# ──────────────────────────────────────────────
# CASE 08 — OLDER ADULT, JOINT LIMITATIONS
# Expected RAG triggers: [T1] + [T6] Special Population (age > 50)
# Tests: 52-year-old with arthritis and lumbar issues — classic special population;
#        system must modify exercise selection AND intensity prescription
# ──────────────────────────────────────────────
CASE_08_INTAKE = """USER INTAKE FORM
─────────────────────────────────────
Goal             : muscle maintenance / anti-aging
Days per week    : 3
Experience       : intermediate
Session duration : 55min
Injuries/limits  : osteoarthritis both knees, chronic lower back tightness (L4-L5)
Priority focus   : maintaining muscle mass, mobility
Age              : 52
Sleep quality    : average
Job type         : desk"""

CASE_08_INBODY = """
InBody 570 Result Sheet
Name: Walid Osman   Age: 52   Gender: Male

Body Composition Analysis
  Weight: 88.4 kg
  Skeletal Muscle Mass: 33.2 kg
  Body Fat Mass: 24.0 kg
  Body Fat %: 27.2%
  BMR: 1830 kcal

Segmental Lean Analysis (kg)
  Right Arm: 3.48   Left Arm: 3.44
  Right Leg: 10.22  Left Leg: 10.08
  Trunk: 26.8
"""

CASE_08_META = {
    "id": "case_08_older_adult_joints",
    "description": "52yr old with bilateral knee arthritis + L4-L5 — T1 + T6 (special population)",
    "expected_rag_triggers": ["T1_injury_pain_flag", "T6_special_population_flag"],
    "validate": [
        "Age 52 triggers T6 special population flag",
        "Bilateral knee arthritis + L4-L5 triggers T1",
        "No deep squats, no conventional deadlifts, no high-impact",
        "Romanian deadlifts, trap bar deadlifts (if available) preferred over conventional",
        "Leg press excluded or ROM limited — leg curl, hip thrust alternatives",
        "Rep ranges shift to 10–20 (lighter load, joint-friendly stimulus)",
        "RAG retrieves age-specific training literature (older adult resistance training)",
        "Low SMM (33.2kg) for intermediate at 52 — sarcopenia risk noted",
        "Mobility work is included as part of session structure",
    ]
}


# ──────────────────────────────────────────────
# CASE 09 — TIME-COMPRESSED INTERMEDIATE
# Tests: 5 days/week but only 40min — volume MUST be compressed;
#        dense session design; superset/giant set pairing likely needed
# Expected RAG triggers: NONE (no clinical edge case)
# ──────────────────────────────────────────────
CASE_09_INTAKE = """USER INTAKE FORM
─────────────────────────────────────
Goal             : hypertrophy
Days per week    : 5
Experience       : intermediate
Session duration : 40min
Injuries/limits  : none
Priority focus   : chest, shoulders
Age              : 30
Sleep quality    : average
Job type         : entrepreneur (high stress)"""

CASE_09_INBODY = """
InBody 570 Result Sheet
Name: Faris Al-Amin   Age: 30   Gender: Male

Body Composition Analysis
  Weight: 79.8 kg
  Skeletal Muscle Mass: 35.6 kg
  Body Fat Mass: 16.0 kg
  Body Fat %: 20.1%
  BMR: 1845 kcal

Segmental Lean Analysis (kg)
  Right Arm: 3.70   Left Arm: 3.65
  Right Leg: 10.40  Left Leg: 10.28
  Trunk: 27.3
"""

CASE_09_META = {
    "id": "case_09_time_compressed",
    "description": "5 days x 40min — volume compression logic, dense session design",
    "expected_rag_triggers": [],
    "validate": [
        "5 days x 40min budget respected — no session exceeds ~10–12 sets total",
        "Supersets are proposed for time efficiency (antagonist pairing)",
        "High-stress job (entrepreneur) reduces volume budget — recovery is compromised",
        "Chest + shoulder priority maintained within compressed structure",
        "Rest periods are shortened (60–90s) vs standard (2–3min) to fit time",
        "Agent does NOT simply cut exercises — it restructures session density",
    ]
}


# ──────────────────────────────────────────────
# CASE 10 — MINIMAL HOME EQUIPMENT
# Tests: Exercise filter fallbacks — no barbells, no cables, no machines;
#        equipment: resistance bands + adjustable DBs (up to 25kg) + pull-up bar
# Expected RAG triggers: NONE
# ──────────────────────────────────────────────
CASE_10_INTAKE = """USER INTAKE FORM
─────────────────────────────────────
Goal             : hypertrophy
Days per week    : 4
Experience       : intermediate
Session duration : 60min
Injuries/limits  : none
Priority focus   : back thickness, biceps
Age              : 28
Sleep quality    : good
Job type         : remote / work from home
Equipment        : adjustable dumbbells (up to 25kg), pull-up bar, resistance bands (light/medium/heavy), bench"""

CASE_10_INBODY = """
InBody 570 Result Sheet
Name: Bilal Mostafa   Age: 28   Gender: Male

Body Composition Analysis
  Weight: 77.2 kg
  Skeletal Muscle Mass: 36.1 kg
  Body Fat Mass: 13.9 kg
  Body Fat %: 18.0%
  BMR: 1815 kcal

Segmental Lean Analysis (kg)
  Right Arm: 3.74   Left Arm: 3.68
  Right Leg: 10.34  Left Leg: 10.22
  Trunk: 26.8
"""

CASE_10_META = {
    "id": "case_10_home_gym_minimal",
    "description": "Home gym with limited equipment — tests exercise filter fallback chain",
    "expected_rag_triggers": [],
    "validate": [
        "Exercise filter correctly excludes all barbell and cable machine exercises",
        "Back thickness: DB rows, chest-supported DB rows, resistance band pull-aparts",
        "Vertical pull: pull-up variations (weighted if needed), band-assisted",
        "No fallback to empty candidate set — system finds valid alternatives",
        "DB weight cap (25kg) is respected in load prescription",
        "Agent notes that cable crossovers / lat pulldowns unavailable — substitutes logged",
        "Plan structure agent adapts split to available equipment constraints",
    ]
}


# ──────────────────────────────────────────────
# CASE 11 — MULTI-FLAG COMBINATION (hardest case)
# Expected RAG triggers: [T7] Multi-Flag Combination
#   Flags active: T1 (injury) + T2 (imbalance) + T3 (plateau) + T5 (low BF)
# Tests: Most complex RAG trigger — multiple flags stack simultaneously;
#        agent must coordinate across all constraints without contradictions
# ──────────────────────────────────────────────
CASE_11_INTAKE = """USER INTAKE FORM
─────────────────────────────────────
Goal             : hypertrophy
Days per week    : 5
Experience       : advanced
Session duration : 85min
Injuries/limits  : right rotator cuff (post-surgery 8 months ago, cleared for training), chronic wrist pain right side
Priority focus   : back to full capacity, overall mass
Plateau note     : same program for 14 months, no size gains in last 4
Age              : 33
Sleep quality    : average
Job type         : desk"""

CASE_11_INBODY = """
InBody 570 Result Sheet
Name: Nour El-Din   Age: 33   Gender: Male

Body Composition Analysis
  Weight: 80.5 kg
  Skeletal Muscle Mass: 41.2 kg
  Body Fat Mass: 5.8 kg
  Body Fat %: 7.2%
  BMR: 2010 kcal

Segmental Lean Analysis (kg)
  Right Arm: 3.92   Left Arm: 4.49
  Right Leg: 10.88  Left Leg: 10.74
  Trunk: 30.2
"""

CASE_11_META = {
    "id": "case_11_multi_flag_combo",
    "description": "4 simultaneous RAG flags: injury (T1) + imbalance (T2) + plateau (T3) + extreme BF (T5) → T7",
    "expected_rag_triggers": [
        "T1_injury_pain_flag",
        "T2_muscle_imbalance_detected",
        "T3_plateau_detected",
        "T5_extreme_inbody_values",
        "T7_multi_flag_combination",  # Overarching trigger
    ],
    "validate": [
        # T1: Rotator cuff + wrist pain
        "Rotator cuff: overhead pressing excluded or heavily modified (landmine press instead)",
        "Wrist pain: barbell curl → DB hammer curl / cable curl; no barbell for pressing",
        # T2: Arm imbalance — left arm LARGER (unusual — right arm weaker post-surgery)
        "Imbalance is injury-origin (right arm smaller post-surgery): T2 fires",
        "Corrective approach: right arm unilateral work with lighter loads, higher reps",
        # T3: Plateau after 14 months same program
        "Plateau: RAG retrieves literature on plateau breaking (deload, method variation)",
        "Program restructure is strongly flagged — agent suggests periodization change",
        # T5: BF% 7.2% is extreme/atypical
        "Extreme low BF: nutrition agent coordination flagged urgently",
        # T7: Multi-flag handling
        "T7 fires: RAG context merges all flags into single coherent query",
        "No constraint contradiction is introduced across all simultaneous flags",
        "Agent output includes a reasoning summary of all active flags and how resolved",
    ]
}


# ──────────────────────────────────────────────
# CASE 12 — RECOMPOSITION GOAL (fat loss + muscle gain)
# Expected RAG triggers: NONE (unless InBody triggers T5)
# Tests: Recomp is a unique goal state — nutrition agent coordination is critical;
#        caloric target is maintenance not surplus/deficit; volume moderate
# ──────────────────────────────────────────────
CASE_12_INTAKE = """USER INTAKE FORM
─────────────────────────────────────
Goal             : body recomposition
Days per week    : 4
Experience       : beginner-intermediate (1.5 years consistent)
Session duration : 65min
Injuries/limits  : none
Priority focus   : lose belly fat while gaining muscle
Age              : 25
Sleep quality    : average
Job type         : student (sedentary)"""

CASE_12_INBODY = """
InBody 570 Result Sheet
Name: Dina Khalil   Age: 25   Gender: Female

Body Composition Analysis
  Weight: 62.8 kg
  Skeletal Muscle Mass: 23.4 kg
  Body Fat Mass: 17.6 kg
  Body Fat %: 28.1%
  BMR: 1340 kcal

Segmental Lean Analysis (kg)
  Right Arm: 2.21   Left Arm: 2.18
  Right Leg: 7.96   Left Leg: 7.88
  Trunk: 19.8
"""

CASE_12_META = {
    "id": "case_12_recomposition_female",
    "description": "Recomp goal (unique nutrition/training crossover) — validates agent coordination on dual objective",
    "expected_rag_triggers": [],
    "validate": [
        "Recomp goal triggers maintenance-calorie target (not surplus/deficit) in nutrition agent",
        "Both agents share the goal state — workout agent increases intensity, nutrition agent holds maintenance",
        "Volume is moderate (between MEV and MAV) — neither bulk nor cut programming",
        "Beginner-intermediate classification uses the 1.5yr consistency signal correctly",
        "BMR (1340 kcal) is correctly used as baseline — low BMR requires careful nutrition coordination",
        "Female classification is passed through correctly — no male-default logic",
        "4-day split is appropriate for recomp goal (enough frequency, enough recovery)",
    ]
}


# ──────────────────────────────────────────────
# CASE 13 — ENDURANCE ATHLETE ADDING STRENGTH
# Expected RAG triggers: [T4] Conflicting Contraindications (endurance vs strength adaptation)
# Tests: Goal is strength/muscle but background is endurance — concurrent training conflict;
#        high aerobic load is a hidden variable the agents must factor into recovery
# ──────────────────────────────────────────────
CASE_13_INTAKE = """USER INTAKE FORM
─────────────────────────────────────
Goal             : strength / muscle building
Days per week    : 3 (lifting only — also runs 40km/week)
Experience       : beginner (to lifting)
Session duration : 60min
Injuries/limits  : tight hip flexors, mild shin splints (from running)
Priority focus   : legs, overall strength for better running economy
Age              : 29
Sleep quality    : average
Job type         : teacher"""

CASE_13_INBODY = """
InBody 570 Result Sheet
Name: Leila Samir   Age: 29   Gender: Female

Body Composition Analysis
  Weight: 57.4 kg
  Skeletal Muscle Mass: 24.8 kg
  Body Fat Mass: 9.8 kg
  Body Fat %: 17.1%
  BMR: 1380 kcal

Segmental Lean Analysis (kg)
  Right Arm: 2.04   Left Arm: 2.01
  Right Leg: 8.12   Left Leg: 8.06
  Trunk: 20.1
"""

CASE_13_META = {
    "id": "case_13_endurance_plus_strength",
    "description": "Concurrent training scenario — running + lifting, agents must account for total fatigue",
    "expected_rag_triggers": ["T4_conflicting_contraindications"],
    "validate": [
        "40km/week running is factored into total fatigue budget",
        "T4 fires: concurrent training creates interference effect (endurance vs strength adaptation)",
        "RAG retrieves concurrent training literature (interference effect mitigation)",
        "Lifting sessions placed maximally far from hard run days",
        "Leg volume is conservative — legs already loaded by running",
        "Hip flexor tightness excludes deep hip flexion under load (lunges, front squats)",
        "Shin splints prevent jump training / plyometrics",
        "BF% (17.1%) for endurance athlete is healthy — no T5 trigger",
        "Nutrition: BMR + running caloric cost must both be communicated to nutrition agent",
    ]
}


# =============================================================================
# QUICK REFERENCE — Which cases test which triggers
# =============================================================================
RAG_TRIGGER_COVERAGE = {
    "T1_injury_pain_flag":              ["case_04", "case_08", "case_11", "case_13"],
    "T2_muscle_imbalance_detected":     ["case_05", "case_11"],
    "T3_plateau_detected":              ["case_11"],
    "T4_conflicting_contraindications": ["case_04", "case_13"],
    "T5_extreme_inbody_values":         ["case_06", "case_07", "case_11"],
    "T6_special_population_flag":       ["case_06", "case_08"],
    "T7_multi_flag_combination":        ["case_11"],
    "no_trigger_clean_path":            ["case_01", "case_02", "case_03", "case_09", "case_10", "case_12"],
}

# =============================================================================
# QUICK REFERENCE — What dimension each case stresses
# =============================================================================
DIMENSION_COVERAGE = {
    "goal_hypertrophy":       ["case_01", "case_04", "case_05", "case_09", "case_10", "case_11"],
    "goal_fat_loss":          ["case_02", "case_06"],
    "goal_strength":          ["case_03"],
    "goal_recomposition":     ["case_12"],
    "goal_muscle_building":   ["case_07"],
    "goal_maintenance":       ["case_08"],
    "goal_concurrent":        ["case_13"],
    "experience_beginner":    ["case_02", "case_06", "case_13"],
    "experience_intermediate":["case_01", "case_04", "case_05", "case_08", "case_09", "case_10", "case_12"],
    "experience_advanced":    ["case_03", "case_07", "case_11"],
    "female_user":            ["case_02", "case_12", "case_13"],
    "limited_equipment":      ["case_10"],
    "time_constrained":       ["case_09"],
    "older_adult":            ["case_08"],
    "high_bf_pct":            ["case_06"],
    "low_bf_pct":             ["case_07", "case_11"],
    "severe_imbalance":       ["case_05", "case_11"],
    "multi_injury":           ["case_04", "case_11"],
}
