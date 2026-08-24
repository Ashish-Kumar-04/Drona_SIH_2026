"""
Core configuration and normative benchmark reference standards for SIH 25073.
"""

import os
from typing import Dict, Any

# Load environment variables from a local .env file if present (SMS credentials, DB URL, etc.).
# This must run before Settings reads os.getenv below.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed yet — env vars can still be provided by the shell.
    # Install it with:  pip install -r requirements.txt
    pass

class Settings:
    PROJECT_NAME: str = "AI Sports Talent Assessment Platform"
    PROBLEM_STATEMENT_ID: str = "25073"
    VERSION: str = "1.0.0"
    
    # Database
    SQLITE_DB_URL: str = os.getenv("DATABASE_URL", "sqlite:///./sih_assessment.db")

    # ─── SMS / OTP delivery ───
    # Twilio is the primary provider; Fast2SMS is an optional India-only fallback.
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")
    FAST2SMS_API_KEY: str = os.getenv("FAST2SMS_API_KEY", "")
    # Country code prepended to bare 10-digit mobile numbers before sending (India = +91).
    DEFAULT_COUNTRY_CODE: str = os.getenv("DEFAULT_COUNTRY_CODE", "+91")
    # When true, the OTP is returned in the API response if SMS delivery is not configured
    # or fails, so the flow stays demoable. MUST be false in production.
    SMS_DEBUG: bool = os.getenv("SMS_DEBUG", "true").strip().lower() in ("1", "true", "yes")

    # ─── Authentication / security ───
    # JWT signing key. MUST be overridden in production via the JWT_SECRET_KEY env var.
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev-insecure-change-me-please-set-JWT_SECRET_KEY")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "12"))
    # Shared enrolment key required to register an Official/Scout account. Prevents anyone
    # self-elevating to an official (which would re-expose every athlete's PII).
    OFFICIAL_SIGNUP_KEY: str = os.getenv("OFFICIAL_SIGNUP_KEY", "SAI-OFFICIAL-2026")
    # HMAC key for tamper-evident certificate signatures. Defaults to the JWT key if unset.
    CERT_SIGNING_KEY: str = os.getenv("CERT_SIGNING_KEY", "").strip() or JWT_SECRET_KEY
    # Public base URL used to build the certificate QR verification link (/api/v1/verify/{id}).
    # Set this to your deployed backend URL in production so scanned QRs resolve publicly.
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

    # ─── CORS ───
    # Comma-separated list of allowed browser origins. Never "*" together with credentials.
    _ALLOWED_ORIGINS_RAW: str = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    ALLOWED_ORIGINS: list = [o.strip() for o in _ALLOWED_ORIGINS_RAW.split(",") if o.strip()]

    # True when the JWT key is still the insecure development default (used to warn on startup).
    @property
    def jwt_key_is_default(self) -> bool:
        return self.JWT_SECRET_KEY == "dev-insecure-change-me-please-set-JWT_SECRET_KEY"

    # Physics constants
    GRAVITY_ACCEL: float = 9.81  # m/s^2
    
    # MediaPipe pose configuration
    MIN_DETECTION_CONFIDENCE: float = 0.5
    MIN_TRACKING_CONFIDENCE: float = 0.5
    
    # Benchmark Labeling Strategy (per document directive #15).
    # This is the DEFAULT provenance label; each test also carries its own citation in TEST_REGISTRY.
    BENCHMARK_SOURCE_LABEL: str = "Prototype / Research Benchmark"

    # ─── Canonical Test Registry ───
    # Single source of truth for every fitness test the platform scores. Replaces the scattered
    # per-test `if test_type == ...` branches, unit maps, and label maps that previously lived in routes.
    #   direction:  "higher" -> larger raw value is better   (reps, cm)
    #               "lower"  -> smaller raw value is better   (seconds)
    #               "optimal_band" -> closeness to a healthy band is better (BMI)
    #   capture:    "cv"       -> derived from pose video by a CV analyzer
    #               "manual"   -> assisted/officiated entry (stopwatch, tape, sit-&-reach box)
    #               "computed" -> derived from existing profile data (no capture step)
    #   domain:     which Athletic Performance Index domain this test feeds
    #   plausible_min/max: hard sanity bounds used to reject typos / fraud on manual entry
    #   source:     per-test provenance shown on results & certificates
    TEST_REGISTRY: Dict[str, Dict[str, Any]] = {
        "sit_up": {
            "label": "Sit-ups (Core Strength & Endurance)",
            "unit": "reps", "direction": "higher", "domain": "strength", "capture": "cv",
            "protocol": "Maximum correct bent-knee sit-ups in 60 seconds.",
            "plausible_min": 0.0, "plausible_max": 120.0,
            "source": "Prototype norm aligned to AAHPERD / Khelo India 60s sit-up data - validate vs SAI tables",
        },
        "vertical_jump": {
            "label": "Standing Vertical Jump (Explosive Power)",
            "unit": "cm", "direction": "higher", "domain": "power", "capture": "cv",
            "protocol": "Sargent-style standing vertical jump; best of 3 attempts.",
            "plausible_min": 0.0, "plausible_max": 120.0,
            "source": "Prototype norm aligned to Eurofit / FITNESSGRAM vertical-jump data - validate vs SAI tables",
        },
        "shuttle_run": {
            "label": "4x10m Shuttle Run (Agility)",
            "unit": "sec", "direction": "lower", "domain": "agility", "capture": "cv",
            "protocol": "4 x 10m shuttle run; lower total time is better.",
            "plausible_min": 6.0, "plausible_max": 40.0,
            "source": "Prototype norm aligned to Eurofit 4x10m shuttle data - validate vs SAI tables",
        },
        "sprint_50m": {
            "label": "50m Dash (Speed)",
            "unit": "sec", "direction": "lower", "domain": "speed", "capture": "manual",
            "protocol": "50m sprint from a standing start; stopwatch or timing gate (seconds).",
            "plausible_min": 5.0, "plausible_max": 25.0,
            "source": "Prototype norm aligned to Khelo India 50m dash data - validate vs SAI tables",
        },
        "endurance_run": {
            "label": "Endurance Run (600m)",
            "unit": "sec", "direction": "lower", "domain": "endurance", "capture": "manual",
            "protocol": "600m timed run; enter total time in seconds. (1.6km needs its own norms.)",
            "plausible_min": 90.0, "plausible_max": 600.0,
            "source": "Prototype norm aligned to Khelo India 600m run data - validate vs SAI tables",
        },
        "sit_and_reach": {
            "label": "Sit & Reach (Flexibility)",
            "unit": "cm", "direction": "higher", "domain": "flexibility", "capture": "manual",
            "protocol": "Sit-and-reach box; cm reached beyond the toe line (may be negative).",
            "plausible_min": -30.0, "plausible_max": 50.0,
            "source": "Prototype norm aligned to Eurofit sit-and-reach data - validate vs SAI tables",
        },
        "broad_jump": {
            "label": "Standing Broad Jump (Leg Power)",
            "unit": "cm", "direction": "higher", "domain": "power", "capture": "cv",
            "manual_fallback": True,
            "protocol": "Standing long jump; best horizontal distance of 3 attempts (cm).",
            "plausible_min": 30.0, "plausible_max": 350.0,
            "source": "Prototype norm aligned to Eurofit standing broad-jump data - validate vs SAI tables",
        },
        "bmi": {
            "label": "Body Mass Index (Body Composition)",
            "unit": "kg/m^2", "direction": "optimal_band", "domain": "body_composition", "capture": "computed",
            "protocol": "Computed from height & weight; scored against an age/gender healthy band.",
            "plausible_min": 8.0, "plausible_max": 45.0,
            "source": "Prototype optimal band aligned to IAP / WHO youth BMI percentiles - validate vs SAI tables",
        },
    }

    # Ordered age-band midpoints used for PER-YEAR linear interpolation of norms.
    # (midpoint_age, band_key) — the benchmarker interpolates between the two bracketing bands.
    AGE_BAND_MIDPOINTS = [
        (8.5, "8-9"),
        (11.0, "10-12"),
        (14.0, "13-15"),
        (17.0, "16-18"),
        (22.0, "Adult"),
    ]

    # Normative Benchmarks by Age band and Sex.
    # Only Male/Female anchors are stored; "General" is derived by averaging them at lookup time,
    # and exact ages are linearly interpolated between the bracketing band midpoints above.
    # Metrics: sit_up (reps/60s), vertical_jump (cm), shuttle_run (4x10m sec), sprint_50m (sec),
    #          endurance_run (600m sec), sit_and_reach (cm), broad_jump (cm), bmi (optimal band).
    # Values are documented, cited best-estimates (see docs/BENCHMARKS.md) — NOT official SAI tables.
    NORMATIVE_BENCHMARKS: Dict[str, Dict[str, Any]] = {
        "8-9_Male": {
            "sit_up": {"mean": 16.0, "std": 5.0}, "vertical_jump": {"mean": 22.0, "std": 5.0},
            "shuttle_run": {"mean": 13.5, "std": 1.1}, "sprint_50m": {"mean": 9.8, "std": 0.9},
            "endurance_run": {"mean": 165.0, "std": 20.0}, "sit_and_reach": {"mean": 2.0, "std": 5.0},
            "broad_jump": {"mean": 120.0, "std": 20.0}, "bmi": {"optimal_low": 14.0, "optimal_high": 18.5, "std": 3.0},
        },
        "8-9_Female": {
            "sit_up": {"mean": 14.0, "std": 5.0}, "vertical_jump": {"mean": 20.0, "std": 5.0},
            "shuttle_run": {"mean": 14.2, "std": 1.2}, "sprint_50m": {"mean": 10.2, "std": 0.9},
            "endurance_run": {"mean": 175.0, "std": 20.0}, "sit_and_reach": {"mean": 4.0, "std": 5.0},
            "broad_jump": {"mean": 110.0, "std": 20.0}, "bmi": {"optimal_low": 14.0, "optimal_high": 18.5, "std": 3.0},
        },
        "10-12_Male": {
            "sit_up": {"mean": 22.0, "std": 6.0}, "vertical_jump": {"mean": 28.0, "std": 6.0},
            "shuttle_run": {"mean": 12.6, "std": 1.0}, "sprint_50m": {"mean": 8.9, "std": 0.8},
            "endurance_run": {"mean": 150.0, "std": 18.0}, "sit_and_reach": {"mean": 3.0, "std": 6.0},
            "broad_jump": {"mean": 145.0, "std": 22.0}, "bmi": {"optimal_low": 14.5, "optimal_high": 20.5, "std": 3.0},
        },
        "10-12_Female": {
            "sit_up": {"mean": 19.0, "std": 5.5}, "vertical_jump": {"mean": 25.0, "std": 5.5},
            "shuttle_run": {"mean": 13.3, "std": 1.1}, "sprint_50m": {"mean": 9.4, "std": 0.8},
            "endurance_run": {"mean": 162.0, "std": 18.0}, "sit_and_reach": {"mean": 6.0, "std": 6.0},
            "broad_jump": {"mean": 135.0, "std": 22.0}, "bmi": {"optimal_low": 14.5, "optimal_high": 20.5, "std": 3.0},
        },
        "13-15_Male": {
            "sit_up": {"mean": 30.0, "std": 6.5}, "vertical_jump": {"mean": 38.0, "std": 7.0},
            "shuttle_run": {"mean": 11.3, "std": 0.9}, "sprint_50m": {"mean": 7.9, "std": 0.7},
            "endurance_run": {"mean": 135.0, "std": 16.0}, "sit_and_reach": {"mean": 4.0, "std": 7.0},
            "broad_jump": {"mean": 180.0, "std": 25.0}, "bmi": {"optimal_low": 16.0, "optimal_high": 22.5, "std": 3.0},
        },
        "13-15_Female": {
            "sit_up": {"mean": 25.0, "std": 6.0}, "vertical_jump": {"mean": 31.0, "std": 6.0},
            "shuttle_run": {"mean": 12.3, "std": 1.0}, "sprint_50m": {"mean": 8.7, "std": 0.7},
            "endurance_run": {"mean": 150.0, "std": 16.0}, "sit_and_reach": {"mean": 9.0, "std": 7.0},
            "broad_jump": {"mean": 155.0, "std": 24.0}, "bmi": {"optimal_low": 16.0, "optimal_high": 22.5, "std": 3.0},
        },
        "16-18_Male": {
            "sit_up": {"mean": 37.0, "std": 7.0}, "vertical_jump": {"mean": 48.0, "std": 8.0},
            "shuttle_run": {"mean": 10.5, "std": 0.8}, "sprint_50m": {"mean": 7.1, "std": 0.6},
            "endurance_run": {"mean": 125.0, "std": 15.0}, "sit_and_reach": {"mean": 6.0, "std": 7.0},
            "broad_jump": {"mean": 210.0, "std": 28.0}, "bmi": {"optimal_low": 17.5, "optimal_high": 24.5, "std": 3.0},
        },
        "16-18_Female": {
            "sit_up": {"mean": 29.0, "std": 6.5}, "vertical_jump": {"mean": 36.0, "std": 6.5},
            "shuttle_run": {"mean": 11.6, "std": 0.9}, "sprint_50m": {"mean": 8.3, "std": 0.7},
            "endurance_run": {"mean": 145.0, "std": 16.0}, "sit_and_reach": {"mean": 12.0, "std": 7.0},
            "broad_jump": {"mean": 170.0, "std": 25.0}, "bmi": {"optimal_low": 17.5, "optimal_high": 24.5, "std": 3.0},
        },
        "Adult_Male": {
            "sit_up": {"mean": 34.0, "std": 8.0}, "vertical_jump": {"mean": 50.0, "std": 8.5},
            "shuttle_run": {"mean": 10.3, "std": 0.8}, "sprint_50m": {"mean": 6.9, "std": 0.6},
            "endurance_run": {"mean": 120.0, "std": 15.0}, "sit_and_reach": {"mean": 7.0, "std": 8.0},
            "broad_jump": {"mean": 215.0, "std": 30.0}, "bmi": {"optimal_low": 18.5, "optimal_high": 25.0, "std": 3.0},
        },
        "Adult_Female": {
            "sit_up": {"mean": 27.0, "std": 7.0}, "vertical_jump": {"mean": 37.0, "std": 7.0},
            "shuttle_run": {"mean": 11.5, "std": 0.9}, "sprint_50m": {"mean": 8.2, "std": 0.7},
            "endurance_run": {"mean": 142.0, "std": 16.0}, "sit_and_reach": {"mean": 13.0, "std": 8.0},
            "broad_jump": {"mean": 172.0, "std": 26.0}, "bmi": {"optimal_low": 18.5, "optimal_high": 25.0, "std": 3.0},
        },
    }

settings = Settings()
