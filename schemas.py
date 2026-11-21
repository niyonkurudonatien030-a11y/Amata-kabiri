"""Input validation. Every value from a browser is checked here before it touches the database."""
import re
from datetime import datetime

ROLES_SELF_REGISTER = ("farmer", "buyer", "driver")
ROLES_ALL = ("farmer", "buyer", "driver", "coop_admin", "admin")
EVIDENCE_CATEGORIES = ("quality_measurement", "lactometer_photo", "delivery_photo",
                       "collection_receipt", "payment_receipt", "other")
PAYMENT_METHODS = ("mobile_money", "bank", "cash", "other")


class ValidationError(Exception):
    pass


def text(data, key, required=True, max_len=500):
    value = data.get(key)
    if value is None or str(value).strip() == "":
        if required:
            raise ValidationError(f"'{key}' is required")
        return None
    value = str(value).strip()
    if len(value) > max_len:
        raise ValidationError(f"'{key}' is too long (max {max_len})")
    return value


def number(data, key, minimum=0.0, required=True):
    raw = data.get(key)
    if raw in (None, ""):
        if required:
            raise ValidationError(f"'{key}' is required")
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValidationError(f"'{key}' must be a number")
    if value != value or value in (float("inf"), float("-inf")):
        raise ValidationError(f"'{key}' must be a finite number")
    if value <= minimum:
        raise ValidationError(f"'{key}' must be greater than {minimum:g}")
    return value


def phone(raw):
    """Accepts 07XXXXXXXX, 2507XXXXXXXX, +2507XXXXXXXX and returns +2507XXXXXXXX."""
    digits = re.sub(r"[\s\-()]", "", str(raw or ""))
    if digits.startswith("+"):
        digits = digits[1:]
    if digits.startswith("0"):
        digits = "250" + digits[1:]
    if not re.fullmatch(r"2507[2389]\d{7}", digits):
        raise ValidationError("Enter a valid Rwandan mobile number, e.g. 0788123456")
    return "+" + digits


def password(raw):
    raw = str(raw or "")
    if len(raw) < 8:
        raise ValidationError("Password must be at least 8 characters")
    if raw.lower() == raw or not re.search(r"\d", raw):
        raise ValidationError("Password needs an uppercase letter and a digit")
    return raw


def registration(data):
    role = text(data, "role")
    if role not in ROLES_SELF_REGISTER:
        raise ValidationError("Role must be farmer, buyer or driver")
    return {
        "role": role,
        "full_name": text(data, "full_name", max_len=120),
        "phone": phone(data.get("phone")),
        "email": text(data, "email", required=False, max_len=120),
        "password": password(data.get("password")),
        "district": text(data, "district", required=False, max_len=60),
        "organisation": text(data, "organisation", required=False, max_len=120),
    }


def iso_datetime(value):
    if not value:
        return None
    try:
        datetime.fromisoformat(str(value))
    except ValueError:
        raise ValidationError("Invalid date/time")
    return str(value)


def deal(data):
    dtype = text(data, "deal_type")
    if dtype not in ("sell", "buy"):
        raise ValidationError("deal_type must be 'sell' or 'buy'")
    litres = number(data, "litres")
    price = number(data, "price_per_litre")
    return {
        "deal_type": dtype,
        "litres": litres,
        "price_per_litre": price,
        "total_value": round(litres * price, 2),
        "location": text(data, "location", max_len=200),
        "district": text(data, "district", required=False, max_len=60),
        "delivery_at": iso_datetime(data.get("delivery_at")),
        "quality_requirements": text(data, "quality_requirements", required=False, max_len=1000),
        "terms": text(data, "terms", required=False, max_len=2000),
    }


def payment(data):
    method = text(data, "method")
    if method not in PAYMENT_METHODS:
        raise ValidationError("Invalid payment method")
    try:
        evidence_id = int(data["evidence_id"]) if data.get("evidence_id") not in (None, "") else None
    except (TypeError, ValueError):
        raise ValidationError("Invalid evidence_id")
    return {
        "amount": number(data, "amount"),
        "method": method,
        "reference": text(data, "reference", required=False, max_len=100),
        "evidence_id": evidence_id,
    }
