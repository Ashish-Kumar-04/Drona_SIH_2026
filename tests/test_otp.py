import pytest
from fastapi.testclient import TestClient
from app.api.main import app
from app.database.session import Base, engine, get_db, SessionLocal
from app.models.db_models import Athlete, OTPReset
from app.services import rate_limit

client = TestClient(app)

def setup_module(module):
    Base.metadata.create_all(bind=engine)

import random

@pytest.fixture(autouse=True)
def _clear_rate_limits():
    # In-memory limiter is keyed by client IP; TestClient shares one IP, so reset
    # between tests to avoid unrelated 429s.
    rate_limit.reset_all()
    yield
    rate_limit.reset_all()

def test_otp_request_and_password_reset_flow():
    rand_suffix = str(random.randint(1000000, 9999999))
    test_phone = f"99{rand_suffix}"
    test_email = f"otp{rand_suffix}@example.com"

    # 1. Register test athlete
    reg_payload = {
        "name": "OTP Test Athlete",
        "age": 16,
        "category": "Male",
        "state": "Delhi",
        "district": "New Delhi",
        "phone": test_phone,
        "email": test_email,
        "password": "initial_password_123"
    }
    reg_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    reg_body = reg_res.json()
    # Registration now returns a TokenResponse: {access_token, account_type, athlete}
    assert reg_body["account_type"] == "athlete"
    assert reg_body["access_token"]
    athlete_id = reg_body["athlete"]["athlete_id"]

    # 2. Request OTP using Phone Number
    otp_req_res = client.post("/api/v1/auth/request-otp", json={"athlete_id": test_phone})
    assert otp_req_res.status_code == 200
    otp_data = otp_req_res.json()
    assert otp_data["athlete_id"] == athlete_id
    assert "otp_code" in otp_data
    otp_code = otp_data["otp_code"]
    assert len(otp_code) == 6

    # 3. Reset password using the received OTP
    reset_payload = {
        "athlete_id": athlete_id,
        "otp_code": otp_code,
        "new_password": "new_secure_password_456"
    }
    reset_res = client.post("/api/v1/auth/reset-password", json=reset_payload)
    assert reset_res.status_code == 200
    assert "successful" in reset_res.json()["message"].lower()

    # 4. Login with old password -> should fail (401)
    old_login = client.post("/api/v1/auth/login", json={"athlete_id": athlete_id, "password": "initial_password_123"})
    assert old_login.status_code == 401

    # 5. Login with new password -> should succeed (200) and return a token + athlete
    new_login = client.post("/api/v1/auth/login", json={"athlete_id": athlete_id, "password": "new_secure_password_456"})
    assert new_login.status_code == 200
    login_body = new_login.json()
    assert login_body["athlete"]["athlete_id"] == athlete_id
    assert login_body["access_token"]
