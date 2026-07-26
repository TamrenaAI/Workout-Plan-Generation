"""
FastAPI Router for Longitudinal Monthly Progress Reports & InBody/CV Analytics
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel
from api.schemas.integration_schemas import MonthlyReportSummary
from services.monthly_report_aggregator import monthly_report_aggregator

router = APIRouter(prefix="/reports", tags=["reports"])


class MonthlyReportRequest(BaseModel):
    user_id: str
    current_smm_kg: float = 38.2
    baseline_smm_kg: float = 37.4
    current_bf_pct: float = 17.1
    baseline_bf_pct: float = 18.3


@router.post("/monthly", response_model=MonthlyReportSummary)
async def generate_monthly_report(request: MonthlyReportRequest):
    """Aggregates month-over-month InBody shifts with computer vision form quality logs to produce a longitudinal progress report."""
    try:
        report = monthly_report_aggregator.generate_monthly_report(
            user_id=request.user_id,
            current_smm_kg=request.current_smm_kg,
            baseline_smm_kg=request.baseline_smm_kg,
            current_bf_pct=request.current_bf_pct,
            baseline_bf_pct=request.baseline_bf_pct
        )
        return report
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate monthly progress report: {str(exc)}")


@router.get("/{report_id}", response_model=MonthlyReportSummary)
async def get_monthly_report(report_id: str):
    """Retrieves a generated monthly progress report by ID."""
    report = monthly_report_aggregator.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Monthly report {report_id} not found.")
    return report
