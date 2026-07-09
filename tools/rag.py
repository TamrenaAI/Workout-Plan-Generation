"""
RAG knowledge base — HARDCODED STUB.

This is a placeholder returning static training principles and muscle-specific
notes. It exists so the agent pipeline has something to reason over while the
RAG team builds the real Qdrant hybrid-search pipeline described in
tamrena_architecture_2.md Section 7 (bge-m3 dense + BM25 sparse + RRF fusion +
bge-reranker-v2-m3, all local, no API calls).

Swapping this out for the real pipeline should require no changes anywhere
else — `search_rag(muscle_group, query)` is the only contract other code
depends on.
"""

from langchain_core.tools import tool

# Principles that apply to every muscle group
_PRINCIPLES = """
[PRINCIPLE] Progressive overload is the primary driver of hypertrophy and strength. Increase load or reps weekly.
[PRINCIPLE] For hypertrophy, train each muscle group 10-20 sets/week across 2+ sessions for optimal frequency.
[PRINCIPLE] Rep ranges: strength 1-5, hypertrophy 6-15, endurance 15+. All ranges build muscle if taken near failure.
[PRINCIPLE] Rest periods: heavy compound 2-3 min, moderate 90s, isolation/corrective 60s.
[PRINCIPLE] RPE (Rate of Perceived Exertion) 8-9 = 1-2 reps in reserve. RPE 5-6 = comfortable, corrective work.
[PRINCIPLE] Elevated BF% (>18% male, >25% female): lean toward higher rep ranges (12-15) for better fat oxidation.
[PRINCIPLE] Asymmetry correction: always start unilateral sets on the weaker side. Never let the stronger side compensate.
[PRINCIPLE] Beginners: 10-12 sets/week per group. Intermediates: 14-18. Advanced: 18-22.
"""

# Muscle-specific notes (what the agent needs to make good exercise choices)
_MUSCLE_NOTES = {
    "chest": """
[CHEST] Chest has two primary functions: horizontal adduction (pressing) and shoulder flexion.
[CHEST] Compound first: flat or incline barbell/dumbbell press for maximum motor unit recruitment.
[CHEST] Incline angle (30-45°) shifts emphasis to clavicular head (upper chest) — prioritise for underdeveloped upper chest.
[CHEST] Cable flyes and pec deck provide constant tension through the stretched position — superior for hypertrophy isolation.
[CHEST] Dips (forward lean) are an effective compound chest movement when bars allow anterior tilt.
""",
    "back_vertical": """
[BACK-VERTICAL] Vertical pulling targets lats and teres major — responsible for the V-taper look.
[BACK-VERTICAL] Pull-ups and lat pulldowns are primary movements. Use full ROM — initiate with scapular depression.
[BACK-VERTICAL] Supinated grip (chin-up) increases bicep contribution and is easier for beginners.
[BACK-VERTICAL] Single-arm cable pulldown — best unilateral lat movement when arm asymmetry is flagged.
[BACK-VERTICAL] Straight-arm pulldown isolates lats without bicep contribution — good finisher.
""",
    "back_horizontal": """
[BACK-HORIZONTAL] Horizontal pulling targets mid/upper traps, rhomboids, and rear delts.
[BACK-HORIZONTAL] Barbell rows allow heaviest loading. Dumbbell rows allow greater ROM and unilateral correction.
[BACK-HORIZONTAL] Cable rows provide constant tension — use for hypertrophy finishers after heavy rows.
[BACK-HORIZONTAL] Chest-supported rows eliminate lower back fatigue — useful when lower back is a limiting factor.
[BACK-HORIZONTAL] Pronated grip rows emphasise rhomboids/traps. Neutral grip shifts more to lats.
""",
    "back": """
[BACK] Back training covers both vertical pulling (lats, teres major — V-taper) and horizontal
pulling (mid/upper traps, rhomboids). Balance both patterns across a back session.
[BACK] Pull-ups / lat pulldowns for vertical pulling; barbell or dumbbell rows for horizontal pulling.
[BACK] Single-arm cable pulldown or single-arm dumbbell row — best unilateral choice when arm asymmetry is flagged.
[BACK] Chest-supported rows eliminate lower back fatigue — useful when lower back is a limiting factor.
""",
    "shoulders": """
[SHOULDERS] Overhead press (barbell or dumbbell) is the primary compound movement for overall shoulder development.
[SHOULDERS] Lateral raises are essential for medial deltoid — cannot be replaced by pressing movements.
[SHOULDERS] Arnold press adds rotation through ROM — hits all three heads. More fatiguing than standard press.
[SHOULDERS] Cable lateral raises maintain tension at the top — superior to dumbbell for hypertrophy.
[SHOULDERS] Seated press reduces core demand and allows heavier loading with better stability.
""",
    "rear_delts": """
[REAR-DELTS] Rear delts are typically undertrained. They require dedicated isolation work.
[REAR-DELTS] Face pulls with external rotation hit rear delts + rotator cuff — important for shoulder health.
[REAR-DELTS] Reverse pec deck and bent-over lateral raises are primary isolation movements.
[REAR-DELTS] Rear delts respond well to higher rep ranges (15-20) and high frequency.
[REAR-DELTS] Include in pull day to avoid shoulder imbalance from pressing volume.
""",
    "triceps": """
[TRICEPS] Triceps make up ~2/3 of upper arm mass — prioritise over biceps for arm size.
[TRICEPS] Long head (largest) is best targeted with overhead extension — requires full shoulder flexion.
[TRICEPS] Pushdowns target lateral and medial head — useful finisher but not sufficient alone.
[TRICEPS] Close-grip bench press is the heaviest tricep compound movement.
[TRICEPS] Dips (upright torso) emphasise triceps over chest — effective mass builder.
""",
    "biceps": """
[BICEPS] Biceps function: elbow flexion + supination. Both must be trained for full development.
[BICEPS] Barbell curl allows maximum load — key strength movement.
[BICEPS] Incline dumbbell curl stretches the long head at the bottom — superior for peak development.
[BICEPS] Hammer curl targets brachialis and brachioradialis — adds thickness to the arm.
[BICEPS] Cable curls maintain tension through full ROM — excellent for hypertrophy finisher.
""",
    "arms": """
[ARMS] Arm training covers triceps (~2/3 of upper arm mass — prioritise for size) and biceps
(elbow flexion + supination — both must be trained).
[ARMS] Close-grip bench press / dips are the heaviest tricep compound movements.
[ARMS] Barbell curl allows maximum bicep load; incline dumbbell curl stretches the long head.
[ARMS] Single-arm cable curl or single-arm pushdown — unilateral choice when arm asymmetry is flagged.
""",
    "quads": """
[QUADS] Squats and leg press are primary compound movements. Squat depth matters — full depth maximises quad stretch.
[QUADS] Hack squat and leg press allow more knee-dominant pattern than back squat — better quad isolation.
[QUADS] Leg extension isolates quads without hip flexor contribution — critical for complete development.
[QUADS] Bulgarian split squat is the best unilateral quad movement — use when leg asymmetry is flagged.
[QUADS] Knee-over-toe training is safe and desirable for quad development when progressed correctly.
""",
    "hamstrings": """
[HAMSTRINGS] Hamstrings cross both hip and knee — require both hip hinge and knee flexion movements.
[HAMSTRINGS] Romanian deadlift (RDL) is the primary hip hinge — maximises hamstring length under load.
[HAMSTRINGS] Leg curl (lying or seated) is the primary knee flexion movement — do not skip it.
[HAMSTRINGS] Nordic hamstring curl builds extraordinary strength and injury resilience. Very high difficulty.
[HAMSTRINGS] Single-leg RDL is the unilateral choice when leg asymmetry is flagged.
""",
    "glutes": """
[GLUTES] Hip thrust is the most effective glute exercise — maximises glute activation at full hip extension.
[GLUTES] Romanian deadlift hits glutes and hamstrings together — good compound for posterior chain.
[GLUTES] Bulgarian split squat with forward lean shifts more load to glutes vs quads.
[GLUTES] Cable kickbacks and abductions isolate glute medius and minimus — needed for complete development.
[GLUTES] Glutes respond to both heavy loading (3-6 reps) and high rep ranges (15-20).
""",
    "calves": """
[CALVES] Calves have two muscles: gastrocnemius (knee extended) and soleus (knee bent).
[CALVES] Standing calf raise targets gastrocnemius. Seated calf raise targets soleus. Train both.
[CALVES] Calves require high volume (15-20 sets/week) and high reps (15-25) due to fibre type composition.
[CALVES] Full ROM critical — complete stretch at bottom, full plantarflexion at top.
[CALVES] Single-leg calf raises add unilateral correction when asymmetry is present.
""",
    "legs": """
[LEGS] Leg training covers quads (squat/leg-press patterns), hamstrings (hip hinge + knee flexion),
glutes (hip extension), and calves.
[LEGS] Squat-pattern exercises (back squat, leg press, hack squat) are quad-primary.
[LEGS] Hip-hinge exercises (Romanian deadlift, hip thrust) are hamstring/glute-primary.
[LEGS] Bulgarian split squat / single-leg RDL — best unilateral choices when leg asymmetry is flagged.
[LEGS] Leg extension and leg curl isolate quads and hamstrings independently when needed.
""",
    "core": """
[CORE] Core training targets stability (anti-rotation, anti-extension) and flexion/rotation strength.
[CORE] Plank and dead bug are anti-extension standards — build spine-safe stability.
[CORE] Cable woodchops and Pallof press target rotational stability.
[CORE] Hanging leg raises and ab wheel rollouts are advanced loaded movements.
[CORE] Core work placed at end of session — pre-fatiguing core impairs compound lifts.
""",
}


@tool
def search_rag(muscle_group: str, query: str) -> str:
    """
    Search the RAG knowledge base for training principles and muscle-specific guidance.
    Returns relevant evidence to inform exercise selection and prescription.
    NOTE: This is a hardcoded stub — RAG team will replace with real Qdrant hybrid search.
    """
    muscle_notes = _MUSCLE_NOTES.get(muscle_group, f"[No specific notes for {muscle_group}]")
    return f"=== PRINCIPLES ===\n{_PRINCIPLES}\n=== {muscle_group.upper()} SPECIFIC ===\n{muscle_notes}"
