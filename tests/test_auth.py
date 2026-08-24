"""
Authentication & authorization tests for Move 1 (security hardening + officials).

Covers: bcrypt hashing, legacy SHA-256 verify+rehash flag, JWT round-trip,
official registration/login (enrolment-key gated), scout endpoint gating,
profile self-only access, assessment ownership binding, and rate limiting.
"""

import random
import hashlib

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.database.session import Base, engine
from app.core import security
from app.core.config import settings
from app.services import rate_limit

client = TestClient(app)


def setup_module(module):
    Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    # TestClient shares one client IP; reset the in-memory limiter between tests.
    rate_limit.reset_all()
    yield
    rate_limit.reset_all()


# ─── Helpers ───
def _rand():
    return str(random.randint(1000000, 9999999))


def _register_athlete(password="pass1234", **over):
    suffix = _rand()
    payload = {
        "name": "Auth Test",
        "age": 15,
        "category": "Male",
        "state": "Delhi",
        "district": "New Delhi",
        "phone": f"98{suffix}",
        "email": f"ath{suffix}@example.com",
        "password": password,
    }
    payload.update(over)
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201, res.text
    body = res.json()
    return body["athlete"]["athlete_id"], body["access_token"]


def _register_official(password="scoutpass", key=None):
    suffix = _rand()
    payload = {
        "name": "Scout Test",
        "email": f"off{suffix}@sai.gov.in",
        "organization": "SAI",
        "password": password,
        "signup_key": key if key is not None else settings.OFFICIAL_SIGNUP_KEY,
    }
    res = client.post("/api/v1/auth/official/register", json=payload)
    return res


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ─── Unit: password hashing ───
def test_bcrypt_hash_and_verify():
    h = security.hash_password("secret-pw")
    assert h.startswith("$2")
    ok, needs_rehash = security.verify_password("secret-pw", h)
    assert ok is True
    assert needs_rehash is False
    bad, _ = security.verify_password("wrong-pw", h)
    assert bad is False


def test_legacy_sha256_verifies_and_flags_rehash():
    legacy = hashlib.sha256("legacy-pw".encode("utf-8")).hexdigest()
    ok, needs_rehash = security.verify_password("legacy-pw", legacy)
    assert ok is True
    assert needs_rehash is True  # should be upgraded to bcrypt on next login
    bad, bad_flag = security.verify_password("nope", legacy)
    assert bad is False
    assert bad_flag is False


def test_empty_stored_hash_is_invalid():
    ok, needs = security.verify_password("anything", "")
    assert ok is False and needs is False


# ─── Unit: JWT ───
def test_jwt_roundtrip_and_type_claim():
    token = security.create_access_token("ATH-2026-000999", typ="athlete")
    claims = security.decode_access_token(token)
    assert claims is not None
    assert claims["sub"] == "ATH-2026-000999"
    assert claims["typ"] == "athlete"

    off_token = security.create_access_token("OFF-2026-000999", typ="official")
    assert security.decode_access_token(off_token)["typ"] == "official"

    assert security.decode_access_token("not-a-real-token") is None


# ─── Legacy athlete login upgrades hash to bcrypt ───
def test_login_rehashes_legacy_sha256():
    from app.database.session import SessionLocal
    from app.models.db_models import Athlete, Performance

    suffix = _rand()
    athlete_id = f"ATH-LEGACY-{suffix}"
    db = SessionLocal()
    try:
        db.add(Athlete(
            athlete_id=athlete_id, name="Legacy", age=17, category="Male",
            state="Delhi", district="New Delhi",
            password_hash=hashlib.sha256("oldpass".encode()).hexdigest(),
        ))
        db.add(Performance(athlete_id=athlete_id, speed_score=0, agility_score=0,
                           strength_score=0, power_score=0, endurance_score=0, overall_index=0))
        db.commit()
    finally:
        db.close()

    res = client.post("/api/v1/auth/login", json={"athlete_id": athlete_id, "password": "oldpass"})
    assert res.status_code == 200

    db = SessionLocal()
    try:
        updated = db.query(Athlete).filter(Athlete.athlete_id == athlete_id).first()
        assert updated.password_hash.startswith("$2")  # upgraded to bcrypt
    finally:
        db.close()


# ─── Official registration is gated by the enrolment key ───
def test_official_register_requires_valid_key():
    bad = _register_official(key="WRONG-KEY")
    assert bad.status_code == 403

    good = _register_official()
    assert good.status_code == 201, good.text
    body = good.json()
    assert body["account_type"] == "official"
    assert body["access_token"]
    assert body["official"]["official_id"].startswith("OFF-2026-")


def test_official_duplicate_email_conflicts():
    suffix = _rand()
    email = f"dup{suffix}@sai.gov.in"
    p = {
        "name": "Dup", "email": email, "organization": "SAI",
        "password": "scoutpass", "signup_key": settings.OFFICIAL_SIGNUP_KEY,
    }
    first = client.post("/api/v1/auth/official/register", json=p)
    assert first.status_code == 201
    second = client.post("/api/v1/auth/official/register", json=p)
    assert second.status_code == 409


def test_official_login():
    suffix = _rand()
    email = f"login{suffix}@sai.gov.in"
    client.post("/api/v1/auth/official/register", json={
        "name": "Login Scout", "email": email, "organization": "SAI",
        "password": "scoutpass", "signup_key": settings.OFFICIAL_SIGNUP_KEY,
    })
    ok = client.post("/api/v1/auth/official/login", json={"email": email, "password": "scoutpass"})
    assert ok.status_code == 200
    assert ok.json()["official"]["email"] == email

    wrong = client.post("/api/v1/auth/official/login", json={"email": email, "password": "nope"})
    assert wrong.status_code == 401


# ─── Scout search authorization ───
def test_scout_search_requires_official_token():
    # No token → 401
    anon = client.get("/api/v1/scout/search")
    assert anon.status_code == 401

    # Athlete token → 403 (wrong account type)
    _, ath_token = _register_athlete()
    forbidden = client.get("/api/v1/scout/search", headers=_auth(ath_token))
    assert forbidden.status_code == 403

    # Official token → 200 with a list
    off = _register_official().json()
    ok = client.get("/api/v1/scout/search", headers=_auth(off["access_token"]))
    assert ok.status_code == 200
    assert isinstance(ok.json(), list)


# ─── Profile self-only for athletes, open to officials ───
def test_profile_access_rules():
    a_id, a_token = _register_athlete()
    b_id, b_token = _register_athlete()

    # Athlete reads own profile → 200
    own = client.get(f"/api/v1/athlete/profile/{a_id}", headers=_auth(a_token))
    assert own.status_code == 200

    # Athlete reads someone else's profile → 403
    other = client.get(f"/api/v1/athlete/profile/{b_id}", headers=_auth(a_token))
    assert other.status_code == 403

    # No token → 401
    anon = client.get(f"/api/v1/athlete/profile/{a_id}")
    assert anon.status_code == 401

    # Official reads any athlete → 200
    off = _register_official().json()
    off_read = client.get(f"/api/v1/athlete/profile/{a_id}", headers=_auth(off["access_token"]))
    assert off_read.status_code == 200


# ─── Assessment endpoints bind to the authenticated athlete ───
def test_sync_forces_caller_athlete_id():
    a_id, a_token = _register_athlete()

    # No token → 401
    anon = client.post("/api/v1/assessment/sync", json=[])
    assert anon.status_code == 401

    bogus_owner = "ATH-2026-999999"
    asm_id = f"ASM-SYNC-{_rand()}"
    item = {
        "assessment_id": asm_id,
        "athlete_id": bogus_owner,            # should be overridden with the caller's id
        "test_type": "vertical_jump",
        "raw_score": 42.0,
        "normalized_score": 80.0,
        "confidence": 95.0,
        "validation_score": 97.0,
        "timestamp": "2026-01-01T00:00:00",
        "status": "VALID",
        "details_json": None,
    }
    synced = client.post("/api/v1/assessment/sync", json=[item], headers=_auth(a_token))
    assert synced.status_code == 200

    # The synced assessment must appear under the CALLER's profile, not the bogus owner.
    prof = client.get(f"/api/v1/athlete/profile/{a_id}", headers=_auth(a_token)).json()
    ids = [asm["assessment_id"] for asm in prof["recent_assessments"]]
    assert asm_id in ids


def test_process_video_requires_athlete_token():
    unauth = client.post("/api/v1/assessment/process-video", json={
        "athlete_id": "ATH-2026-000001", "test_type": "sit_up", "fps": 30.0, "frames": []
    })
    assert unauth.status_code == 401


# ─── Rate limiting ───
def test_login_rate_limit_returns_429():
    # rate_limit(10, 300) on /auth/login → the 11th call from the same IP is throttled.
    last = None
    for _ in range(11):
        last = client.post("/api/v1/auth/login",
                           json={"athlete_id": "ATH-DOES-NOT-EXIST", "password": "x"})
    assert last.status_code == 429
    assert "Retry-After" in last.headers
