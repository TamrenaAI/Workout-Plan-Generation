"""
GET /progress/scans — the current user's InBody scan history, most recent
first. Backs the mobile app's Progress tab timeline.

GET /progress/comparison — latest scan vs. the one before it, with deltas.
Returns {"comparison": null} until the user has at least 2 scans (i.e.
their second InBody re-scan) — there's nothing to compare against on a
single scan.
"""

from fastapi import APIRouter, Depends

from auth.dependencies import get_current_user
from pipeline.inbody_history import compare_latest_two, list_scans_for_user

router = APIRouter()


@router.get("/progress/scans")
async def get_scan_history(user: dict = Depends(get_current_user)):
    return {"scans": list_scans_for_user(user["id"])}


@router.get("/progress/comparison")
async def get_latest_comparison(user: dict = Depends(get_current_user)):
    return {"comparison": compare_latest_two(user["id"])}
