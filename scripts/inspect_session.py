"""
Inspect a session's shared memory file + progress tracker — the production
replacement for manually running the inspection cells in
notebooks/Agent_exploration.ipynb (Part 8, cells 30-32).

Usage:
    python scripts/inspect_session.py <session_id>
    python scripts/inspect_session.py <session_id> --schedule-only
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import SESSION_DIR
from tools.memory import validate_plan_completeness, validate_session_duration


def main():
    parser = argparse.ArgumentParser(description="Inspect a Tamreena session's plan memory + progress.")
    parser.add_argument("session_id")
    parser.add_argument("--schedule-only", action="store_true", help="Only print the Weekly Schedule section")
    args = parser.parse_args()

    plan_path = Path(SESSION_DIR) / args.session_id / "plan.md"
    progress_path = Path(SESSION_DIR) / args.session_id / "progress.json"

    if args.schedule_only:
        if not plan_path.exists():
            print("Session file not found — pipeline may not have written to memory yet.")
            return
        content = plan_path.read_text(encoding="utf-8")
        marker = "## Weekly Schedule"
        if marker in content:
            print(content[content.index(marker):])
        else:
            print("No '## Weekly Schedule' section found yet — Plan Assembler may not have run.")
        return

    print("=" * 60)
    print("plan.md")
    print("=" * 60)
    if plan_path.exists():
        print(plan_path.read_text(encoding="utf-8"))
    else:
        print("Session file not found — pipeline may not have written to memory yet.")

    print("\n" + "=" * 60)
    print("progress.json")
    print("=" * 60)
    if progress_path.exists():
        print(json.dumps(json.loads(progress_path.read_text(encoding="utf-8")), indent=2))
    else:
        print("progress.json not found — init_plan_progress may not have been called.")

    print("\nvalidate_plan_completeness:")
    print(validate_plan_completeness.invoke({"session_id": args.session_id}))

    print("\nvalidate_session_duration:")
    print(validate_session_duration.invoke({"session_id": args.session_id}))


if __name__ == "__main__":
    main()
