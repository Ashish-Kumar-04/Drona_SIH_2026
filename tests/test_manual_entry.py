"""
Integration tests for the manual / assisted result-entry endpoint.

POST /api/v1/assessment/manual-entry records tests that cannot be reliably measured by CV
from a single phone clip (50m dash, 600m run, sit & reach) or from a tape (broad jump).
It must: normalize & store a plausible value, reject CV-only tests, reject out-of-range
values, reject unknown tests, and require authentication.
"""

import random
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
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


def _rand():
    return str(random.randint(1000000, 9999999))


def _register_athlete(age=16, category="Male"):
    suffix = _rand()
    payload = {
        "name": "Manual Athlete", "age": age, "category": category,
        "state": "Karnataka", "district": "Mysuru",
        "phone": f"97{suffix}", "email": f"manual{suffix}@example.com",
        "password": "pass1234",
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201, res.text
    body = res.json()
    return body["athlete"]["athlete_id"], body["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _entry(athlete_id, test_type, raw_value, officiated=False, notes=None):
    return {
        "athlete_id": athlete_id, "test_type": test_type,
        "raw_value": raw_value, "officiated": officiated, "notes": notes,
    }


# ─── Happy path ───
def test_manual_entry_accepts_and_scores_sprint():
    a_id, token = _register_athlete()
    res = client.post("/api/v1/assessment/manual-entry",
                      json=_entry(a_id, "sprint_50m", 7.0, officiated=True),
                      headers=_auth(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["test_type"] == "sprint_50m"
    assert body["unit"] == "sec"
    assert body["status"] == "VALID"
    assert 1.0 <= body["normalized_score"] <= 99.0
    assert body["normalized_score"] > 50.0            # 7.0s @16M is above average
    assert body["validation_score"] == 90.0           # officiated
    assert "Prototype" in body["benchmark_source"]
    assert body["details"]["entry_mode"] == "manual"
    assert body["details"]["officiated"] is True


def test_manual_entry_self_reported_scores_lower_confidence():
    a_id, token = _register_athlete()
    res = client.post("/api/v1/assessment/manual-entry",
                      json=_entry(a_id, "sit_and_reach", 12.0, officiated=False),
                      headers=_auth(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["validation_score"] == 75.0           # self-reported
    assert body["details"]["officiated"] is False


def test_manual_entry_folds_into_performance_index():
    a_id, token = _register_athlete()
    client.post("/api/v1/assessment/manual-entry",
                json=_entry(a_id, "sprint_50m", 6.8, officiated=True),
                headers=_auth(token))
    # Speed comes exclusively from sprint_50m; after entry it must leave the 50.0 placeholder.
    prof = client.get(f"/api/v1/athlete/profile/{a_id}", headers=_auth(token))
    assert prof.status_code == 200, prof.text
    perf = prof.json()["performance"]
    assert perf["speed_score"] != 50.0
    assert perf["tests_completed"] >= 1


# ─── Rejections ───
def test_manual_entry_rejects_cv_test():
    a_id, token = _register_athlete()
    # sit_up is a CV test with no manual fallback -> must be pushed to the video endpoints.
    res = client.post("/api/v1/assessment/manual-entry",
                      json=_entry(a_id, "sit_up", 40.0),
                      headers=_auth(token))
    assert res.status_code == 400, res.text
    assert "cv" in res.json()["detail"].lower()


def test_manual_entry_rejects_out_of_bounds():
    a_id, token = _register_athlete()
    # 2.0s for a 50m dash is physically impossible (plausible_min is 5.0s).
    res = client.post("/api/v1/assessment/manual-entry",
                      json=_entry(a_id, "sprint_50m", 2.0),
                      headers=_auth(token))
    assert res.status_code == 400, res.text
    assert "plausible" in res.json()["detail"].lower()


def test_manual_entry_rejects_unknown_test():
    a_id, token = _register_athlete()
    res = client.post("/api/v1/assessment/manual-entry",
                      json=_entry(a_id, "not_a_real_test", 10.0),
                      headers=_auth(token))
    assert res.status_code == 400, res.text


def test_manual_entry_allows_broad_jump_fallback():
    # broad_jump is CV-first but carries a tape-measured manual fallback.
    a_id, token = _register_athlete()
    res = client.post("/api/v1/assessment/manual-entry",
                      json=_entry(a_id, "broad_jump", 200.0, officiated=True),
                      headers=_auth(token))
    assert res.status_code == 200, res.text
    assert res.json()["test_type"] == "broad_jump"


def test_manual_entry_requires_auth():
    a_id, _token = _register_athlete()
    res = client.post("/api/v1/assessment/manual-entry",
                      json=_entry(a_id, "sprint_50m", 7.0))
    assert res.status_code == 401
