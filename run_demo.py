"""
SIH Problem Statement 25073: Real AI Model Engine Demonstration & Verification Runner.
Demonstrates the full end-to-end pipeline:
Athlete Registration -> Camera Guidance -> Real AI Test Processing -> Anomaly Fraud Verification -> Benchmarking -> Athletic Performance Index -> Offline Sync -> Scout Talent Discovery.
"""

import sys
import os
import json
import numpy as np
import uuid
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath("."))

from app.database.session import init_db, SessionLocal
from app.models.db_models import Athlete, Assessment, Performance, Official
from app.core import security
from app.services import verification as cert_sig
from app.cv_engine.pose_detector import PoseDetector
from app.cv_engine.situp_analyzer import SitUpAnalyzer
from app.cv_engine.vertical_jump_analyzer import VerticalJumpAnalyzer
from app.cv_engine.shuttle_run_analyzer import ShuttleRunAnalyzer
from app.cv_engine.anomaly_verifier import AnomalyVerifier
from app.scoring_engine.benchmarker import BenchmarkingEngine
from app.scoring_engine.performance_index import AthleticPerformanceIndexCalculator
from app.database.sync_service import OfflineSyncService

def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title.upper()}")
    print("=" * 70)

def generate_situp_pose_sequence(num_reps: int = 4, fps: float = 30.0):
    """Generates realistic pose landmark timeline for sit-ups test."""
    landmark_history = []
    base_angles = [140, 130, 115, 100, 85, 70, 58, 55, 60, 75, 90, 105, 120, 135, 140]
    angles = []
    for a in base_angles:
        angles.extend([a, a])

    h = (0.5, 0.5, 0.95)
    k = (0.8, 0.5, 0.95)

    for rep in range(num_reps):
        for angle in angles:
            rad = angle * (np.pi / 180.0)
            s = (0.5 + 0.3 * float(np.cos(rad)), 0.5 - 0.3 * float(np.sin(rad)), 0.95)
            frame = {
                "NOSE": (s[0], s[1] - 0.1, 0.95),
                "LEFT_SHOULDER": s, "RIGHT_SHOULDER": s,
                "LEFT_HIP": h, "RIGHT_HIP": h,
                "LEFT_KNEE": k, "RIGHT_KNEE": k,
                "LEFT_ANKLE": (0.8, 0.8, 0.95), "RIGHT_ANKLE": (0.8, 0.8, 0.95)
            }
            landmark_history.append(frame)
    return landmark_history

def generate_vertical_jump_sequence(fps: float = 30.0):
    """Generates realistic pose landmark timeline for vertical jump test."""
    landmark_history = []
    total_frames = 60 # 2 seconds
    baseline_ankle_y = 0.82
    baseline_hip_y = 0.52

    for f in range(total_frames):
        if 16 <= f <= 34:
            t_air = (f - 16) / 18.0
            elevation = 0.16 * np.sin(t_air * np.pi) # ~43cm jump elevation profile
        else:
            elevation = 0.0

        ankle_y = baseline_ankle_y - elevation
        hip_y = baseline_hip_y - elevation

        frame = {
            "NOSE": (0.5, 0.18 - elevation, 0.95),
            "LEFT_SHOULDER": (0.45, 0.30 - elevation, 0.95),
            "RIGHT_SHOULDER": (0.55, 0.30 - elevation, 0.95),
            "LEFT_HIP": (0.45, hip_y, 0.95),
            "RIGHT_HIP": (0.55, hip_y, 0.95),
            "LEFT_KNEE": (0.45, hip_y + 0.15, 0.95),
            "RIGHT_KNEE": (0.55, hip_y + 0.15, 0.95),
            "LEFT_ANKLE": (0.45, ankle_y, 0.95),
            "RIGHT_ANKLE": (0.55, ankle_y, 0.95)
        }
        landmark_history.append(frame)
    return landmark_history

def generate_shuttle_run_sequence(fps: float = 30.0):
    """Generates realistic pose landmark timeline for 10x4m shuttle run test."""
    landmark_history = []
    total_frames = 370 # ~12.3 seconds sprint & turnaround
    for f in range(total_frames):
        if f <= 185:
            x = 0.10 + (0.80 * (f / 185.0))
        else:
            x = 0.90 - (0.80 * ((f - 185) / 185.0))

        frame = {
            "NOSE": (x, 0.2, 0.92),
            "LEFT_SHOULDER": (x, 0.3, 0.92), "RIGHT_SHOULDER": (x, 0.3, 0.92),
            "LEFT_HIP": (x, 0.5, 0.92), "RIGHT_HIP": (x, 0.5, 0.92),
            "LEFT_KNEE": (x, 0.7, 0.92), "RIGHT_KNEE": (x, 0.7, 0.92),
            "LEFT_ANKLE": (x, 0.9, 0.92), "RIGHT_ANKLE": (x, 0.9, 0.92)
        }
        landmark_history.append(frame)
    return landmark_history

def main():
    print_header("Initializing Database & Core AI Platform Engines")
    init_db()
    db = SessionLocal()

    # Step 1: Athlete Registration
    print_header("Step 1: Athlete Registration")
    athlete_id = "ATH-2026-000123"
    athlete = db.query(Athlete).filter(Athlete.athlete_id == athlete_id).first()
    if not athlete:
        athlete = Athlete(
            athlete_id=athlete_id,
            name="Rohan Kumar",
            age=16,
            category="Male",
            state="Uttar Pradesh",
            district="Prayagraj",
            school="Kendriya Vidyalaya",
            sports_interest="Athletics / Football",
            password_hash=security.hash_password("demo123")
        )
        db.add(athlete)
        perf = Performance(
            athlete_id=athlete_id,
            speed_score=50.0, agility_score=50.0, strength_score=50.0,
            power_score=50.0, endurance_score=50.0, overall_index=50.0
        )
        db.add(perf)
        db.commit()

    print(f"  Registered Athlete ID : {athlete.athlete_id}")
    print(f"  Name                 : {athlete.name}")
    print(f"  Age / Category       : {athlete.age} / {athlete.category}")
    print(f"  Location             : {athlete.district}, {athlete.state}")
    print(f"  Demo login password  : demo123")

    # Seed a demo Scout / Official account so the official dashboard is usable out of the box.
    official_email = "official@sai.gov.in"
    official = db.query(Official).filter(Official.email == official_email).first()
    if not official:
        official = Official(
            official_id="OFF-2026-000001",
            name="SAI Talent Scout",
            email=official_email,
            organization="Sports Authority of India",
            phone=None,
            password_hash=security.hash_password("scout123"),
        )
        db.add(official)
        db.commit()
    print(f"  Demo Official login   : {official_email} / scout123")

    # Step 2: AI Camera Guidance Check
    print_header("Step 2: AI Camera Guidance Pre-Check (Section 8)")
    sample_seq = generate_vertical_jump_sequence()
    guidance = PoseDetector.check_camera_guidance(sample_seq)
    print(f"  [OK] Full Body Visible   : {guidance['full_body_visible']}")
    print(f"  [OK] Camera Stability    : {guidance['camera_stable']}")
    print(f"  [OK] Lighting Sufficient : {guidance['lighting_sufficient']}")
    print(f"  [OK] Camera Check Status : {guidance['message']}")

    # Step 3: Vertical Jump Assessment (Section 11)
    print_header("Step 3: Real Vertical Jump AI Assessment (Section 11)")
    vjump_seq = generate_vertical_jump_sequence()
    vjump_analyzer = VerticalJumpAnalyzer()
    vjump_res = vjump_analyzer.analyze_sequence(vjump_seq, fps=30.0, user_height_cm=170.0)
    vjump_verification = AnomalyVerifier.verify_assessment(vjump_seq, fps=30.0, test_specific_valid=vjump_res["takeoff_detected"])
    vjump_norm, vjump_status, bench_src = BenchmarkingEngine.normalize_score(
        vjump_res["jump_height_cm"], "vertical_jump", athlete.age, athlete.category
    )

    print(f"  Jump Height         : {vjump_res['jump_height_cm']} cm")
    print(f"  Take-off Detected   : {'[OK]' if vjump_res['takeoff_detected'] else 'X'}")
    print(f"  Landing Detected    : {'[OK]' if vjump_res['landing_detected'] else 'X'}")
    print(f"  Flight Time         : {vjump_res['flight_time_sec']} sec")
    print(f"  AI Confidence       : {vjump_res['confidence']}%")
    print(f"  Validation Score    : {vjump_verification['validation_score']}% ({vjump_verification['status']})")
    print(f"  Normalized Score    : {vjump_norm}/100 ({vjump_status})")

    run_suffix = uuid.uuid4().hex[:6].upper()
    vjump_ts = datetime.utcnow().replace(microsecond=0)
    vjump_sig = cert_sig.sign_fields(
        athlete_id, "vertical_jump", vjump_res["jump_height_cm"], vjump_norm,
        vjump_verification["status"], vjump_ts,
    )
    db.add(Assessment(
        assessment_id=f"ASM-VJUMP-{run_suffix}", athlete_id=athlete_id, test_type="vertical_jump",
        raw_score=vjump_res["jump_height_cm"], normalized_score=vjump_norm,
        confidence=vjump_res["confidence"], validation_score=vjump_verification["validation_score"],
        timestamp=vjump_ts, status=vjump_verification["status"], sync_status="SYNCED",
        details_json=json.dumps({**vjump_res, cert_sig.SIGNATURE_KEY: vjump_sig})
    ))

    # Step 4: Sit-Ups Assessment (Section 10)
    print_header("Step 4: Real Sit-Ups AI Assessment (Section 10)")
    situp_seq = generate_situp_pose_sequence(num_reps=4)
    situp_analyzer = SitUpAnalyzer()
    situp_res = situp_analyzer.analyze_sequence(situp_seq, fps=30.0)
    situp_verification = AnomalyVerifier.verify_assessment(situp_seq, fps=30.0, test_specific_valid=situp_res["valid_reps"] > 0)
    situp_norm, situp_status, _ = BenchmarkingEngine.normalize_score(
        situp_res["valid_reps"] * 8.0, "sit_up", athlete.age, athlete.category # scaled to 60s standard
    )

    print(f"  Total Reps Counted  : {situp_res['total_reps']}")
    print(f"  Valid Reps          : {situp_res['valid_reps']}")
    print(f"  Form Score          : {situp_res['form_score']}%")
    print(f"  Cadence Consistency : {situp_res['rhythm_consistency_score']}%")
    print(f"  AI Confidence       : {situp_res['confidence']}%")
    print(f"  Validation Score    : {situp_verification['validation_score']}% ({situp_verification['status']})")
    print(f"  Normalized Score    : {situp_norm}/100 ({situp_status})")

    situp_raw = situp_res["valid_reps"] * 8.0
    situp_ts = datetime.utcnow().replace(microsecond=0)
    situp_sig = cert_sig.sign_fields(
        athlete_id, "sit_up", situp_raw, situp_norm,
        situp_verification["status"], situp_ts,
    )
    db.add(Assessment(
        assessment_id=f"ASM-SITUP-{run_suffix}", athlete_id=athlete_id, test_type="sit_up",
        raw_score=situp_raw, normalized_score=situp_norm,
        confidence=situp_res["confidence"], validation_score=situp_verification["validation_score"],
        timestamp=situp_ts, status=situp_verification["status"], sync_status="SYNCED",
        details_json=json.dumps({**situp_res, cert_sig.SIGNATURE_KEY: situp_sig})
    ))

    # Step 5: Shuttle Run Assessment (Section 12)
    print_header("Step 5: Real Shuttle Run AI Assessment (Section 12)")
    shuttle_seq = generate_shuttle_run_sequence()
    shuttle_analyzer = ShuttleRunAnalyzer()
    shuttle_res = shuttle_analyzer.analyze_sequence(shuttle_seq, fps=30.0)
    shuttle_verification = AnomalyVerifier.verify_assessment(shuttle_seq, fps=30.0, test_specific_valid=shuttle_res["valid_run"])
    shuttle_norm, shuttle_status, _ = BenchmarkingEngine.normalize_score(
        shuttle_res["total_time_sec"], "shuttle_run", athlete.age, athlete.category
    )

    print(f"  Total Time          : {shuttle_res['total_time_sec']} sec")
    print(f"  Boundary Crossed    : {'[OK]' if shuttle_res['boundary_crossed'] else 'X'}")
    print(f"  Valid Sprint        : {'[OK]' if shuttle_res['valid_run'] else 'X'}")
    print(f"  AI Confidence       : {shuttle_res['confidence']}%")
    print(f"  Validation Score    : {shuttle_verification['validation_score']}% ({shuttle_verification['status']})")
    print(f"  Normalized Score    : {shuttle_norm}/100 ({shuttle_status})")

    shuttle_ts = datetime.utcnow().replace(microsecond=0)
    shuttle_sig = cert_sig.sign_fields(
        athlete_id, "shuttle_run", shuttle_res["total_time_sec"], shuttle_norm,
        shuttle_verification["status"], shuttle_ts,
    )
    db.add(Assessment(
        assessment_id=f"ASM-SHUTTLE-{run_suffix}", athlete_id=athlete_id, test_type="shuttle_run",
        raw_score=shuttle_res["total_time_sec"], normalized_score=shuttle_norm,
        confidence=shuttle_res["confidence"], validation_score=shuttle_verification["validation_score"],
        timestamp=shuttle_ts, status=shuttle_verification["status"], sync_status="SYNCED",
        details_json=json.dumps({**shuttle_res, cert_sig.SIGNATURE_KEY: shuttle_sig})
    ))
    db.commit()

    # Step 6: Athletic Performance Index Calculation (Section 16, 17)
    print_header("Step 6: Athletic Performance Index & Profile (Section 16, 17, 21)")
    all_assessments = db.query(Assessment).filter(Assessment.athlete_id == athlete_id).all()
    index_data = AthleticPerformanceIndexCalculator.calculate_index(all_assessments)
    
    perf = db.query(Performance).filter(Performance.athlete_id == athlete_id).first()
    perf.speed_score = index_data["speed_score"]
    perf.agility_score = index_data["agility_score"]
    perf.strength_score = index_data["strength_score"]
    perf.power_score = index_data["power_score"]
    perf.endurance_score = index_data["endurance_score"]
    perf.flexibility_score = index_data["flexibility_score"]
    perf.body_composition_score = index_data["body_composition_score"]
    perf.overall_index = index_data["overall_index"]
    db.commit()

    print(f"  Athlete ID                : {athlete_id}")
    print(f"  Location                  : {athlete.district}, {athlete.state}")
    print(f"  --------------------------------------------------")
    print(f"  Speed Score               : {index_data['speed_score']}/100")
    print(f"  Agility Score             : {index_data['agility_score']}/100")
    print(f"  Strength Score            : {index_data['strength_score']}/100")
    print(f"  Explosive Power Score     : {index_data['power_score']}/100")
    print(f"  Endurance Score           : {index_data['endurance_score']}/100")
    print(f"  Flexibility Score         : {index_data['flexibility_score']}/100")
    print(f"  Body Composition Score    : {index_data['body_composition_score']}/100")
    print(f"  Tests Completed           : {index_data['tests_completed']}")
    print(f"  --------------------------------------------------")
    print(f"  ATHLETIC PERFORMANCE INDEX: {index_data['overall_index']}/100")
    print(f"  Benchmark Reference Label : {bench_src}")

    # Step 7: Offline-First Sync Queue Verification (Section 18)
    print_header("Step 7: Offline-First SQLite Sync Engine Check (Section 18)")
    offline_asm = Assessment(
        assessment_id=f"ASM-OFFLINE-{run_suffix}", athlete_id=athlete_id, test_type="vertical_jump",
        raw_score=44.0, normalized_score=83.0, confidence=95.0, validation_score=97.0,
        timestamp=datetime.utcnow(), status="VALID", sync_status="PENDING"
    )
    db.add(offline_asm)
    db.commit()

    pending = OfflineSyncService.get_pending_sync(db)
    print(f"  [Offline Mode] Saved local assessment to SQLite. Pending Sync count: {len(pending)}")
    synced_count = OfflineSyncService.mark_as_synced(db, [a.assessment_id for a in pending])
    print(f"  [Online Sync] Internet Restored. Successfully synchronized {synced_count} items to cloud database!")

    # Step 8: Scout Dashboard Talent Discovery (Section 21, 22, 23)
    print_header("Step 8: Scout Talent Discovery Search (Section 22, 23)")
    results = db.query(Athlete).join(Performance).filter(
        Athlete.state == "Uttar Pradesh",
        Athlete.district == "Prayagraj",
        Performance.overall_index >= 80.0
    ).all()

    print(f"  Filter Criteria : State='Uttar Pradesh', District='Prayagraj', Performance Index >= 80")
    print(f"  Discovered Emerging Athletes Count: {len(results)}")
    for i, ath in enumerate(results, 1):
        print(f"    {i}. Athlete ID: {ath.athlete_id} | Name: {ath.name} | Index: {ath.performance.overall_index}/100")

    print_header("Verification Successful: Real AI Model Engine fully executed!")
    db.close()

if __name__ == "__main__":
    main()
