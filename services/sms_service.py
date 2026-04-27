"""MSG91 OTP delivery wrapper."""

import os
from typing import Tuple
import logging

import requests


MSG91_OTP_URL = "https://api.msg91.com/api/v5/otp"
logger = logging.getLogger(__name__)


def _normalize_indian_phone(phone: str) -> str:
    """Return a clean Indian mobile number prefixed with country code 91."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if digits.startswith("91") and len(digits) >= 12:
        local = digits[-10:]
    else:
        local = digits[-10:]
    return f"91{local}" if local else ""


def send_msg91_otp(phone: str, otp: str) -> Tuple[bool, str]:
    """Send OTP through MSG91 and return (ok, message)."""
    auth_key = os.environ.get("MSG91_AUTH_KEY", "").strip()
    template_id = os.environ.get("MSG91_TEMPLATE_ID", "").strip()
    mobile = _normalize_indian_phone(phone)

    if not auth_key or not template_id:
        return False, "MSG91 credentials are missing in environment."
    if len(mobile) != 12:
        return False, "Invalid customer mobile number for MSG91."

    payload = {
        "template_id": template_id,
        "mobile": mobile,
        "otp": otp,
        "authkey": auth_key,
    }
    try:
        response = requests.post(MSG91_OTP_URL, json=payload, timeout=12)
        if 200 <= response.status_code < 300:
            return True, "OTP SMS sent."
        message = f"MSG91 error {response.status_code}: {response.text[:200]}"
        logger.error(message)
        return False, message
    except Exception as exc:
        message = f"MSG91 request failed: {exc}"
        logger.exception(message)
        return False, message
