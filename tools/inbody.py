"""
InBody scan parsing — a tool, not an agent (see tamrena_architecture_2.md Section 4a).

Two entry points feed the rest of the pipeline the same text block format
("INBODY ANALYSIS ... FLAGS"):

1. Image/PDF scans (production path): `run_inbody_pipeline_from_bytes` runs
   quality check -> authenticity check -> structured VLM extraction ->
   deterministic flag computation (from Inbody_Agent.ipynb), then
   `format_inbody_result` converts the result into the same text block the
   Supervisor's prompt expects. Flags are computed in plain Python from the
   extracted numbers — never asked of the LLM — so there's no hallucination
   risk on the numbers that drive downstream programming decisions.

2. Raw text (dev/testing + the actual path the Supervisor calls today):
   `parse_inbody_text` is an agent tool that asks the LLM to read already-
   available InBody text and format it directly into the same block
   (from Agent_exploration.ipynb cell 6). All 13 cases in tests/test_cases.py
   exercise this path.

The image pipeline's webcam capture widget (InBodyCameraCapture in
Inbody_Agent.ipynb) is a notebook-only dev convenience and is intentionally
not ported here — the API takes an uploaded file, not a live camera feed.
"""

import base64
from pathlib import Path
from typing import Literal, Optional, Union

import cv2
import fitz  # pymupdf
import numpy as np
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from pydantic import BaseModel

from agents.llm import get_llm

_extraction_llm = get_llm(temperature=0)  # deterministic — extraction must not vary


# ── Pydantic models (from Inbody_Agent.ipynb) ────────────────────────────────

class SegmentalReading(BaseModel):
    value: float
    unit: Literal["kg", "lb"]
    percent_of_ideal: Optional[float] = None  # the % bar shown on the scan


class InBodyRawExtraction(BaseModel):
    # ── Identity ─────────────────────────────────────────────────────────
    inbody_model: Optional[str] = None          # "270S" / "570" / "770"
    gender: Literal["male", "female"]
    age: Optional[int] = None

    # ── Core composition ────────────────────────────────────────────────
    weight: float
    weight_unit: Literal["kg", "lb"]
    skeletal_muscle_mass: float
    smm_unit: Literal["kg", "lb"]
    body_fat_percent: float                     # PBF — always a plain % number
    bmr_kcal: Optional[int] = None               # not present on 270S

    # ── Segmental lean ───────────────────────────────────────────────────
    right_arm: SegmentalReading
    left_arm: SegmentalReading
    trunk: SegmentalReading
    right_leg: SegmentalReading
    left_leg: SegmentalReading

    # ── Higher-model only (570 / 770) ────────────────────────────────────
    ecw_ratio: Optional[float] = None
    visceral_fat_level: Optional[int] = None      # 570: level 1-20
    visceral_fat_area_cm2: Optional[float] = None  # 770: cm²
    smi: Optional[float] = None                   # Skeletal Muscle Index

    # ── Recovery indicators (present on select models) ──────────────────
    phase_angle: Optional[float] = None           # 270S + 770: cell health indicator
    waist_hip_ratio: Optional[float] = None        # 570 + 770: fat distribution pattern

    extraction_notes: Optional[str] = None         # anything the VLM couldn't read clearly


class InBodyFlags(BaseModel):
    arm_asymmetry: bool
    arm_diff_grams: float
    weaker_arm: Optional[Literal["left", "right"]] = None

    leg_asymmetry: bool
    leg_diff_grams: float
    weaker_leg: Optional[Literal["left", "right"]] = None

    elevated_bf: bool
    trunk_underdeveloped: bool


class InBodyResult(BaseModel):
    raw: InBodyRawExtraction
    flags: InBodyFlags


class InBodyValidation(BaseModel):
    is_inbody_scan: bool
    confidence: Literal["high", "medium", "low"]
    issue: Optional[str] = None


# ── Stage 1: image quality ────────────────────────────────────────────────

def check_image_quality(image_bytes: bytes) -> dict:
    """Checks blur and brightness from raw image bytes."""
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if img is None:
        return {"pass": False, "issue": "Could not decode image.", "blur_score": 0, "brightness": 0}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    brightness = float(gray.mean())

    if blur_score < 100:
        return {
            "pass": False,
            "issue": f"Image is too blurry (score: {blur_score:.1f}). Retake in better lighting or hold the camera steady.",
            "blur_score": blur_score,
            "brightness": brightness,
        }
    if brightness < 50:
        return {
            "pass": False,
            "issue": "Image is too dark. Move to a brighter area or turn on a light.",
            "blur_score": blur_score,
            "brightness": brightness,
        }
    dark_pixel_ratio = float((gray < 80).mean())
    if dark_pixel_ratio < 0.02:
        return {
            "pass": False,
            "issue": "Image is overexposed — no text is visible. Move away from direct light.",
            "blur_score": blur_score,
            "brightness": brightness,
        }

    return {"pass": True, "issue": None, "blur_score": blur_score, "brightness": brightness}


# ── File loading helpers ──────────────────────────────────────────────────

def pdf_to_image_bytes(pdf_bytes: bytes, zoom: float = 2.0) -> bytes:
    """Renders the first page of a PDF to PNG bytes."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    return pix.tobytes("png")


def load_scan(file_path: Union[str, Path]) -> tuple[bytes, str]:
    """Loads an InBody scan from a file path. Returns (image_bytes, content_type)."""
    path = Path(file_path)
    raw = path.read_bytes()

    if path.suffix.lower() == ".pdf":
        return pdf_to_image_bytes(raw), "image/png"

    ext_to_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
    content_type = ext_to_type.get(path.suffix.lower(), "image/jpeg")
    return raw, content_type


# ── Stage 2: authenticity check ───────────────────────────────────────────

VALIDATION_PROMPT = """You are checking whether an image is an InBody body composition result sheet.

Look for these identifiers:
- InBody logo in the top-left corner
- "Body Composition Analysis" section
- "Segmental Lean Analysis" section with arm/leg/trunk values
- Typical InBody layout with measurement bars or tables

Return your assessment. If it is NOT an InBody scan, describe what it appears to be instead."""


def validate_inbody_scan(image_bytes: bytes, content_type: str) -> InBodyValidation:
    """Lightweight LLM check — runs BEFORE the full extraction pipeline."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    validation_llm = _extraction_llm.with_structured_output(InBodyValidation)

    return validation_llm.invoke([
        SystemMessage(content=VALIDATION_PROMPT),
        HumanMessage(content=[
            {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{b64}"}},
            {"type": "text", "text": "Is this an InBody body composition result sheet?"},
        ]),
    ])


# ── Stage 3: structured extraction ────────────────────────────────────────

EXTRACTION_PROMPT = """You are an InBody scan data extractor.

Your ONLY job is to read values printed on the scan and return them in the exact schema.

Rules:
- NEVER calculate, derive, or infer values — only read what is explicitly printed
- If a field is not on this InBody model or you cannot read it clearly → return null
- ALWAYS extract the unit (kg or lb) alongside every measurement — do not assume
- If a value is partially obscured or ambiguous, set it to null and note it in extraction_notes
- Do not guess. A null is always better than a wrong number.

── body_fat_percent ────────────────────────────────────────────────────────────
This is the PBF (Percent Body Fat) value — a plain percentage number (e.g. 35.0, not 0.35).
It is found in the Obesity Analysis section, labeled "PBF" or "Percent Body Fat".
CRITICAL: Do NOT use BMI — BMI is a different field (kg/m²) and will always be wrong here.
CRITICAL: Do NOT use Body Fat Mass (the weight value in kg or lb) — that is a different field.
Example: Obesity Analysis shows "BMI: 22.1" and "PBF: 35.0" → extract 35.0, not 22.1.

── Segmental Lean Analysis values ──────────────────────────────────────────────
Read the number printed in text next to each segment label (Right Arm, Left Arm, Trunk,
Right Leg, Left Leg). Each segment has its weight value printed explicitly as a number with
a unit (kg or lb).
CRITICAL: Do NOT estimate values from bar length — the bars are visual only.
CRITICAL: Read each segment's value independently — never copy one segment's value to another.
The percent_of_ideal is the percentage number printed next to or below each segment's bar
(e.g. 139.0). Read it from the same row as the segment's weight value.

── bmr_kcal ────────────────────────────────────────────────────────────────────
Found in the "Research Parameters" section, labeled "Basal Metabolic Rate".
This section is often on the RIGHT side of the scan.
Present on 270S, 570, and 770 — check the Research Parameters section before returning null.

── Other field locations ────────────────────────────────────────────────────────
- inbody_model   → top of the scan in brackets, e.g. "[InBody270S]" → extract "270S"
- skeletal_muscle_mass / smm_unit → "Muscle-Fat Analysis" section, "SMM" row
- ecw_ratio      → "ECW Ratio" or "ECW/TBW" section (570/770 only)
- visceral_fat_level    → "Visceral Fat Level" scale 1–20 (570 only)
- visceral_fat_area_cm2 → "VFA" in cm² (770 only)
- smi            → "SMI" in Research Parameters, unit kg/m² (570/770 only)

── phase_angle ─────────────────────────────────────────────────────────────────
Found on 270S and 770, labeled "Whole Body Phase Angle" or "Phase Angle".
Extract the numeric value only (e.g. 7.5, not "7.5°").
Location: often in a small box in the top-right area or Research Parameters section.
If not visible or not on this model → return null.

── waist_hip_ratio ─────────────────────────────────────────────────────────────
Found on 570 and 770 in the Research Parameters section, labeled "Waist-Hip Ratio".
Extract the numeric value only (e.g. 0.83).
If not visible or not on this model → return null."""


def extract_inbody(image_bytes: bytes, content_type: str) -> InBodyRawExtraction:
    """Sends the scan image to the vision model with structured output."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    extraction_llm = _extraction_llm.with_structured_output(InBodyRawExtraction)

    return extraction_llm.invoke([
        SystemMessage(content=EXTRACTION_PROMPT),
        HumanMessage(content=[
            {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{b64}"}},
            {"type": "text", "text": "Extract all InBody data from this scan."},
        ]),
    ])


# ── Stage 4: deterministic flag computation (no LLM — no hallucination risk) ─

def to_kg(value: float, unit: str) -> float:
    """Normalize any segmental value to kg."""
    return value * 0.453592 if unit == "lb" else value


def compute_flags(r: InBodyRawExtraction) -> InBodyFlags:
    """Derives all flags deterministically from raw extracted values."""
    ra_kg = to_kg(r.right_arm.value, r.right_arm.unit)
    la_kg = to_kg(r.left_arm.value, r.left_arm.unit)
    rl_kg = to_kg(r.right_leg.value, r.right_leg.unit)
    ll_kg = to_kg(r.left_leg.value, r.left_leg.unit)

    arm_diff_g = abs(ra_kg - la_kg) * 1000
    leg_diff_g = abs(rl_kg - ll_kg) * 1000

    bf_threshold = 18.0 if r.gender == "male" else 25.0

    # trunk: use percent_of_ideal if available — InBody already normalises by body stats
    trunk_pct = r.trunk.percent_of_ideal
    trunk_underdeveloped = (trunk_pct < 100.0) if trunk_pct is not None else False

    return InBodyFlags(
        arm_asymmetry=arm_diff_g > 200,
        arm_diff_grams=round(arm_diff_g, 1),
        weaker_arm=("left" if la_kg < ra_kg else "right" if ra_kg < la_kg else None),

        leg_asymmetry=leg_diff_g > 500,
        leg_diff_grams=round(leg_diff_g, 1),
        weaker_leg=("left" if ll_kg < rl_kg else "right" if rl_kg < ll_kg else None),

        elevated_bf=r.body_fat_percent > bf_threshold,
        trunk_underdeveloped=trunk_underdeveloped,
    )


# ── Full image pipeline ───────────────────────────────────────────────────

def run_inbody_pipeline_from_bytes(image_bytes: bytes, content_type: str = "image/png") -> Union[InBodyResult, dict]:
    """
    Full pipeline from raw image bytes: quality check -> authenticity check ->
    extraction -> flag computation. Returns InBodyResult on success, or
    {"error": str, "stage": str} on failure.
    """
    quality = check_image_quality(image_bytes)
    if not quality["pass"]:
        return {
            "error": quality["issue"],
            "stage": "quality_check",
            "blur_score": quality["blur_score"],
            "brightness": quality["brightness"],
        }

    validation = validate_inbody_scan(image_bytes, content_type)
    if not validation.is_inbody_scan:
        return {"error": validation.issue or "This does not appear to be an InBody scan.", "stage": "authenticity_check"}

    raw = extract_inbody(image_bytes, content_type)
    flags = compute_flags(raw)
    return InBodyResult(raw=raw, flags=flags)


def run_inbody_pipeline(file_path: Union[str, Path]) -> Union[InBodyResult, dict]:
    """Convenience wrapper — loads from file path then calls the bytes pipeline."""
    image_bytes, content_type = load_scan(file_path)
    return run_inbody_pipeline_from_bytes(image_bytes, content_type)


def format_inbody_result(result: InBodyResult) -> str:
    """
    Converts a structured InBodyResult into the same "INBODY ANALYSIS ... FLAGS"
    text block that parse_inbody_text produces, so the Supervisor and all
    downstream sub-agents consume one consistent format regardless of whether
    the InBody data came from an image scan or raw text.
    """
    r, f = result.raw, result.flags
    yes_no = lambda b: "YES" if b else "NO"

    lines = [
        "INBODY ANALYSIS",
        "───────────────",
        f"Skeletal Muscle Mass : {r.skeletal_muscle_mass} {r.smm_unit}",
        f"Body Fat %           : {r.body_fat_percent}%",
        f"BMR                  : {r.bmr_kcal if r.bmr_kcal is not None else 'UNKNOWN'} kcal",
        "Segmental Lean Mass:",
        f"  Right arm : {r.right_arm.value} {r.right_arm.unit} | Left arm : {r.left_arm.value} {r.left_arm.unit}"
        f"  → Arm asymmetry: {yes_no(f.arm_asymmetry)} (diff: {f.arm_diff_grams}g)",
        f"  Right leg : {r.right_leg.value} {r.right_leg.unit} | Left leg : {r.left_leg.value} {r.left_leg.unit}"
        f"  → Leg asymmetry: {yes_no(f.leg_asymmetry)} (diff: {f.leg_diff_grams}g)",
        f"  Trunk     : {r.trunk.value} {r.trunk.unit}",
        "",
        "FLAGS (used by all sub-agents)",
        "───────────────────────────────",
        f"ARM_ASYMMETRY   : {yes_no(f.arm_asymmetry)}  — if YES, pull day must include unilateral movements",
        f"LEG_ASYMMETRY   : {yes_no(f.leg_asymmetry)}  — if YES, leg day prioritises unilateral, start on weaker side",
        f"ELEVATED_BF     : {yes_no(f.elevated_bf)}  — if YES (>18% male/>25% female), lean toward 12-15 rep ranges",
        f"TRUNK_UNDERDEVELOPED : {yes_no(f.trunk_underdeveloped)} — if YES, chest/back volume gets priority",
    ]
    return "\n".join(lines)


# ── Text-based path (dev/testing + the path the Supervisor actually calls) ──

INBODY_TEXT_SYSTEM_PROMPT = """You are an InBody scan analysis tool. Extract fitness-relevant data and output structured text.

Output format (follow exactly):

INBODY ANALYSIS
───────────────
Skeletal Muscle Mass : {value} kg
Body Fat %           : {value}%
BMR                  : {value} kcal
Segmental Lean Mass:
  Right arm : {value} kg | Left arm : {value} kg  → Arm asymmetry: YES/NO (diff: {value}g)
  Right leg : {value} kg | Left leg : {value} kg  → Leg asymmetry: YES/NO (diff: {value}g)
  Trunk     : {value} kg

FLAGS (used by all sub-agents)
───────────────────────────────
ARM_ASYMMETRY   : YES/NO  — if YES, pull day must include unilateral movements
LEG_ASYMMETRY   : YES/NO  — if YES, leg day prioritises unilateral, start on weaker side
ELEVATED_BF     : YES/NO  — if YES (>18% male/>25% female), lean toward 12-15 rep ranges
TRUNK_UNDERDEVELOPED : YES/NO — if YES, chest/back volume gets priority

Extract what you can from the scan. If a value is not visible, write UNKNOWN."""

_text_llm = get_llm(temperature=0.3)


@tool
def parse_inbody_text(session_id: str, raw_text: str) -> str:
    """Parse InBody data from raw text and return the structured ANALYSIS + FLAGS block.
    Use this when InBody data is already available as text (e.g. OCR output, or when
    an image has already been run through the image pipeline and formatted to text)."""
    prompt = f"""{INBODY_TEXT_SYSTEM_PROMPT}

Raw InBody text to parse:
{raw_text}"""
    result = _text_llm.invoke(prompt)
    return result.content
