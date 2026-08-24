"""
Real SMS Delivery Service for Password Reset OTP and Notifications.
Primary provider: Twilio (global). Fast2SMS (India) is supported as an optional fallback.

Every send returns an accurate outcome dict — it never claims success for a message that
was not actually accepted by a provider:
    {"success": bool, "delivered": bool, "provider": str, "to": str, "detail": str, "sid"?: str}
"""

import logging
import urllib.request
import urllib.parse
import urllib.error
import json
import base64

from app.core.config import settings

logger = logging.getLogger(__name__)


def normalize_phone_e164(phone_number: str, default_country_code: str = "+91") -> str:
    """
    Normalize a phone number to E.164 format (e.g. +919876543210), which Twilio requires.
    An un-normalized number (e.g. a bare '9876543210') is the most common reason Twilio
    rejects a message with error 21211 "Invalid 'To' Phone Number".

    Rules:
      - A number already starting with '+' keeps its country code.
      - A bare 10-digit national number gets the default country code prepended.
      - A number that already includes the country-code digits gets a leading '+'.
    """
    if not phone_number:
        return ""

    raw = phone_number.strip()
    has_plus = raw.startswith("+")
    digits = "".join(filter(str.isdigit, raw))
    if not digits:
        return ""

    if has_plus:
        return "+" + digits

    cc_digits = "".join(filter(str.isdigit, default_country_code)) or "91"

    # Strip a single leading trunk '0' (India is often written as 0XXXXXXXXXX).
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    if len(digits) == 10:
        # Bare national mobile number → prepend the default country code.
        return "+" + cc_digits + digits
    if len(digits) > 10 and digits.startswith(cc_digits):
        # Already includes the country code, just missing the '+'.
        return "+" + digits
    # Fallback: assume it's already international and just add the '+'.
    return "+" + digits


def _send_via_twilio(to_number: str, message: str) -> dict:
    """Send an SMS through Twilio's REST API and surface the real outcome."""
    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
    auth_str = f"{settings.TWILIO_ACCOUNT_SID}:{settings.TWILIO_AUTH_TOKEN}"
    b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = urllib.parse.urlencode({
        "From": settings.TWILIO_PHONE_NUMBER,
        "To": to_number,
        "Body": message,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = json.loads(response.read().decode("utf-8"))
        sid = res_body.get("sid")
        twilio_status = res_body.get("status")
        logger.info(f"Twilio accepted SMS to {to_number}: sid={sid} status={twilio_status}")
        return {
            "success": True, "delivered": True, "provider": "Twilio",
            "to": to_number, "sid": sid, "detail": f"Twilio status: {twilio_status}",
        }
    except urllib.error.HTTPError as e:
        # Twilio returns a JSON body describing the real reason (unverified trial number,
        # invalid 'To', bad credentials, etc.). Surface it instead of hiding it.
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            twilio_msg = err_body.get("message", str(e))
            twilio_code = err_body.get("code")
        except Exception:
            twilio_msg, twilio_code = str(e), None
        detail = f"Twilio error {twilio_code}: {twilio_msg}" if twilio_code else f"Twilio error: {twilio_msg}"
        logger.error(detail)
        return {"success": False, "delivered": False, "provider": "Twilio", "to": to_number, "detail": detail}
    except Exception as e:
        detail = f"Twilio dispatch failed (network/timeout): {e}"
        logger.error(detail)
        return {"success": False, "delivered": False, "provider": "Twilio", "to": to_number, "detail": detail}


def _send_via_fast2sms(to_number: str, otp_code: str) -> dict:
    """Send an OTP through Fast2SMS (India) and surface the real outcome."""
    clean_phone = "".join(filter(str.isdigit, to_number))[-10:]
    url = "https://www.fast2sms.com/dev/bulkV2"
    headers = {
        "authorization": settings.FAST2SMS_API_KEY,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = urllib.parse.urlencode({
        "variables_values": otp_code,
        "route": "otp",
        "numbers": clean_phone,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = json.loads(response.read().decode("utf-8"))
        # Fast2SMS returns HTTP 200 even on failure — the real result is in "return".
        if res_body.get("return") is True:
            logger.info(f"Fast2SMS accepted SMS to {clean_phone}: {res_body}")
            return {
                "success": True, "delivered": True, "provider": "Fast2SMS",
                "to": clean_phone, "detail": str(res_body.get("message")),
            }
        detail = f"Fast2SMS rejected: {res_body.get('message')}"
        logger.error(detail)
        return {"success": False, "delivered": False, "provider": "Fast2SMS", "to": clean_phone, "detail": detail}
    except Exception as e:
        detail = f"Fast2SMS dispatch failed: {e}"
        logger.error(detail)
        return {"success": False, "delivered": False, "provider": "Fast2SMS", "to": clean_phone, "detail": detail}


def send_otp_sms(phone_number: str, otp_code: str) -> dict:
    """
    Send a password-reset OTP via SMS. Tries Twilio first, then Fast2SMS.
    Returns an accurate outcome dict (see module docstring). `delivered` is True only when
    a real provider accepted the message.
    """
    message = (
        f"Your Drona AI Sports Assessment password reset OTP is: {otp_code}. "
        f"Valid for 10 minutes. Do not share this OTP."
    )
    to_number = normalize_phone_e164(phone_number, settings.DEFAULT_COUNTRY_CODE)

    if not to_number:
        detail = "No valid phone number to send the OTP to."
        logger.error(detail)
        return {"success": False, "delivered": False, "provider": "none", "to": "", "detail": detail}

    # 1. Twilio (primary, global)
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_PHONE_NUMBER:
        return _send_via_twilio(to_number, message)

    # 2. Fast2SMS (optional India fallback)
    if settings.FAST2SMS_API_KEY:
        return _send_via_fast2sms(to_number, otp_code)

    # 3. No provider configured — development fallback. Explicitly NOT delivered.
    logger.warning(
        "No SMS provider configured (set TWILIO_* or FAST2SMS_API_KEY in .env). "
        f"OTP for {to_number} was NOT sent to a real phone."
    )
    # ASCII-only output: a Windows cp1252 console raises UnicodeEncodeError on emoji.
    print("\n==========================================")
    print("[SMS NOT CONFIGURED] OTP was NOT sent to a real phone.")
    print(f"  Would send to : {to_number}")
    print(f"  Message       : {message}")
    print("  Fix: copy .env.example to .env and set your TWILIO_* credentials.")
    print("==========================================\n")
    return {
        "success": False, "delivered": False, "provider": "none", "to": to_number,
        "detail": "No SMS provider configured. Copy .env.example to .env and set your Twilio credentials.",
    }
