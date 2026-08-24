"""
Tamper-evident certificate signatures.

Each assessment is signed with HMAC-SHA256 over its canonical, immutable fields
(athlete id, test, raw + normalized score, authenticity status, timestamp). The
signature is stored inside the assessment's details_json at creation time and
printed (in short form) on the PDF certificate. The public /verify/{id} endpoint
recomputes the signature from the current database row and compares it against the
stored one — so any later tampering with a stored score makes verification fail.

The signing key is settings.CERT_SIGNING_KEY (defaults to the JWT secret).
"""

import hmac
import hashlib
from datetime import datetime

from app.core.config import settings

# Key inside details_json where the issue-time signature is stored.
SIGNATURE_KEY = "cert_signature"


def _canonical(athlete_id, test_type, raw_score, normalized_score, status, timestamp) -> str:
    """Stable, order-fixed representation of the fields the signature covers."""
    ts = timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp)
    # Fixed precision so trivial float-repr differences never change the signature.
    return "|".join([
        str(athlete_id),
        str(test_type),
        f"{float(raw_score):.4f}",
        f"{float(normalized_score):.4f}",
        str(status),
        ts,
    ])


def sign_fields(athlete_id, test_type, raw_score, normalized_score, status, timestamp) -> str:
    """Compute the full hex HMAC-SHA256 signature for the given assessment fields."""
    msg = _canonical(athlete_id, test_type, raw_score, normalized_score, status, timestamp)
    return hmac.new(
        settings.CERT_SIGNING_KEY.encode("utf-8"),
        msg.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def sign_assessment(assessment) -> str:
    """Compute the signature from an Assessment ORM row's current field values."""
    return sign_fields(
        assessment.athlete_id,
        assessment.test_type,
        assessment.raw_score,
        assessment.normalized_score,
        assessment.status,
        assessment.timestamp,
    )


def short_signature(signature: str) -> str:
    """A short, human-transcribable form of a signature for printing (e.g. A1B2-C3D4-E5F6-7890)."""
    s = (signature or "").upper()[:16]
    return "-".join(s[i:i + 4] for i in range(0, len(s), 4))


def verify_assessment(assessment, stored_signature: str):
    """
    Recompute the signature from the current DB row and compare with the stored one.

    Returns (authentic: bool, note: str).
    - authentic True  → the signed fields are unchanged since the certificate was issued.
    - authentic False → a signed field was altered after issue (tampering) — or the
      stored signature is missing/garbled.
    """
    recomputed = sign_assessment(assessment)
    if not stored_signature:
        # Legacy row created before signing existed — self-consistent, but not issue-signed.
        return True, "unsigned_legacy_record"
    if hmac.compare_digest(recomputed, stored_signature):
        return True, "signature_valid"
    return False, "signature_mismatch"
