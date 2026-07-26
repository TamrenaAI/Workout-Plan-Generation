"""
CLI runner for the Tamreena agent pipeline — the production replacement for
manually running the per-case cells in notebooks/Agent_exploration.ipynb
(Part 8, cells 17-29).

Usage:
    python scripts/run_pipeline.py --list
    python scripts/run_pipeline.py --case 1
    python scripts/run_pipeline.py --case 11
"""

import argparse
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Force UTF-8 output encoding for Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.exercise_recommender import EXERCISE_RECOMMENDER
from agents.plan_assembler import PLAN_ASSEMBLER
from agents.supervisor import build_supervisor
from tests import test_cases as tc

CASE_NUMBERS = range(1, 14)


def _case_data(n: int):
    tag = f"CASE_{n:02d}"
    intake = getattr(tc, f"{tag}_INTAKE")
    inbody = getattr(tc, f"{tag}_INBODY")
    meta = getattr(tc, f"{tag}_META")
    return intake, inbody, meta


def list_cases():
    for n in CASE_NUMBERS:
        try:
            _, _, meta = _case_data(n)
        except AttributeError:
            continue
        print(f"{n:>2}. {meta['id']:<35} {meta['description']}")


def run_case(n: int) -> str:
    intake, inbody, meta = _case_data(n)

    session_id = str(uuid.uuid4())
    print(f"Session ({meta['id']}): {session_id}")

    supervisor = build_supervisor(sub_agents=[EXERCISE_RECOMMENDER, PLAN_ASSEMBLER])

    user_message = f"""SESSION_ID: {session_id}

{intake}

INBODY RAW TEXT:
{inbody}

Generate a full personalised workout plan for this user."""

    print(f"\nStarting pipeline at {datetime.now().strftime('%H:%M:%S')}...\n")

    result = supervisor.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        print_mode="updates",
    )
    final_plan = result["messages"][-1].content

    print("\n" + "=" * 60)
    print("FINAL PLAN OUTPUT")
    print("=" * 60)
    print(final_plan)
    print(f"\nSession file: sessions/{session_id}/plan.md")

    print("\n" + "-" * 60)
    print(f"Manual validation checklist -- {meta['id']}")
    print("-" * 60)
    for item in meta["validate"]:
        print(f"  [ ] {item}")

    return session_id


def main():
    parser = argparse.ArgumentParser(description="Run the Tamreena agent pipeline against a test case.")
    parser.add_argument("--case", type=int, help="Test case number (1-13)")
    parser.add_argument("--list", action="store_true", help="List available test cases")
    args = parser.parse_args()

    if args.list or not args.case:
        list_cases()
        return

    if args.case not in CASE_NUMBERS:
        print(f"Unknown case {args.case}. Use --list to see available cases.")
        sys.exit(1)

    run_case(args.case)


if __name__ == "__main__":
    main()
