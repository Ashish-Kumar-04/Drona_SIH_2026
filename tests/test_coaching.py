"""
Tests for the corrective coaching feedback engine (Feature 2).

Two layers:
  * Unit tests for the pure `generate_feedback(...)` — per-test fault rules (sit-up ROM /
    incomplete reps, jump take-off/landing, shuttle boundary), the two-sided BMI band, the
    norm-based training-tip layer for manual tests, capture-quality flags, and the guarantee
    that it always returns a well-formed dict.
  * Integration tests proving the feedback rides real API responses (manual-entry capture) and
    is injected on the fly for historical assessment rows that predate the feature.
"""

import random
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.database.session import Base, engine, SessionLocal
from app.models.db_models import Assessment
from app.scoring_engine.coaching import generate_feedback
from app.services.rate_limit import reset_all

client = TestClient(app)

_KEYS = {"summary", "score_band", "faults", "improvements", "strengths"}


def setup_module(module):
    Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    reset_all()
    yield
    reset_all()


def _assert_wellformed(fb):
    assert _KEYS.issubset(fb.keys())
    assert isinstance(fb["summary"], str) and fb["summary"]
    assert isinstance(fb["score_band"], str) and fb["score_band"]
    assert isinstance(fb["faults"], list)
    assert isinstance(fb["improvements"], list)
    assert isinstance(fb["strengths"], list)
    for f in fb["faults"]:
        assert set(f.keys()) == {"issue", "severity"}


def _issues(fb):
    return " ".join(f["issue"].lower() for f in fb["faults"])


def _improvements(fb):
    return " ".join(s.lower() for s in fb["improvements"])


# ─────────────────────────── Unit: sit-up ───────────────────────────
def test_situp_shallow_rom_flags_not_coming_up():
    fb = generate_feedback("sit_up", 5.0, 30.0, details={
        "total_reps": 10, "valid_reps": 5, "invalid_reps": 5,
        "form_score": 50.0, "rhythm_consistency_score": 90.0,
        "min_angle_recorded": 110.0, "max_angle_recorded": 140.0,
    }, age=16, category="Male")
    _assert_wellformed(fb)
    assert "sitting up far enough" in _issues(fb)
    assert any(f["severity"] == "high" for f in fb["faults"])
    # Half the reps were incomplete -> that fault too.
    assert "didn't count" in _issues(fb)
    assert fb["improvements"]  # actionable fixes present


def test_situp_incomplete_reps_flagged():
    fb = generate_feedback("sit_up", 6.0, 45.0, details={
        "total_reps": 10, "valid_reps": 6, "invalid_reps": 4,
        "form_score": 60.0, "rhythm_consistency_score": 88.0,
        "min_angle_recorded": 60.0, "max_angle_recorded": 145.0,
    }, age=16, category="Male")
    _assert_wellformed(fb)
    assert "didn't count" in _issues(fb)


def test_situp_good_form_yields_strengths_not_faults():
    fb = generate_feedback("sit_up", 30.0, 88.0, details={
        "total_reps": 20, "valid_reps": 20, "invalid_reps": 0,
        "form_score": 100.0, "rhythm_consistency_score": 92.0,
        "min_angle_recorded": 55.0, "max_angle_recorded": 145.0,
    }, age=16, category="Male")
    _assert_wellformed(fb)
    assert fb["faults"] == []
    assert fb["strengths"]
    assert fb["score_band"] == "Excellent"


# ─────────────────────────── Unit: jumps ───────────────────────────
def test_vertical_jump_missing_takeoff_flagged():
    fb = generate_feedback("vertical_jump", 0.0, 20.0, details={
        "takeoff_detected": False, "landing_detected": True, "flight_time_sec": 0.0,
    }, age=16, category="Male")
    _assert_wellformed(fb)
    assert "take-off" in _issues(fb)


def test_broad_jump_short_flight_gets_power_cue():
    fb = generate_feedback("broad_jump", 150.0, 45.0, details={
        "takeoff_detected": True, "landing_detected": True, "flight_time_sec": 0.25,
    }, age=16, category="Male")
    _assert_wellformed(fb)
    assert "flight time was short" in _issues(fb)
    assert "arm" in _improvements(fb)  # arm-swing / knee-drive cue


# ─────────────────────────── Unit: shuttle ───────────────────────────
def test_shuttle_no_boundary_flagged():
    fb = generate_feedback("shuttle_run", 15.0, 25.0, details={
        "boundary_crossed": False, "valid_run": False, "turnaround_time_sec": 0.0,
    }, age=16, category="Male")
    _assert_wellformed(fb)
    assert "far line" in _issues(fb)


def test_shuttle_slow_turn_flagged():
    fb = generate_feedback("shuttle_run", 13.0, 40.0, details={
        "boundary_crossed": True, "valid_run": True, "turnaround_time_sec": 1.6,
    }, age=16, category="Male")
    _assert_wellformed(fb)
    assert "turn was slow" in _issues(fb)


# ─────────────────────────── Unit: two-sided BMI ───────────────────────────
def test_bmi_below_band_flags_underweight():
    fb = generate_feedback("bmi", 13.0, 30.0, details={}, age=16, category="Male")
    _assert_wellformed(fb)
    assert "below the healthy range" in _issues(fb)


def test_bmi_above_band_flags_overweight():
    fb = generate_feedback("bmi", 30.0, 30.0, details={}, age=16, category="Male")
    _assert_wellformed(fb)
    assert "above the healthy range" in _issues(fb)


def test_bmi_within_band_is_a_strength():
    fb = generate_feedback("bmi", 21.0, 90.0, details={}, age=16, category="Male")
    _assert_wellformed(fb)
    assert fb["faults"] == []
    assert any("healthy range" in s.lower() for s in fb["strengths"])


# ─────────────────────────── Unit: norm layer (manual tests) ───────────────────────────
def test_norm_layer_below_average_gives_training_tip_and_target():
    # sprint_50m has no CV signals; guidance must still come from the norm layer.
    fb = generate_feedback("sprint_50m", 12.0, 15.0, details={}, age=16, category="Male")
    _assert_wellformed(fb)
    assert fb["faults"] == []              # no technique signals for a manual test
    assert fb["improvements"]              # ...but norm-based tips are present
    assert "typical result" in _improvements(fb)
    assert "faster" in _improvements(fb)   # sprint is a "lower-is-better" test


def test_norm_layer_high_score_reinforces():
    fb = generate_feedback("endurance_run", 130.0, 82.0, details={}, age=16, category="Male")
    _assert_wellformed(fb)
    assert fb["strengths"]


# ─────────────────────────── Unit: capture flags + robustness ───────────────────────────
def test_capture_flags_become_a_fault():
    fb = generate_feedback("sit_up", 5.0, 30.0, details={
        "total_reps": 5, "valid_reps": 5, "invalid_reps": 0,
        "min_angle_recorded": 60.0, "max_angle_recorded": 140.0,
        "verification": {"flags": ["ATHLETE_DISAPPEARED_MID_TEST"]},
    }, age=16, category="Male")
    _assert_wellformed(fb)
    assert "wasn't captured" in _issues(fb)


def test_wellformed_for_unknown_test_and_empty_details():
    fb = generate_feedback("mystery_test", 5.0, 50.0)
    _assert_wellformed(fb)
    assert fb["score_band"] == "Average"


def test_no_age_still_wellformed():
    # No age -> no norm lookup; must not raise and must stay well-formed.
    fb = generate_feedback("sit_up", 5.0, 55.0, details={"min_angle_recorded": 120.0})
    _assert_wellformed(fb)
    assert "sitting up far enough" in _issues(fb)


# ─────────────────────────── Integration ───────────────────────────
def _rand():
    return str(random.randint(1000000, 9999999))


def _register_athlete(age=16, category="Male"):
    suffix = _rand()
    payload = {
        "name": "Coaching Athlete", "age": age, "category": category,
        "state": "Karnataka", "district": "Mysuru",
        "phone": f"96{suffix}", "email": f"coach{suffix}@example.com",
        "password": "pass1234",
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201, res.text
    body = res.json()
    return body["athlete"]["athlete_id"], body["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_manual_entry_response_includes_coaching():
    a_id, token = _register_athlete()
    res = client.post("/api/v1/assessment/manual-entry",
                      json={"athlete_id": a_id, "test_type": "sprint_50m",
                            "raw_value": 7.0, "officiated": True, "notes": None},
                      headers=_auth(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["coaching"] is not None
    _assert_wellformed(body["coaching"])
    # It also rides the details channel for older clients.
    assert body["details"]["coaching"]["summary"] == body["coaching"]["summary"]


def test_profile_injects_coaching_for_legacy_row():
    """A historical assessment stored without coaching still shows feedback in the profile."""
    a_id, token = _register_athlete()

    # Insert a legacy-style row directly: details_json has no 'coaching' key.
    asm_id = f"ASM-LEGACY-{uuid.uuid4().hex[:6]}"
    db = SessionLocal()
    try:
        db.add(Assessment(
            assessment_id=asm_id, athlete_id=a_id, test_type="sit_up",
            raw_score=6.0, normalized_score=30.0, confidence=90.0, validation_score=95.0,
            timestamp=datetime.utcnow(), status="VALID", sync_status="SYNCED",
            details_json="{}",
        ))
        db.commit()
    finally:
        db.close()

    prof = client.get(f"/api/v1/athlete/profile/{a_id}", headers=_auth(token))
    assert prof.status_code == 200, prof.text
    rows = {r["assessment_id"]: r for r in prof.json()["recent_assessments"]}
    assert asm_id in rows
    coaching = rows[asm_id]["coaching"]
    assert coaching is not None
    _assert_wellformed(coaching)
    # Below-average sit-up -> norm layer supplies a core-training tip.
    assert coaching["improvements"]
