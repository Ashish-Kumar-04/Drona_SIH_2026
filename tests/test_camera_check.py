"""
Tests for the live-capture camera alignment guidance (Feature 1).

Two layers:
  * Unit tests for `PoseDetector.check_camera_guidance(...)` geometry — driven by synthetic
    landmark frames, so they need NO MediaPipe model (fast + deterministic). They cover
    full-body visibility, centering, distance (too far / clipped), per-test orientation, the
    prioritized instruction, the 0-100 alignment score, and backward compatibility.
  * Integration tests for `POST /assessment/camera-check` — auth is required, the CV-unavailable
    path returns a clean fallback, and a decoded frame with no detectable pose returns a
    well-formed "no athlete" payload (fake detector, so no model download).
"""

import random

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.api.main import app
from app.cv_engine.pose_detector import PoseDetector
from app.database.session import Base, engine
from app.services.rate_limit import reset_all

client = TestClient(app)


def setup_module(module):
    Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    reset_all()
    yield
    reset_all()


# ─────────────────────────── Synthetic pose helpers ───────────────────────────
def _good_pose(cx=0.5, top=0.10, bottom=0.90, shoulder_half=0.10, vis=0.95):
    """
    A well-framed, front-on, full-body pose centred at cx spanning [top, bottom] vertically.
    shoulder_half is half the shoulder width (0.10 ⇒ front-on; ~0.02 ⇒ side-on).
    """
    mid = (top + bottom) / 2.0
    return {
        "NOSE": (cx, top, vis),
        "LEFT_SHOULDER": (cx - shoulder_half, top + 0.15, vis),
        "RIGHT_SHOULDER": (cx + shoulder_half, top + 0.15, vis),
        "LEFT_HIP": (cx - 0.05, mid, vis),
        "RIGHT_HIP": (cx + 0.05, mid, vis),
        "LEFT_KNEE": (cx - 0.05, mid + 0.17, vis),
        "RIGHT_KNEE": (cx + 0.05, mid + 0.17, vis),
        "LEFT_ANKLE": (cx - 0.05, bottom, vis),
        "RIGHT_ANKLE": (cx + 0.05, bottom, vis),
    }


# ─────────────────────────── Unit: geometry ───────────────────────────
def test_good_pose_is_ready():
    g = PoseDetector.check_camera_guidance([_good_pose()], test_type="vertical_jump")
    assert g["full_body_visible"] is True
    assert g["centered"] is True
    assert g["distance_ok"] is True
    assert g["orientation_ok"] is True
    assert g["ready"] is True
    assert g["alignment_score"] == 100
    assert "Perfect" in g["instruction"]


def test_off_center_pose_flags_direction():
    g = PoseDetector.check_camera_guidance([_good_pose(cx=0.82)], test_type="vertical_jump")
    assert g["centered"] is False
    assert g["ready"] is False
    assert "right" in g["instruction"].lower()
    assert g["off_center_x"] > 0.15


def test_too_far_pose_asks_to_move_closer():
    # Small vertical span ⇒ athlete looks tiny in frame.
    g = PoseDetector.check_camera_guidance([_good_pose(top=0.42, bottom=0.58)],
                                           test_type="vertical_jump")
    assert g["distance_ok"] is False
    assert "closer" in g["instruction"].lower()


def test_clipped_pose_asks_to_step_back():
    # Ankles below the bottom edge ⇒ body is cut off ⇒ step back.
    g = PoseDetector.check_camera_guidance([_good_pose(top=0.10, bottom=0.985)],
                                           test_type="vertical_jump")
    assert g["distance_ok"] is False
    assert "step back" in g["instruction"].lower()


def test_missing_lower_body_not_full_body_visible():
    pose = _good_pose()
    # Drop the ankles' visibility (feet out of frame).
    pose["LEFT_ANKLE"] = (0.45, 0.9, 0.1)
    pose["RIGHT_ANKLE"] = (0.55, 0.9, 0.1)
    g = PoseDetector.check_camera_guidance([pose], test_type="vertical_jump")
    assert g["full_body_visible"] is False
    assert "whole body" in g["instruction"].lower()


def test_orientation_enforced_per_test():
    # A front-on pose (wide shoulders) is wrong for a sit-up (needs a side view).
    front = _good_pose(shoulder_half=0.12)
    g = PoseDetector.check_camera_guidance([front], test_type="sit_up")
    assert g["orientation"] == "front"
    assert g["orientation_ok"] is False
    assert "side-on" in g["instruction"].lower()

    # The same front-on pose is fine for a vertical jump (needs front).
    g2 = PoseDetector.check_camera_guidance([front], test_type="vertical_jump")
    assert g2["orientation_ok"] is True


def test_shuttle_does_not_enforce_orientation():
    front = _good_pose(shoulder_half=0.12)
    g = PoseDetector.check_camera_guidance([front], test_type="shuttle_run")
    assert g["orientation_ok"] is True


def test_empty_history_reports_no_athlete():
    g = PoseDetector.check_camera_guidance([], test_type="vertical_jump")
    assert g["ready"] is False
    assert g["alignment_score"] == 0
    assert "no athlete" in g["instruction"].lower()


def test_backward_compatible_without_test_type():
    # Original callers pass no test_type; old keys must still be present and orientation not enforced.
    g = PoseDetector.check_camera_guidance([_good_pose(shoulder_half=0.02)])
    for key in ("ready", "full_body_visible", "camera_stable", "lighting_sufficient",
                "athlete_positioned", "message"):
        assert key in g
    assert g["orientation_ok"] is True  # "any" when no test_type


# ─────────────────────────── Integration: endpoint ───────────────────────────
def _jpeg_bytes():
    ok, buf = cv2.imencode(".jpg", np.zeros((120, 160, 3), dtype=np.uint8))
    assert ok
    return buf.tobytes()


def _register_athlete():
    suffix = str(random.randint(1000000, 9999999))
    payload = {
        "name": "Camera Athlete", "age": 16, "category": "Male",
        "state": "Karnataka", "district": "Mysuru",
        "phone": f"95{suffix}", "email": f"cam{suffix}@example.com",
        "password": "pass1234",
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201, res.text
    return res.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_camera_check_requires_auth():
    res = client.post("/api/v1/assessment/camera-check",
                      files={"file": ("frame.jpg", _jpeg_bytes(), "image/jpeg")},
                      data={"test_type": "sit_up"})
    assert res.status_code == 401


def test_camera_check_cv_unavailable_fallback(monkeypatch):
    monkeypatch.setattr(routes, "HAS_CV2_MP", False)
    token = _register_athlete()
    res = client.post("/api/v1/assessment/camera-check",
                      files={"file": ("frame.jpg", _jpeg_bytes(), "image/jpeg")},
                      data={"test_type": "sit_up"},
                      headers=_auth(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["cv_available"] is False
    assert body["ready"] is False
    assert body["alignment_score"] == 0
    assert body["instruction"]


def test_camera_check_no_pose_detected(monkeypatch):
    """CV available + decodable frame but no pose found ⇒ clean 'no athlete' payload."""
    class _FakeDetector:
        def process_frame(self, frame):
            return None

    monkeypatch.setattr(routes, "HAS_CV2_MP", True)
    monkeypatch.setattr(routes, "_CAMERA_CHECK_DETECTOR", _FakeDetector())
    token = _register_athlete()
    res = client.post("/api/v1/assessment/camera-check",
                      files={"file": ("frame.jpg", _jpeg_bytes(), "image/jpeg")},
                      data={"test_type": "vertical_jump"},
                      headers=_auth(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["cv_available"] is True
    assert body["ready"] is False
    assert "no athlete" in body["instruction"].lower()


def test_camera_check_reports_guidance_for_detected_pose(monkeypatch):
    """CV available + a good detected pose ⇒ full-body visible, scored guidance."""
    class _FakeDetector:
        def process_frame(self, frame):
            return _good_pose()

    monkeypatch.setattr(routes, "HAS_CV2_MP", True)
    monkeypatch.setattr(routes, "_CAMERA_CHECK_DETECTOR", _FakeDetector())
    token = _register_athlete()
    res = client.post("/api/v1/assessment/camera-check",
                      files={"file": ("frame.jpg", _jpeg_bytes(), "image/jpeg")},
                      data={"test_type": "vertical_jump"},
                      headers=_auth(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["cv_available"] is True
    assert body["full_body_visible"] is True
    assert body["centered"] is True
    # A black frame fails only the lighting check, so the score stays high.
    assert body["alignment_score"] >= 80
