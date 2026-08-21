"""
REST API Endpoint Routes for Athlete, Assessment, Sync, and Scout Talent Discovery.
Implements Sections 19, 21, and 22 of SIH 25073 specification.
"""

import uuid
import json
import os
import hashlib
import random
import tempfile
import cv2
import numpy as np
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database.session import get_db
from app.models.db_models import Athlete, Assessment, Performance, OTPReset
from app.models.schemas import (
    AthleteRegister, AthleteLogin, AthleteResponse, VideoAssessmentRequest, AssessmentResponse,
    PerformanceResponse, AthleteProfileResponse, SyncAssessmentItem, ScoutSearchRequest,
    OTPRequestSchema, OTPVerifySchema
)
from app.cv_engine.situp_analyzer import SitUpAnalyzer
from app.cv_engine.vertical_jump_analyzer import VerticalJumpAnalyzer
from app.cv_engine.shuttle_run_analyzer import ShuttleRunAnalyzer
from app.cv_engine.anomaly_verifier import AnomalyVerifier
from app.cv_engine.pose_detector import PoseDetector
from app.scoring_engine.benchmarker import BenchmarkingEngine
from app.scoring_engine.performance_index import AthleticPerformanceIndexCalculator
from app.database.sync_service import OfflineSyncService

router = APIRouter()

def _hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

@router.post("/auth/register", response_model=AthleteResponse, status_code=status.HTTP_201_CREATED)
def register_athlete(req: AthleteRegister, db: Session = Depends(get_db)):
    """Register a new athlete and issue unique Athlete ID (e.g. ATH-2026-000123)."""
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
        password_hash=_hash_password(req.password)
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
    return athlete

@router.post("/auth/login", response_model=AthleteResponse)
def login_athlete(req: AthleteLogin, db: Session = Depends(get_db)):
    """Login an existing athlete by Athlete ID and password."""
    athlete = db.query(Athlete).filter(Athlete.athlete_id == req.athlete_id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="No athlete found with this ID. Please check your Athlete ID.")
    if athlete.password_hash != _hash_password(req.password):
        raise HTTPException(status_code=401, detail="Incorrect password. Please try again or reset your password.")
    return athlete

@router.post("/auth/request-otp")
def request_password_reset_otp(req: OTPRequestSchema, db: Session = Depends(get_db)):
    """Generate a 6-digit OTP for password reset. In production, this sends via SMS/Email."""
    athlete = db.query(Athlete).filter(Athlete.athlete_id == req.athlete_id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="No athlete found with this ID.")
    
    otp_code = str(random.randint(100000, 999999))
    
    otp_record = OTPReset(
        athlete_id=req.athlete_id,
        otp_code=otp_code,
        created_at=datetime.utcnow(),
        used=0
    )
    db.add(otp_record)
    db.commit()
    
    # In production: send OTP via SMS/email to athlete.phone or athlete.email
    # For prototype: return OTP directly so the frontend can display it
    return {
        "message": "OTP sent successfully.",
        "athlete_id": req.athlete_id,
        "otp": otp_code,  # PROTOTYPE ONLY — remove in production
        "contact": athlete.phone or athlete.email or "No contact on file",
        "expires_in_minutes": 10
    }

@router.post("/auth/reset-password")
def verify_otp_and_reset_password(req: OTPVerifySchema, db: Session = Depends(get_db)):
    """Verify OTP and reset athlete password."""
    athlete = db.query(Athlete).filter(Athlete.athlete_id == req.athlete_id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="No athlete found with this ID.")
    
    # Find the most recent unused OTP for this athlete
    otp_record = (
        db.query(OTPReset)
        .filter(OTPReset.athlete_id == req.athlete_id, OTPReset.used == 0)
        .order_by(OTPReset.created_at.desc())
        .first()
    )
    
    if not otp_record:
        raise HTTPException(status_code=400, detail="No active OTP found. Please request a new one.")
    
    # Check expiry (10 minutes)
    if datetime.utcnow() - otp_record.created_at > timedelta(minutes=10):
        otp_record.used = 1
        db.commit()
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")
    
    if otp_record.otp_code != req.otp_code:
        raise HTTPException(status_code=400, detail="Invalid OTP. Please check and try again.")
    
    # Mark OTP as used and update password
    otp_record.used = 1
    athlete.password_hash = _hash_password(req.new_password)
    db.commit()
    
    return {"message": "Password reset successful. You can now login with your new password."}

@router.get("/athlete/profile/{athlete_id}", response_model=AthleteProfileResponse)
def get_athlete_profile(athlete_id: str, db: Session = Depends(get_db)):
    """Fetch complete Athlete Profile including Performance Index and Recent Assessments."""
    athlete = db.query(Athlete).filter(Athlete.athlete_id == athlete_id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

    perf = db.query(Performance).filter(Performance.athlete_id == athlete_id).first()
    assessments = db.query(Assessment).filter(Assessment.athlete_id == athlete_id).order_by(Assessment.timestamp.desc()).all()

    assessment_responses = []
    for a in assessments:
        unit = "reps" if a.test_type == "sit_up" else "cm" if a.test_type == "vertical_jump" else "sec"
        bench_score, bench_status, bench_src = BenchmarkingEngine.normalize_score(
            a.raw_score, a.test_type, athlete.age, athlete.category
        )
        
        details = json.loads(a.details_json) if a.details_json else {}

        assessment_responses.append(AssessmentResponse(
            assessment_id=a.assessment_id,
            athlete_id=a.athlete_id,
            test_type=a.test_type,
            raw_score=a.raw_score,
            unit=unit,
            normalized_score=a.normalized_score,
            confidence=a.confidence,
            validation_score=a.validation_score,
            status=a.status,
            benchmark_status=bench_status,
            benchmark_source=bench_src,
            timestamp=a.timestamp,
            details=details
        ))

    perf_response = PerformanceResponse.from_orm(perf) if perf else None

    return AthleteProfileResponse(
        athlete=AthleteResponse.from_orm(athlete),
        performance=perf_response,
        recent_assessments=assessment_responses
    )

@router.post("/assessment/process-video", response_model=AssessmentResponse)
def process_assessment_video(req: VideoAssessmentRequest, db: Session = Depends(get_db)):
    """
    Process video landmark frames through the Real AI CV & Anomaly Verification Engines.
    Computes real reps/jump height/shuttle time, verifies authenticity, normalizes scores, and updates Athletic Performance Index.
    """
    athlete = db.query(Athlete).filter(Athlete.athlete_id == req.athlete_id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

    # Convert schema landmark frames to internal analyzer landmark format
    landmark_history = []
    for frame in req.frames:
        frame_dict = {}
        for name, kp in frame.landmarks.items():
            frame_dict[name] = (kp.x, kp.y, kp.visibility)
        landmark_history.append(frame_dict)

    # 1. Execute Test-Specific AI Model Engine
    if req.test_type == "sit_up":
        analyzer = SitUpAnalyzer()
        results = analyzer.analyze_sequence(landmark_history, fps=req.fps)
        raw_score = float(results["valid_reps"])
        unit = "reps"
        test_valid = results["valid_reps"] >= 1 or results["total_reps"] >= 1
    elif req.test_type == "vertical_jump":
        analyzer = VerticalJumpAnalyzer()
        results = analyzer.analyze_sequence(landmark_history, fps=req.fps, user_height_cm=req.reference_height_cm)
        raw_score = float(results["jump_height_cm"])
        unit = "cm"
        test_valid = results["takeoff_detected"] and results["landing_detected"]
    elif req.test_type == "shuttle_run":
        analyzer = ShuttleRunAnalyzer()
        results = analyzer.analyze_sequence(landmark_history, fps=req.fps)
        raw_score = float(results["total_time_sec"])
        unit = "sec"
        test_valid = results["valid_run"]
    else:
        raise HTTPException(status_code=400, detail="Invalid test_type. Must be sit_up, vertical_jump, or shuttle_run.")

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

    # 4. Save Assessment Record
    assessment = Assessment(
        assessment_id=assessment_id,
        athlete_id=req.athlete_id,
        test_type=req.test_type,
        raw_score=raw_score,
        normalized_score=normalized_score,
        confidence=confidence,
        validation_score=validation_score,
        timestamp=datetime.utcnow(),
        status=assessment_status,
        sync_status="SYNCED",
        details_json=json.dumps({**results, "verification": verification})
    )
    db.add(assessment)
    db.commit()

    # 5. Update Athlete Performance Index Record
    all_assessments = db.query(Assessment).filter(Assessment.athlete_id == req.athlete_id).all()
    index_data = AthleticPerformanceIndexCalculator.calculate_index(all_assessments)
    
    perf = db.query(Performance).filter(Performance.athlete_id == req.athlete_id).first()
    if perf:
        perf.speed_score = index_data["speed_score"]
        perf.agility_score = index_data["agility_score"]
        perf.strength_score = index_data["strength_score"]
        perf.power_score = index_data["power_score"]
        perf.endurance_score = index_data["endurance_score"]
        perf.overall_index = index_data["overall_index"]
        db.commit()

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
        details=results
    )

@router.post("/assessment/sync")
def sync_offline_assessments(items: List[SyncAssessmentItem], db: Session = Depends(get_db)):
    """Offline Synchronization API Endpoint (Section 18)."""
    items_dict = [item.dict() for item in items]
    result = OfflineSyncService.sync_incoming_assessments(db, items_dict)
    return result

@router.post("/assessment/upload-video")
async def upload_assessment_video(
    file: UploadFile = File(...),
    athlete_id: str = Form(...),
    test_type: str = Form(...),
    reference_height_cm: Optional[float] = Form(170.0),
    db: Session = Depends(get_db)
):
    """
    Accepts real video upload (.mp4, .webm, .mov), extracts frames with OpenCV,
    processes with MediaPipe Pose Deep Learning Model, executes biomechanical analyzers,
    performs anti-cheat verification, and records scores.
    """
    athlete = db.query(Athlete).filter(Athlete.athlete_id == athlete_id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

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

    # 1. Execute Test-Specific AI Model Engine
    if test_type == "sit_up":
        analyzer = SitUpAnalyzer()
        results = analyzer.analyze_sequence(landmark_history, fps=fps)
        raw_score = float(results["valid_reps"])
        unit = "reps"
        test_valid = results["valid_reps"] >= 1 or results["total_reps"] >= 1
    elif test_type == "vertical_jump":
        analyzer = VerticalJumpAnalyzer(reference_athlete_height_cm=reference_height_cm or 170.0)
        results = analyzer.analyze_sequence(landmark_history, fps=fps, user_height_cm=reference_height_cm)
        raw_score = float(results["jump_height_cm"])
        unit = "cm"
        test_valid = results["takeoff_detected"] and results["landing_detected"]
    elif test_type == "shuttle_run":
        analyzer = ShuttleRunAnalyzer()
        results = analyzer.analyze_sequence(landmark_history, fps=fps)
        raw_score = float(results["total_time_sec"])
        unit = "sec"
        test_valid = results["valid_run"]
    else:
        raise HTTPException(status_code=400, detail="Invalid test_type. Must be sit_up, vertical_jump, or shuttle_run.")

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

    # 4. Save Assessment Record
    assessment = Assessment(
        assessment_id=assessment_id,
        athlete_id=athlete_id,
        test_type=test_type,
        raw_score=raw_score,
        normalized_score=normalized_score,
        confidence=confidence,
        validation_score=validation_score,
        timestamp=datetime.utcnow(),
        status=assessment_status,
        sync_status="SYNCED",
        details_json=json.dumps({**results, "verification": verification})
    )
    db.add(assessment)
    db.commit()

    # 5. Update Athlete Performance Index Record
    all_assessments = db.query(Assessment).filter(Assessment.athlete_id == athlete_id).all()
    index_data = AthleticPerformanceIndexCalculator.calculate_index(all_assessments)
    
    perf = db.query(Performance).filter(Performance.athlete_id == athlete_id).first()
    if perf:
        perf.speed_score = index_data["speed_score"]
        perf.agility_score = index_data["agility_score"]
        perf.strength_score = index_data["strength_score"]
        perf.power_score = index_data["power_score"]
        perf.endurance_score = index_data["endurance_score"]
        perf.overall_index = index_data["overall_index"]
        db.commit()

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
        "verification": verification,
        "frames_summary": {
            "total_frames_processed": frame_idx,
            "pose_frames_detected": len(landmark_history),
            "fps": fps
        },
        "frames_landmarks": frames_data[:300] # return sample keypoint frames for frontend animation
    }

@router.get("/scout/search", response_model=List[AthleteProfileResponse])
def search_scout_talent(
    state: Optional[str] = None,
    district: Optional[str] = None,
    min_overall_index: Optional[float] = None,
    test_type: Optional[str] = None,
    db: Session = Depends(get_db)
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

        assessment_responses = [
            AssessmentResponse(
                assessment_id=a.assessment_id,
                athlete_id=a.athlete_id,
                test_type=a.test_type,
                raw_score=a.raw_score,
                unit="reps" if a.test_type == "sit_up" else "cm" if a.test_type == "vertical_jump" else "sec",
                normalized_score=a.normalized_score,
                confidence=a.confidence,
                validation_score=a.validation_score,
                status=a.status,
                benchmark_status="Above Benchmark" if a.normalized_score >= 70 else "Average",
                benchmark_source="Prototype / Research Benchmark",
                timestamp=a.timestamp,
                details=json.loads(a.details_json) if a.details_json else {}
            ) for a in assessments
        ]

        results.append(AthleteProfileResponse(
            athlete=AthleteResponse.from_orm(athlete),
            performance=PerformanceResponse.from_orm(perf) if perf else None,
            recent_assessments=assessment_responses
        ))

    return results
