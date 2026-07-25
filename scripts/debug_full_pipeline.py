"""
One-off debug runner (not a permanent script) — exercises the REAL end-to-end
path: InBody image bytes -> quality/authenticity checks -> VLM structured
extraction -> deterministic flags -> Supervisor + sub-agent plan generation
-> final schedule read back from plan memory. Prints each stage's result so
failures are attributable to a specific stage instead of a single opaque
traceback.

Usage:
    python scripts/debug_full_pipeline.py samples/inbody2.jfif
"""

import sys
import traceback
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.exercise_recommender import EXERCISE_RECOMMENDER
from agents.plan_assembler import PLAN_ASSEMBLER
from agents.supervisor import build_supervisor
from tools.inbody import format_inbody_result, load_scan, run_inbody_pipeline_from_bytes
from tools.memory import read_plan_memory


def main():
    image_path = sys.argv[1] if len(sys.argv) > 1 else "samples/inbody2.jfif"
    print(f"=== STAGE 1: load_scan({image_path}) ===")
    image_bytes, content_type = load_scan(image_path)
    print(f"OK — {len(image_bytes)} bytes, content_type={content_type}\n")

    print("=== STAGE 2: run_inbody_pipeline_from_bytes (quality -> authenticity -> VLM extraction -> flags) ===")
    try:
        result = run_inbody_pipeline_from_bytes(image_bytes, content_type)
    except Exception:
        print("FAILED — unhandled exception in the InBody pipeline:")
        traceback.print_exc()
        return

    if isinstance(result, dict):
        print(f"REJECTED at stage [{result['stage']}]: {result['error']}")
        return
    print("OK — extraction:")
    print(result.raw.model_dump_json(indent=2))
    print("\nFlags:")
    print(result.flags.model_dump_json(indent=2))

    inbody_text = format_inbody_result(result)
    print("\n=== STAGE 3: format_inbody_result ===")
    print(inbody_text)

    session_id = str(uuid.uuid4())
    print(f"\n=== STAGE 4: Supervisor pipeline (session_id={session_id}) ===")
    supervisor = build_supervisor(sub_agents=[EXERCISE_RECOMMENDER, PLAN_ASSEMBLER])

    user_message = f"""SESSION_ID: {session_id}

Goal: hypertrophy
Days per week: 4
Experience: intermediate
Session duration: 60min
Priority focus: none

INBODY RAW TEXT:
{inbody_text}

Generate a full personalised workout plan for this user."""

    try:
        result = supervisor.invoke(
            {"messages": [{"role": "user", "content": user_message}]},
            config={"recursion_limit": 150},
        )
    except Exception:
        print("FAILED — unhandled exception in the Supervisor pipeline:")
        traceback.print_exc()
        print(f"\nPartial plan memory (sessions/{session_id}/plan.md):")
        print(read_plan_memory.invoke({"session_id": session_id}))
        return

    print("OK — Supervisor finished. Final reply:")
    print(result["messages"][-1].content)

    print(f"\n=== STAGE 5: plan memory (sessions/{session_id}/plan.md) ===")
    print(read_plan_memory.invoke({"session_id": session_id}))

    print(f"\nDONE. session_id={session_id}")


if __name__ == "__main__":
    main()
