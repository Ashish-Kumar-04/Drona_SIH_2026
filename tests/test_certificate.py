"""
Verified certificate tests (Move 3).

Covers: PDF certificate download (auth required + ownership enforced), the public
/verify authenticity check, and tamper detection — mutating a signed field in the
stored record flips `authentic` to False.
"""

import json
import random
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.database.session import Base, engine, SessionLocal
from app.models.db_models import Assessment
from app.services import verification as cert_sig
from app.services.rate_limit import reset_all

client = TestClient(app)


def setup_module(module):
    Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    # TestClient shares one client IP; reset the in-memory limiter between tests.
    reset_all()
    yield
    reset_all()


# ─── Helpers ───
def _rand():
    return str(random.randint(1000000, 9999999))


def _register_athlete(password="pass1234"):
    suffix = _rand()
    payload = {
        "name": "Cert Athlete", "age": 16, "category": "Male",
        "state": "Maharashtra", "district": "Pune",
        "phone": f"98{suffix}", "email": f"cert{suffix}@example.com",
        "password": password,
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201, res.text
    body = res.json()
    return body["athlete"]["athlete_id"], body["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_signed_assessment(athlete_id, raw_score=42.0, normalized_score=78.5,
                            status="VALID", test_type="vertical_jump"):
    """Insert an assessment row carrying a valid issue-time signature; return its id."""
    asm_id = f"ASM-CERT-{_rand()}"
    ts = datetime(2026, 1, 1, 12, 0, 0)  # no microseconds → survives SQLite round-trip
    sig = cert_sig.sign_fields(athlete_id, test_type, raw_score, normalized_score, status, ts)
    db = SessionLocal()
    try:
        db.add(Assessment(
            assessment_id=asm_id, athlete_id=athlete_id, test_type=test_type,
            raw_score=raw_score, normalized_score=normalized_score,
            confidence=95.0, validation_score=96.0, timestamp=ts, status=status,
            sync_status="SYNCED",
            details_json=json.dumps({cert_sig.SIGNATURE_KEY: sig}),
        ))
        db.commit()
    finally:
        db.close()
    return asm_id


# ─── PDF certificate download ───
def test_certificate_download_returns_pdf():
    a_id, a_token = _register_athlete()
    asm_id = _make_signed_assessment(a_id)
    res = client.get(f"/api/v1/assessment/{asm_id}/certificate", headers=_auth(a_token))
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("application/pdf")
    assert res.content[:5] == b"%PDF-"
    assert len(res.content) > 1000  # a real, non-trivial PDF


def test_certificate_ownership_enforced():
    a_id, a_token = _register_athlete()
    _b_id, b_token = _register_athlete()
    asm_id = _make_signed_assessment(a_id)

    # Owner → 200
    assert client.get(f"/api/v1/assessment/{asm_id}/certificate",
                      headers=_auth(a_token)).status_code == 200
    # Another athlete → 403
    assert client.get(f"/api/v1/assessment/{asm_id}/certificate",
                      headers=_auth(b_token)).status_code == 403
    # Anonymous → 401
    assert client.get(f"/api/v1/assessment/{asm_id}/certificate").status_code == 401


def test_certificate_unknown_id_404():
    _a_id, a_token = _register_athlete()
    assert client.get("/api/v1/assessment/ASM-NOPE-000/certificate",
                      headers=_auth(a_token)).status_code == 404


# ─── Public verification ───
def test_verify_authentic_true():
    a_id, _ = _register_athlete()
    asm_id = _make_signed_assessment(a_id, raw_score=42.0, normalized_score=78.5)
    res = client.get(f"/api/v1/verify/{asm_id}")  # public — no token
    assert res.status_code == 200
    body = res.json()
    assert body["authentic"] is True
    assert body["verification_note"] == "signature_valid"
    assert body["assessment_id"] == asm_id
    assert body["raw_score"] == 42.0
    assert body["signature"]


def test_verify_detects_tampering():
    a_id, _ = _register_athlete()
    asm_id = _make_signed_assessment(a_id, raw_score=42.0, normalized_score=78.5)

    # Authentic before tampering
    assert client.get(f"/api/v1/verify/{asm_id}").json()["authentic"] is True

    # Tamper: bump the stored raw_score without updating the stored signature.
    db = SessionLocal()
    try:
        row = db.query(Assessment).filter(Assessment.assessment_id == asm_id).first()
        row.raw_score = 99.0
        db.commit()
    finally:
        db.close()

    after = client.get(f"/api/v1/verify/{asm_id}").json()
    assert after["authentic"] is False
    assert after["verification_note"] == "signature_mismatch"


def test_verify_unknown_id_404():
    assert client.get("/api/v1/verify/ASM-NOPE-000").status_code == 404
