"""
GET /progress/scans — the current user's InBody scan history, most recent
first. Backs the mobile app's Progress tab timeline.

GET /progress/comparison — latest scan vs. the one before it, with deltas.
Returns {"comparison": null} until the user has at least 2 scans (i.e.
their second InBody re-scan) — there's nothing to compare against on a
single scan.

GET /progress/{session_id}/report — the stored monthly-review report (see
pipeline/monthly_progress.py and agents/progress_analyst.py) for a session
that was created via POST /plan/{session_id}/monthly-review. session_id here
is the NEW session's id (the review's output), not the old one being
reviewed.
"""

from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import get_current_user
from auth.ownership import user_owns_session
from pipeline.inbody_history import compare_latest_two, list_scans_for_user
from pipeline.monthly_progress import get_progress_report

router = APIRouter()


@router.get("/progress/scans")
async def get_scan_history(user: dict = Depends(get_current_user)):
    return {"scans": list_scans_for_user(user["id"])}


@router.get("/progress/comparison")
async def get_latest_comparison(user: dict = Depends(get_current_user)):
    return {"comparison": compare_latest_two(user["id"])}


@router.get("/progress/{session_id}/report")
async def get_review_report(session_id: str, user: dict = Depends(get_current_user)):
    if not user_owns_session(session_id, user["id"]):
        raise HTTPException(404, "Unknown session_id.")
    report = get_progress_report(session_id)
    if report is None:
        raise HTTPException(404, "No progress report for this session.")
    return report
