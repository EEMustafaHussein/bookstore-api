"""Small helpers for reading and checking HTML form fields."""

import re

from email_validator import EmailNotValidError, validate_email

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_IRAQI_MOBILE = re.compile(r"^(?:\+?964|00964|0)?(7\d{9})$")


def text(form, key: str, max_length: int = 200) -> str:
    value = form.get(key)
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


def secret(form, key: str) -> str:
    """Reads a password exactly as typed (no trimming)."""
    value = form.get(key)
    return value[:200] if isinstance(value, str) else ""


def western_digits(value: str) -> str:
    return value.translate(_DIGITS)


def number(form, key: str) -> int | None:
    """Reads a whole number, accepting Arabic digits and thousands separators like 25,000."""
    raw = western_digits(text(form, key, 30)).replace(",", "").replace("٬", "").replace(" ", "")
    if not raw:
        return None
    if not raw.isdigit():
        raise ValueError(key)
    return int(raw)


def checkbox(form, key: str) -> bool:
    return form.get(key) in ("on", "1", "true", "yes")


def email(value: str) -> str | None:
    try:
        return validate_email(value, check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        return None


def iraqi_mobile(value: str) -> str | None:
    cleaned = re.sub(r"[\s\-()]", "", western_digits(value))
    match = _IRAQI_MOBILE.match(cleaned)
    return f"0{match.group(1)}" if match else None


def safe_url(value: str) -> str:
    """Accepts only http(s) links so a stored link can never run script."""
    value = value.strip()
    if not value:
        return ""
    # Any other scheme (javascript:, data:, ...) is dropped instead of being turned into a link.
    if re.match(r"^[a-z][a-z0-9+.\-]*:(?!//)", value, re.IGNORECASE):
        return ""
    if not re.match(r"^https?://", value, re.IGNORECASE):
        value = "https://" + value.lstrip("/")
    if re.search(r"[\s<>\"']", value):
        return ""
    return value[:300]


def safe_next(value: str | None, default: str = "/") -> str:
    """Only allows redirects to pages on this site."""
    if value and value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    return default
