"""
REST API Endpoint Routes for Athlete, Assessment, Sync, and Scout Talent Discovery.
Implements Sections 19, 21, and 22 of SIH 25073 specification.
"""

import uuid
import json
import io
import os
import random
import tempfile
import cv2
import numpy as np
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database.session import get_db
from app.models.db_models import Athlete, Assessment, Performance, OTPReset, Official
from app.models.schemas import (
    AthleteRegister, AthleteLogin, AthleteResponse, VideoAssessmentRequest, AssessmentResponse,
    PerformanceResponse, AthleteProfileResponse, SyncAssessmentItem, ScoutSearchRequest,
    OTPRequestSchema, OTPVerifySchema, ManualAssessmentRequest,
    OfficialRegister, OfficialLogin, OfficialResponse, TokenResponse
)
from app.cv_engine.situp_analyzer import SitUpAnalyzer
from app.cv_engine.vertical_jump_analyzer import VerticalJumpAnalyzer
from app.cv_engine.shuttle_run_analyzer import ShuttleRunAnalyzer
from app.cv_engine.broad_jump_analyzer import BroadJumpAnalyzer
from app.cv_engine.anomaly_verifier import AnomalyVerifier
from app.cv_engine.pose_detector import PoseDetector, HAS_CV2_MP
from app.scoring_engine.benchmarker import BenchmarkingEngine
from app.scoring_engine.performance_index import AthleticPerformanceIndexCalculator
from app.scoring_engine.coaching import generate_feedback
from app.database.sync_service import OfflineSyncService
from app.services.sms_service import send_otp_sms
from app.services.rate_limit import (
    rate_limit, register_otp_failure, otp_attempts_exceeded, reset_otp_attempts
)
from app.api.deps import get_current_athlete, get_current_official, get_athlete_or_official
from app.core import security
from app.services import verification as cert_sig, pdf_service
from app.core.config import settings

router = APIRouter()

# Lazily-created, process-wide PoseDetector for the live camera-check endpoint. Re-creating it per
# request would reload the MediaPipe model every call (catastrophic at ~1 Hz), so we cache one.
_CAMERA_CHECK_DETECTOR = None


def _get_camera_check_detector():
    global _CAMERA_CHECK_DETECTOR
    if _CAMERA_CHECK_DETECTOR is None:
        _CAMERA_CHECK_DETECTOR = PoseDetector()
    return _CAMERA_CHECK_DETECTOR


# ─────────────────────────────────────────────────────────────────────────────
# Shared assessment helpers
# These centralize the logic that previously lived (and drifted) inside both the
# /assessment/process-video and /assessment/upload-video handlers.
# ─────────────────────────────────────────────────────────────────────────────

# Tests whose result is derived from a pose-landmark video by a CV analyzer.
CV_TESTS = {t for t, meta in settings.TEST_REGISTRY.items() if meta.get("capture") == "cv"}
# Tests entered manually (stopwatch / tape / sit-&-reach box) — no reliable single-clip CV.
MANUAL_TESTS = {t for t, meta in settings.TEST_REGISTRY.items() if meta.get("capture") == "manual"}
# Tests accepted by the manual-entry endpoint: the manual tests plus CV tests that allow a
# tape-measure fallback (e.g. broad jump, where the officiated tape value is authoritative).
MANUAL_ENTRY_ALLOWED = MANUAL_TESTS | {
    t for t, meta in settings.TEST_REGISTRY.items() if meta.get("manual_fallback")
}


def _unit_for(test_type: str) -> str:
    """Display unit for a test, from the single-source-of-truth registry."""
    return settings.TEST_REGISTRY.get(test_type, {}).get("unit", "")


def _run_cv_analyzer(test_type: str, landmark_history: list, fps: float,
                     reference_height_cm: Optional[float] = 170.0):
    """
    Dispatch a pose-landmark sequence to the correct CV analyzer.
    Returns (raw_score, results_dict, test_valid). Raises HTTP 400 for non-CV tests.
    """
    ref = reference_height_cm or 170.0
    if test_type == "sit_up":
        results = SitUpAnalyzer().analyze_sequence(landmark_history, fps=fps)
        return (float(results["valid_reps"]), results,
                results["valid_reps"] >= 1 or results["total_reps"] >= 1)
    if test_type == "vertical_jump":
        results = VerticalJumpAnalyzer(reference_athlete_height_cm=ref).analyze_sequence(
            landmark_history, fps=fps, user_height_cm=reference_height_cm)
        return (float(results["jump_height_cm"]), results,
                results["takeoff_detected"] and results["landing_detected"])
    if test_type == "shuttle_run":
        results = ShuttleRunAnalyzer().analyze_sequence(landmark_history, fps=fps)
        return float(results["total_time_sec"]), results, results["valid_run"]
    if test_type == "broad_jump":
        results = BroadJumpAnalyzer(reference_athlete_height_cm=ref).analyze_sequence(
            landmark_history, fps=fps, user_height_cm=reference_height_cm)
        return (float(results["jump_distance_cm"]), results,
                results["takeoff_detected"] and results["landing_detected"])
    valid = ", ".join(sorted(CV_TESTS))
    raise HTTPException(status_code=400, detail=f"Invalid CV test_type '{test_type}'. Must be one of: {valid}.")


def _bmi_and_score(athlete: Athlete):
    """(bmi_value, bmi_score) computed live from the athlete profile, or (None, None)."""
    bmi = BenchmarkingEngine.compute_bmi(athlete.height_cm, athlete.weight_kg)
    if bmi is None:
        return None, None
    score, _status, _src = BenchmarkingEngine.normalize_score(bmi, "bmi", athlete.age, athlete.category)
    return bmi, score


def _compute_index(db: Session, athlete: Athlete):
    """Recompute the Athletic Performance Index (folding in live BMI). Returns (index_data, bmi)."""
    all_assessments = db.query(Assessment).filter(Assessment.athlete_id == athlete.athlete_id).all()
    bmi, bmi_score = _bmi_and_score(athlete)
    index_data = AthleticPerformanceIndexCalculator.calculate_index(all_assessments, bmi_score=bmi_score)
    return index_data, bmi


def _persist_performance(db: Session, athlete: Athlete):
    """
    Recompute and UPSERT the Performance row. Creating the row when it is missing fixes the
    latent bug where a missing Performance record was silently never saved. Returns (index_data, bmi).
    """
    index_data, bmi = _compute_index(db, athlete)
    perf = db.query(Performance).filter(Performance.athlete_id == athlete.athlete_id).first()
    if not perf:
        perf = Performance(athlete_id=athlete.athlete_id)
        db.add(perf)
    perf.speed_score = index_data["speed_score"]
    perf.agility_score = index_data["agility_score"]
    perf.strength_score = index_data["strength_score"]
    perf.power_score = index_data["power_score"]
    perf.endurance_score = index_data["endurance_score"]
    perf.flexibility_score = index_data["flexibility_score"]
    perf.body_composition_score = index_data["body_composition_score"]
    perf.overall_index = index_data["overall_index"]
    db.commit()
    return index_data, bmi


def _perf_response(athlete_id: str, index_data: dict, bmi: Optional[float]) -> PerformanceResponse:
    """Build a PerformanceResponse from a freshly computed index + live BMI."""
    return PerformanceResponse(
        athlete_id=athlete_id,
        speed_score=index_data["speed_score"],
        agility_score=index_data["agility_score"],
        strength_score=index_data["strength_score"],
        power_score=index_data["power_score"],
        endurance_score=index_data["endurance_score"],
        flexibility_score=index_data["flexibility_score"],
        body_composition_score=index_data["body_composition_score"],
        bmi=bmi,
        overall_index=index_data["overall_index"],
        tests_completed=index_data["tests_completed"],
    )


def _coaching_for(details: dict, test_type: str, raw_score: float,
                  normalized_score: float, athlete: Athlete) -> dict:
    """
    Corrective coaching feedback for an assessment. Reuses the feedback already stored in
    `details["coaching"]` (fresh captures) and computes it on the fly when missing, so
    historical rows displayed in the profile/scout views also get feedback. Pure — no re-sign.
    """
    if isinstance(details, dict):
        existing = details.get("coaching")
        if existing:
            return existing
    return generate_feedback(
        test_type, raw_score, normalized_score,
        details=details, age=athlete.age, category=athlete.category,
    )


@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit(10, 3600))])
def register_athlete(req: AthleteRegister, db: Session = Depends(get_db)):
    """Register a new athlete, issue a unique Athlete ID, and return an access token."""
    random_num = str(uuid.uuid4().int)[:6]
    athlete_id = f"ATH-2026-{random_num}"

    athlete = Athlete(
        athlete_id=athlete_id,
        name=req.name,
        age=req.age,
        category=req.category,
        state=req.state,
        district=req.district,
        school=req.school,
        sports_interest=req.sports_interest,
        height_cm=req.height_cm,
        weight_kg=req.weight_kg,
        phone=req.phone,
        email=req.email,
        password_hash=security.hash_password(req.password)
    )
    db.add(athlete)

    # Initialize baseline performance record (starts at 0 — no fake scores)
    perf = Performance(
        athlete_id=athlete_id,
        speed_score=0.0,
        agility_score=0.0,
        strength_score=0.0,
        power_score=0.0,
        endurance_score=0.0,
        overall_index=0.0
    )
    db.add(perf)
    db.commit()
    db.refresh(athlete)

    token = security.create_access_token(athlete.athlete_id, typ="athlete")
    return TokenResponse(access_token=token, account_type="athlete",
                         athlete=AthleteResponse.from_orm(athlete))

@router.post("/auth/login", response_model=TokenResponse, dependencies=[Depends(rate_limit(10, 300))])
def login_athlete(req: AthleteLogin, db: Session = Depends(get_db)):
    """Login an existing athlete by Athlete ID and password; return an access token."""
    athlete = db.query(Athlete).filter(Athlete.athlete_id == req.athlete_id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="No athlete found with this ID. Please check your Athlete ID.")

    is_valid, needs_rehash = security.verify_password(req.password, athlete.password_hash)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Incorrect password. Please try again or reset your password.")

    # Transparently upgrade legacy SHA-256 hashes to bcrypt on successful login.
    if needs_rehash:
        athlete.password_hash = security.hash_password(req.password)
        db.commit()

    token = security.create_access_token(athlete.athlete_id, typ="athlete")
    return TokenResponse(access_token=token, account_type="athlete",
                         athlete=AthleteResponse.from_orm(athlete))


@router.post("/auth/request-otp", dependencies=[Depends(rate_limit(5, 600))])
def request_password_reset_otp(req: OTPRequestSchema, db: Session = Depends(get_db)):
    """Generate a 6-digit OTP for password reset and dispatch it via SMS (Twilio)."""
    ident = req.athlete_id.strip()
    athlete = db.query(Athlete).filter(
        (Athlete.athlete_id == ident) | (Athlete.phone == ident) | (Athlete.email == ident)
    ).first()
    if not athlete:
        raise HTTPException(
            status_code=404,
            detail=f"No athlete found matching '{ident}'. Please check your Athlete ID, Phone Number, or Email."
        )

    if not athlete.phone:
        raise HTTPException(
            status_code=400,
            detail="No phone number is registered for this athlete, so an SMS OTP cannot be sent. Please contact support."
        )

    otp_code = str(random.randint(100000, 999999))

    otp_record = OTPReset(
        athlete_id=athlete.athlete_id,
        otp_code=otp_code,
        created_at=datetime.utcnow(),
        used=0
    )
    db.add(otp_record)
    db.commit()

    # A fresh OTP was issued — clear any prior failed-attempt count for this athlete.
    reset_otp_attempts(athlete.athlete_id)

    # Dispatch the real SMS and report the true outcome.
    sms_res = send_otp_sms(athlete.phone, otp_code)
    delivered = bool(sms_res.get("delivered"))
    contact_display = sms_res.get("to") or athlete.phone

    resp = {
        "athlete_id": athlete.athlete_id,
        "contact": contact_display,
        "expires_in_minutes": 10,
        "delivered": delivered,
        "delivery_provider": sms_res.get("provider", "none"),
    }

    if delivered:
        resp["message"] = f"OTP sent via SMS to {contact_display}. Please check your phone."
    else:
        resp["message"] = f"Could not deliver SMS: {sms_res.get('detail', 'SMS is not configured')}"

    # Only expose the OTP when real delivery did NOT happen and debug mode is on, so the
    # flow stays demoable but the code is never leaked once real SMS delivery works.
    if settings.SMS_DEBUG and not delivered:
        resp["otp_code"] = otp_code
        resp["debug_note"] = (
            "SMS_DEBUG is on and the SMS was not delivered — showing the OTP for testing only. "
            "Configure Twilio in .env and set SMS_DEBUG=false to disable this."
        )

    return resp

@router.post("/auth/reset-password", dependencies=[Depends(rate_limit(10, 600))])
def verify_otp_and_reset_password(req: OTPVerifySchema, db: Session = Depends(get_db)):
    """Verify OTP and reset athlete password."""
    ident = req.athlete_id.strip()
    athlete = db.query(Athlete).filter(
        (Athlete.athlete_id == ident) | (Athlete.phone == ident) | (Athlete.email == ident)
    ).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="No athlete found matching this ID or phone number.")

    # Block brute-forcing: after too many wrong OTPs, invalidate outstanding OTPs.
    if otp_attempts_exceeded(athlete.athlete_id):
        db.query(OTPReset).filter(
            OTPReset.athlete_id == athlete.athlete_id, OTPReset.used == 0
        ).update({OTPReset.used: 1})
        db.commit()
        raise HTTPException(
            status_code=429,
            detail="Too many incorrect OTP attempts. Please request a new OTP."
        )

    # Find the most recent unused OTP for this athlete (ordered by auto-increment ID desc)
    otp_record = (
        db.query(OTPReset)
        .filter(OTPReset.athlete_id == athlete.athlete_id, OTPReset.used == 0)
        .order_by(OTPReset.id.desc())
        .first()
    )

    if not otp_record:
        raise HTTPException(status_code=400, detail="No active OTP found. Please request a new one.")

    # Check expiry (10 minutes = 600 seconds)
    time_diff = (datetime.utcnow() - otp_record.created_at).total_seconds()
    if time_diff > 600 or time_diff < -60:
        otp_record.used = 1
        db.commit()
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

    if otp_record.otp_code != req.otp_code.strip():
        attempts = register_otp_failure(athlete.athlete_id)
        remaining = max(0, 5 - attempts)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid OTP. Please check the code sent via SMS. {remaining} attempts remaining."
        )

    # Mark OTP as used and update password (bcrypt)
    otp_record.used = 1
    athlete.password_hash = security.hash_password(req.new_password)
    db.commit()
    reset_otp_attempts(athlete.athlete_id)

    return {"message": "Password reset successful! You can now login with your new password."}


# ─── Official / Scout authentication ───
@router.post("/auth/official/register", response_model=TokenResponse,
             status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit(10, 3600))])
def register_official(req: OfficialRegister, db: Session = Depends(get_db)):
    """
    Register a scout/official account. Requires the shared OFFICIAL_SIGNUP_KEY so that
    not just anyone can gain access to athlete PII via the scout search.
    """
    if req.signup_key.strip() != settings.OFFICIAL_SIGNUP_KEY:
        raise HTTPException(status_code=403, detail="Invalid official enrolment key.")

    email = req.email.strip().lower()
    if db.query(Official).filter(Official.email == email).first():
        raise HTTPException(status_code=409, detail="An official account with this email already exists.")

    random_num = str(uuid.uuid4().int)[:6]
    official = Official(
        official_id=f"OFF-2026-{random_num}",
        name=req.name.strip(),
        email=email,
        organization=(req.organization or "").strip() or None,
        phone=(req.phone or "").strip() or None,
        password_hash=security.hash_password(req.password),
    )
    db.add(official)
    db.commit()
    db.refresh(official)

    token = security.create_access_token(official.official_id, typ="official")
    return TokenResponse(access_token=token, account_type="official",
                         official=OfficialResponse.from_orm(official))


@router.post("/auth/official/login", response_model=TokenResponse,
             dependencies=[Depends(rate_limit(10, 300))])
def login_official(req: OfficialLogin, db: Session = Depends(get_db)):
    """Login an official/scout by email + password; return an access token."""
    email = req.email.strip().lower()
    official = db.query(Official).filter(Official.email == email).first()
    if not official:
        raise HTTPException(status_code=404, detail="No official account found with this email.")

    is_valid, needs_rehash = security.verify_password(req.password, official.password_hash)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Incorrect password. Please try again.")
    if needs_rehash:
        official.password_hash = security.hash_password(req.password)
        db.commit()

    token = security.create_access_token(official.official_id, typ="official")
    return TokenResponse(access_token=token, account_type="official",
                         official=OfficialResponse.from_orm(official))


@router.get("/athlete/profile/{athlete_id}", response_model=AthleteProfileResponse)
def get_athlete_profile(athlete_id: str, db: Session = Depends(get_db),
                        caller: dict = Depends(get_athlete_or_official)):
    """Fetch complete Athlete Profile including Performance Index and Recent Assessments."""
    # Athletes may only read their own profile; officials may read anyone's.
    if caller["typ"] == "athlete" and caller["id"] != athlete_id:
        raise HTTPException(status_code=403, detail="You can only view your own profile.")
    athlete = db.query(Athlete).filter(Athlete.athlete_id == athlete_id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

    assessments = db.query(Assessment).filter(Assessment.athlete_id == athlete_id).order_by(Assessment.timestamp.desc()).all()

    assessment_responses = []
    for a in assessments:
        bench_score, bench_status, bench_src = BenchmarkingEngine.normalize_score(
            a.raw_score, a.test_type, athlete.age, athlete.category
        )

        details = json.loads(a.details_json) if a.details_json else {}
        coaching = _coaching_for(details, a.test_type, a.raw_score, a.normalized_score, athlete)
        details["coaching"] = coaching  # also expose via the details channel for older clients

        assessment_responses.append(AssessmentResponse(
            assessment_id=a.assessment_id,
            athlete_id=a.athlete_id,
            test_type=a.test_type,
            raw_score=a.raw_score,
            unit=_unit_for(a.test_type),
            normalized_score=a.normalized_score,
            confidence=a.confidence,
            validation_score=a.validation_score,
            status=a.status,
            benchmark_status=bench_status,
            benchmark_source=bench_src,
            timestamp=a.timestamp,
            details=details,
            coaching=coaching
        ))

    # Compute the index live so the profile reflects the current battery + BMI from the
    # live profile, even before the stored Performance row has been rebuilt.
    index_data, bmi = _compute_index(db, athlete)
    perf_response = _perf_response(athlete_id, index_data, bmi)

    return AthleteProfileResponse(
        athlete=AthleteResponse.from_orm(athlete),
        performance=perf_response,
        recent_assessments=assessment_responses
    )

@router.post("/assessment/process-video", response_model=AssessmentResponse)
def process_assessment_video(req: VideoAssessmentRequest, db: Session = Depends(get_db),
                             current: Athlete = Depends(get_current_athlete)):
    """
    Process video landmark frames through the Real AI CV & Anomaly Verification Engines.
    Computes real reps/jump height/shuttle time, verifies authenticity, normalizes scores, and updates Athletic Performance Index.
    """
    # Bind the assessment to the authenticated athlete — ignore any client-supplied id.
    req.athlete_id = current.athlete_id
    athlete = current

    # Convert schema landmark frames to internal analyzer landmark format
    landmark_history = []
    for frame in req.frames:
        frame_dict = {}
        for name, kp in frame.landmarks.items():
            frame_dict[name] = (kp.x, kp.y, kp.visibility)
        landmark_history.append(frame_dict)

    # 1. Execute Test-Specific AI Model Engine (centralized CV dispatch)
    raw_score, results, test_valid = _run_cv_analyzer(
        req.test_type, landmark_history, req.fps, reference_height_cm=req.reference_height_cm
    )
    unit = _unit_for(req.test_type)

    # 2. Execute AI Fraud & Anomaly Detector
    verifier = AnomalyVerifier()
    verification = verifier.verify_assessment(landmark_history, fps=req.fps, test_specific_valid=test_valid)

    # 3. Execute Benchmarking & Score Normalization
    normalized_score, bench_status, bench_src = BenchmarkingEngine.normalize_score(
        raw_score, req.test_type, athlete.age, athlete.category
    )

    assessment_id = f"ASM-{uuid.uuid4().hex[:8]}"
    confidence = float(results.get("confidence", 90.0))
    validation_score = float(verification.get("validation_score", 95.0))
    assessment_status = verification.get("status", "VALID")

    # 3b. Generate corrective coaching feedback (what to fix + how). Pass verification so
    # capture-quality flags become part of the feedback. Stored in results so it persists
    # in details_json and rides the response.
    coaching = generate_feedback(
        req.test_type, raw_score, normalized_score,
        details={**results, "verification": verification},
        age=athlete.age, category=athlete.category,
    )
    results["coaching"] = coaching

    # 4. Save Assessment Record (with a tamper-evident HMAC signature over the scored fields)
    assessment_ts = datetime.utcnow()
    signature = cert_sig.sign_fields(
        req.athlete_id, req.test_type, raw_score, normalized_score, assessment_status, assessment_ts
    )
    assessment = Assessment(
        assessment_id=assessment_id,
        athlete_id=req.athlete_id,
        test_type=req.test_type,
        raw_score=raw_score,
        normalized_score=normalized_score,
        confidence=confidence,
        validation_score=validation_score,
        timestamp=assessment_ts,
        status=assessment_status,
        sync_status="SYNCED",
        details_json=json.dumps({**results, "verification": verification, cert_sig.SIGNATURE_KEY: signature})
    )
    db.add(assessment)
    db.commit()

    # 5. Update Athlete Performance Index Record (UPSERT — creates the row if missing).
    _persist_performance(db, athlete)

    return AssessmentResponse(
        assessment_id=assessment_id,
        athlete_id=req.athlete_id,
        test_type=req.test_type,
        raw_score=raw_score,
        unit=unit,
        normalized_score=normalized_score,
        confidence=confidence,
        validation_score=validation_score,
        status=assessment_status,
        benchmark_status=bench_status,
        benchmark_source=bench_src,
        timestamp=assessment.timestamp,
        details=results,
        coaching=coaching
    )

@router.post("/assessment/manual-entry", response_model=AssessmentResponse)
def submit_manual_assessment(req: ManualAssessmentRequest, db: Session = Depends(get_db),
                             current: Athlete = Depends(get_current_athlete)):
    """
    Record a MANUAL / assisted-entry test result — 50m dash, 600m endurance run, sit & reach,
    or a tape-measured broad jump — which cannot be reliably measured by CV from a single phone
    clip. The value is validated against the registry plausibility bounds, normalized against
    age/sex norms, signed, stored, and folded into the Athletic Performance Index.
    """
    athlete = current
    test_type = req.test_type
    reg = settings.TEST_REGISTRY.get(test_type)
    if not reg:
        valid = ", ".join(sorted(MANUAL_ENTRY_ALLOWED))
        raise HTTPException(status_code=400, detail=f"Unknown test_type '{test_type}'. Manual-entry tests: {valid}.")
    if test_type not in MANUAL_ENTRY_ALLOWED:
        raise HTTPException(
            status_code=400,
            detail=f"'{test_type}' is a {reg.get('capture')} test — submit it via the video endpoints, not manual entry."
        )

    raw_score = float(req.raw_value)
    lo = float(reg.get("plausible_min", float("-inf")))
    hi = float(reg.get("plausible_max", float("inf")))
    within_bounds = lo <= raw_score <= hi

    verification = AnomalyVerifier.verify_manual_entry(
        test_type, raw_score, within_bounds=within_bounds, officiated=req.officiated
    )
    if not within_bounds:
        raise HTTPException(
            status_code=400,
            detail=(f"Value {raw_score} {reg.get('unit', '')} is outside the plausible range "
                    f"[{lo}, {hi}] for {reg.get('label', test_type)}. Please re-check the measurement.")
        )

    # Normalize against age/sex norms.
    normalized_score, bench_status, bench_src = BenchmarkingEngine.normalize_score(
        raw_score, test_type, athlete.age, athlete.category
    )

    results = {
        "entry_mode": "manual",
        "officiated": bool(req.officiated),
        "notes": req.notes,
        "unit": reg.get("unit", ""),
        "protocol": reg.get("protocol", ""),
        "verification": verification,
    }
    # Corrective coaching feedback — norm-based for manual tests (no rich CV signals), plus any
    # capture/plausibility flags from verify_manual_entry.
    coaching = generate_feedback(
        test_type, raw_score, normalized_score,
        details=results, age=athlete.age, category=athlete.category,
    )
    results["coaching"] = coaching
    assessment_id = f"ASM-{uuid.uuid4().hex[:8]}"
    confidence = float(verification.get("authenticity_score", 75.0))
    validation_score = float(verification.get("validation_score", 75.0))
    assessment_status = verification.get("status", "VALID")

    # Save with a tamper-evident HMAC signature over the scored fields.
    assessment_ts = datetime.utcnow()
    signature = cert_sig.sign_fields(
        athlete.athlete_id, test_type, raw_score, normalized_score, assessment_status, assessment_ts
    )
    results[cert_sig.SIGNATURE_KEY] = signature
    assessment = Assessment(
        assessment_id=assessment_id,
        athlete_id=athlete.athlete_id,
        test_type=test_type,
        raw_score=raw_score,
        normalized_score=normalized_score,
        confidence=confidence,
        validation_score=validation_score,
        timestamp=assessment_ts,
        status=assessment_status,
        sync_status="SYNCED",
        details_json=json.dumps(results)
    )
    db.add(assessment)
    db.commit()

    _persist_performance(db, athlete)

    return AssessmentResponse(
        assessment_id=assessment_id,
        athlete_id=athlete.athlete_id,
        test_type=test_type,
        raw_score=raw_score,
        unit=reg.get("unit", ""),
        normalized_score=normalized_score,
        confidence=confidence,
        validation_score=validation_score,
        status=assessment_status,
        benchmark_status=bench_status,
        benchmark_source=bench_src,
        timestamp=assessment.timestamp,
        details=results,
        coaching=coaching
    )

@router.post("/assessment/sync")
def sync_offline_assessments(items: List[SyncAssessmentItem], db: Session = Depends(get_db),
                             current: Athlete = Depends(get_current_athlete)):
    """Offline Synchronization API Endpoint (Section 18)."""
    # Force every synced item to belong to the authenticated athlete.
    items_dict = []
    for item in items:
        d = item.dict()
        d["athlete_id"] = current.athlete_id
        items_dict.append(d)
    result = OfflineSyncService.sync_incoming_assessments(db, items_dict)
    return result

@router.post("/assessment/upload-video")
async def upload_assessment_video(
    file: UploadFile = File(...),
    athlete_id: str = Form(...),
    test_type: str = Form(...),
    reference_height_cm: Optional[float] = Form(170.0),
    db: Session = Depends(get_db),
    current: Athlete = Depends(get_current_athlete)
):
    """
    Accepts real video upload (.mp4, .webm, .mov), extracts frames with OpenCV,
    processes with MediaPipe Pose Deep Learning Model, executes biomechanical analyzers,
    performs anti-cheat verification, and records scores.
    """
    # Bind the upload to the authenticated athlete — ignore any client-supplied id.
    athlete_id = current.athlete_id
    athlete = current

    # Save uploaded video to temp file
    suffix = os.path.splitext(file.filename)[1] if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_vid:
        content = await file.read()
        temp_vid.write(content)
        temp_vid_path = temp_vid.name

    try:
        cap = cv2.VideoCapture(temp_vid_path)
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Could not open uploaded video file.")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or np.isnan(fps):
            fps = 30.0

        pose_detector = PoseDetector()
        landmark_history = []
        frames_data = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Process with MediaPipe
            landmarks = pose_detector.process_frame(frame)
            if landmarks:
                landmark_history.append(landmarks)
                frames_data.append({
                    "frame_index": frame_idx,
                    "timestamp": round(frame_idx / fps, 3),
                    "landmarks": landmarks
                })
            frame_idx += 1

        cap.release()
    finally:
        if os.path.exists(temp_vid_path):
            try:
                os.remove(temp_vid_path)
            except Exception:
                pass

    if len(landmark_history) < 10:
        raise HTTPException(
            status_code=400,
            detail=f"Only {len(landmark_history)} pose frames detected. Please ensure full body of athlete is visible in the video."
        )

    # 1. Execute Test-Specific AI Model Engine (centralized CV dispatch)
    raw_score, results, test_valid = _run_cv_analyzer(
        test_type, landmark_history, fps, reference_height_cm=reference_height_cm
    )
    unit = _unit_for(test_type)

    # 2. Execute AI Fraud & Anomaly Detector
    verifier = AnomalyVerifier()
    verification = verifier.verify_assessment(landmark_history, fps=fps, test_specific_valid=test_valid)

    # 3. Execute Benchmarking & Score Normalization
    normalized_score, bench_status, bench_src = BenchmarkingEngine.normalize_score(
        raw_score, test_type, athlete.age, athlete.category
    )

    assessment_id = f"ASM-{uuid.uuid4().hex[:8]}"
    confidence = float(results.get("confidence", 90.0))
    validation_score = float(verification.get("validation_score", 95.0))
    assessment_status = verification.get("status", "VALID")

    # 3b. Corrective coaching feedback (what to fix + how), incl. capture-quality flags.
    coaching = generate_feedback(
        test_type, raw_score, normalized_score,
        details={**results, "verification": verification},
        age=athlete.age, category=athlete.category,
    )
    results["coaching"] = coaching

    # 4. Save Assessment Record (with a tamper-evident HMAC signature over the scored fields)
    assessment_ts = datetime.utcnow()
    signature = cert_sig.sign_fields(
        athlete_id, test_type, raw_score, normalized_score, assessment_status, assessment_ts
    )
    assessment = Assessment(
        assessment_id=assessment_id,
        athlete_id=athlete_id,
        test_type=test_type,
        raw_score=raw_score,
        normalized_score=normalized_score,
        confidence=confidence,
        validation_score=validation_score,
        timestamp=assessment_ts,
        status=assessment_status,
        sync_status="SYNCED",
        details_json=json.dumps({**results, "verification": verification, cert_sig.SIGNATURE_KEY: signature})
    )
    db.add(assessment)
    db.commit()

    # 5. Update Athlete Performance Index Record (UPSERT — creates the row if missing).
    _persist_performance(db, athlete)

    # 6. Prepare skeleton-overlay frames for the frontend.
    # Every frame keeps its TRUE timestamp so the overlay can be synced to
    # video.currentTime. For long clips we evenly downsample across the WHOLE
    # timeline instead of truncating the tail — that way the skeleton tracks the
    # video from start to finish rather than freezing partway through.
    MAX_OVERLAY_FRAMES = 900  # ~30s at 30fps; nearest-timestamp lookup keeps it smooth
    if len(frames_data) > MAX_OVERLAY_FRAMES:
        step = len(frames_data) / MAX_OVERLAY_FRAMES
        overlay_frames = [frames_data[int(i * step)] for i in range(MAX_OVERLAY_FRAMES)]
    else:
        overlay_frames = frames_data

    return {
        "assessment_id": assessment_id,
        "athlete_id": athlete_id,
        "test_type": test_type,
        "raw_score": raw_score,
        "unit": unit,
        "normalized_score": normalized_score,
        "confidence": confidence,
        "validation_score": validation_score,
        "status": assessment_status,
        "benchmark_status": bench_status,
        "benchmark_source": bench_src,
        "timestamp": assessment.timestamp.isoformat(),
        "details": results,
        "coaching": coaching,
        "verification": verification,
        "frames_summary": {
            "total_frames_processed": frame_idx,
            "pose_frames_detected": len(landmark_history),
            "fps": fps
        },
        "frames_landmarks": overlay_frames  # timestamped keypoint frames for synced overlay
    }


@router.post("/assessment/camera-check")
async def camera_alignment_check(
    file: UploadFile = File(...),
    test_type: str = Form(...),
    current: Athlete = Depends(get_current_athlete)
):
    """
    Real-time camera alignment guidance for LIVE capture (webcam), NOT the upload-video path.

    Accepts one downscaled JPEG frame + the chosen test_type, runs the same trusted MediaPipe
    PoseDetector used for scoring, and returns pose-aware guidance: full-body visibility,
    centering, distance, orientation, a single prioritized `instruction`, and a 0-100
    `alignment_score` the client gates its Start button on.

    Degrades gracefully: if the CV libraries are unavailable, or the frame can't be decoded, or
    no pose is found, it returns a well-formed low-readiness payload so the client can fall back
    to its honest on-device luminance heuristic instead of hard-blocking the athlete.
    """
    # No CV stack on the server → tell the client to use its on-device checks.
    if not HAS_CV2_MP:
        return {
            "cv_available": False,
            "ready": False,
            "full_body_visible": False,
            "centered": False,
            "distance_ok": False,
            "orientation_ok": True,
            "alignment_score": 0,
            "test_type": test_type,
            "instruction": "Server pose guidance is unavailable — using on-device checks.",
            "message": "Server pose guidance is unavailable — using on-device checks.",
        }

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty camera frame.")

    arr = np.frombuffer(content, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Could not decode camera frame image.")

    detector = _get_camera_check_detector()
    landmarks = detector.process_frame(frame)
    history = [landmarks] if landmarks else []
    guidance = PoseDetector.check_camera_guidance(history, frame_bgr=frame, test_type=test_type)
    guidance["cv_available"] = True
    return guidance


@router.get("/scout/search", response_model=List[AthleteProfileResponse])
def search_scout_talent(
    state: Optional[str] = None,
    district: Optional[str] = None,
    min_overall_index: Optional[float] = None,
    test_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current: Official = Depends(get_current_official)
):
    """
    Scout Talent Discovery Search API Endpoint (Sections 21, 22, 23).
    Filter athletes by State, District, Performance Range (>80), Test Type, and Validation Status.
    """
    query = db.query(Athlete)
    if state:
        query = query.filter(Athlete.state.ilike(f"%{state}%"))
    if district:
        query = query.filter(Athlete.district.ilike(f"%{district}%"))

    athletes = query.all()
    results = []

    for athlete in athletes:
        perf = db.query(Performance).filter(Performance.athlete_id == athlete.athlete_id).first()
        if min_overall_index is not None:
            if not perf or perf.overall_index < min_overall_index:
                continue

        assessments = db.query(Assessment).filter(Assessment.athlete_id == athlete.athlete_id).order_by(Assessment.timestamp.desc()).all()
        if test_type:
            assessments = [a for a in assessments if a.test_type == test_type]
            if not assessments:
                continue

        assessment_responses = []
        for a in assessments:
            details = json.loads(a.details_json) if a.details_json else {}
            coaching = _coaching_for(details, a.test_type, a.raw_score, a.normalized_score, athlete)
            details["coaching"] = coaching
            assessment_responses.append(AssessmentResponse(
                assessment_id=a.assessment_id,
                athlete_id=a.athlete_id,
                test_type=a.test_type,
                raw_score=a.raw_score,
                unit=_unit_for(a.test_type),
                normalized_score=a.normalized_score,
                confidence=a.confidence,
                validation_score=a.validation_score,
                status=a.status,
                benchmark_status=BenchmarkingEngine.classify(a.normalized_score),
                benchmark_source=settings.TEST_REGISTRY.get(a.test_type, {}).get(
                    "source", settings.BENCHMARK_SOURCE_LABEL),
                timestamp=a.timestamp,
                details=details,
                coaching=coaching
            ))

        # Build the performance card from the stored row plus a live BMI from the profile.
        perf_response = None
        if perf:
            bmi = BenchmarkingEngine.compute_bmi(athlete.height_cm, athlete.weight_kg)
            perf_response = PerformanceResponse(
                athlete_id=perf.athlete_id,
                speed_score=perf.speed_score,
                agility_score=perf.agility_score,
                strength_score=perf.strength_score,
                power_score=perf.power_score,
                endurance_score=perf.endurance_score,
                flexibility_score=getattr(perf, "flexibility_score", 0.0) or 0.0,
                body_composition_score=getattr(perf, "body_composition_score", 0.0) or 0.0,
                bmi=bmi,
                overall_index=perf.overall_index,
            )

        results.append(AthleteProfileResponse(
            athlete=AthleteResponse.from_orm(athlete),
            performance=perf_response,
            recent_assessments=assessment_responses
        ))

    return results


# ─── Verified certificate (Move 3) ───


@router.get("/assessment/{assessment_id}/certificate")
def download_certificate(assessment_id: str, db: Session = Depends(get_db),
                         caller: dict = Depends(get_athlete_or_official)):
    """
    Generate and download the verified PDF certificate for one assessment.
    Athletes may download only their own certificate; officials may download any.
    """
    assessment = db.query(Assessment).filter(Assessment.assessment_id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    if caller["typ"] == "athlete" and caller["id"] != assessment.athlete_id:
        raise HTTPException(status_code=403, detail="You can only download your own certificate.")

    athlete = db.query(Athlete).filter(Athlete.athlete_id == assessment.athlete_id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found.")

    details = json.loads(assessment.details_json) if assessment.details_json else {}
    # Use the issue-time signature if present; otherwise sign the current row (legacy record).
    stored_sig = details.get(cert_sig.SIGNATURE_KEY) or cert_sig.sign_assessment(assessment)

    verify_url = f"{settings.PUBLIC_BASE_URL}/api/v1/verify/{assessment_id}"
    location = f"{athlete.district}, {athlete.state}"

    pdf_bytes = pdf_service.generate_certificate_pdf(
        name=athlete.name,
        athlete_id=athlete.athlete_id,
        age=athlete.age,
        category=athlete.category,
        location=location,
        test_label=settings.TEST_REGISTRY.get(assessment.test_type, {}).get("label", assessment.test_type),
        raw_score=assessment.raw_score,
        unit=_unit_for(assessment.test_type),
        normalized_score=assessment.normalized_score,
        validation_score=assessment.validation_score,
        status=assessment.status,
        timestamp_text=assessment.timestamp.strftime("%d %b %Y, %H:%M UTC"),
        verify_url=verify_url,
        signature_display=cert_sig.short_signature(stored_sig),
        benchmark_label=settings.BENCHMARK_SOURCE_LABEL,
    )

    headers = {"Content-Disposition": f'attachment; filename="SAI_Certificate_{assessment_id}.pdf"'}
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


@router.get("/verify/{assessment_id}")
def verify_certificate(assessment_id: str, db: Session = Depends(get_db)):
    """
    Public authenticity check for a certificate (scanned from its QR code).
    Recomputes the HMAC signature from the stored record and reports whether it still
    matches the issue-time signature — so any tampering with a stored score is detected.
    """
    assessment = db.query(Assessment).filter(Assessment.assessment_id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="No assessment found for this certificate ID.")

    athlete = db.query(Athlete).filter(Athlete.athlete_id == assessment.athlete_id).first()
    details = json.loads(assessment.details_json) if assessment.details_json else {}
    stored_sig = details.get(cert_sig.SIGNATURE_KEY)
    authentic, note = cert_sig.verify_assessment(assessment, stored_sig)

    return {
        "authentic": authentic,
        "verification_note": note,
        "assessment_id": assessment.assessment_id,
        "athlete_id": assessment.athlete_id,
        "athlete_name": athlete.name if athlete else None,
        "test_type": assessment.test_type,
        "raw_score": assessment.raw_score,
        "normalized_score": assessment.normalized_score,
        "validation_score": assessment.validation_score,
        "status": assessment.status,
        "assessed_on": assessment.timestamp.isoformat(),
        "signature": cert_sig.short_signature(stored_sig) if stored_sig else None,
        "benchmark_source": settings.BENCHMARK_SOURCE_LABEL,
    }
