"""
Sensitive data redaction utilities.

Adapted and extended from Member 4's security module specification.
Recursively sanitises dictionaries, lists, strings, and nested objects by replacing sensitive keys
(e.g., passwords, OTPs, CVVs, card numbers, API keys, tokens) with "[REDACTED]".
Provides regex-based pattern redaction for Bearer tokens, URLs with credentials, and card numbers.
"""

from __future__ import annotations

import re
from typing import Any

# Sensitive keys matching Member 4's security.js specification and Phase 7 compliance requirements
SENSITIVE_KEYS: tuple[str, ...] = (
    "password",
    "passwd",
    "pwd",
    "passcode",
    "otp",
    "totp",
    "token",
    "bearer",
    "authorization",
    "auth",
    "cookie",
    "cardnumber",
    "creditcard",
    "debitcard",
    "cvv",
    "cvc",
    "upiid",
    "vpa",
    "passengername",
    "phonenumber",
    "phone",
    "email",
    "dateofbirth",
    "dob",
    "passport",
    "aadhar",
    "sessionid",
    "apikey",
    "secret",
    "privatekey",
    "pin",
)

REDACTED_PLACEHOLDER = "[REDACTED]"
_ALPHANUMERIC_REGEX = re.compile(r"[^a-z0-9]")

# Regex patterns for string-level redaction
_BEARER_PATTERN = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9_\-\.]+")
_CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
_URL_CREDS_PATTERN = re.compile(r"(://[^:\s]+:)[^@\s]+@")
_URL_QUERY_SECRET_PATTERN = re.compile(
    r"(?i)([?&](?:token|password|pwd|api_key|apikey|secret|key|auth|session)=)[^&\s]+"
)


def is_sensitive_key(key: str) -> bool:
    """Return True if the key name contains any sensitive substring."""
    normalized = _ALPHANUMERIC_REGEX.sub("", key.lower())
    return any(s in normalized for s in SENSITIVE_KEYS)


def redact_string(text: str) -> str:
    """Apply pattern-based redaction to free text strings (e.g. URLs, auth headers)."""
    if not text:
        return text
    
    # 1. Redact Bearer tokens
    text = _BEARER_PATTERN.sub(r"\1" + REDACTED_PLACEHOLDER, text)
    # 2. Redact embedded URL credentials (e.g. https://user:pass@host)
    text = _URL_CREDS_PATTERN.sub(r"\1" + REDACTED_PLACEHOLDER + "@", text)
    # 3. Redact query parameters containing secrets
    text = _URL_QUERY_SECRET_PATTERN.sub(r"\1" + REDACTED_PLACEHOLDER, text)
    # 4. Redact credit card sequences
    text = _CREDIT_CARD_PATTERN.sub(REDACTED_PLACEHOLDER, text)
    return text


def redact_sensitive_data(value: Any) -> Any:
    """
    Recursively redact sensitive fields and string patterns from a data structure.

    Leaves non-sensitive fields untouched and returns a new object without mutating
    the input.
    """
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and is_sensitive_key(k):
                safe[k] = REDACTED_PLACEHOLDER
            else:
                safe[k] = redact_sensitive_data(v)
        return safe

    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]

    if isinstance(value, tuple):
        return tuple(redact_sensitive_data(item) for item in value)

    if isinstance(value, str):
        return redact_string(value)

    if hasattr(value, "model_dump") and callable(value.model_dump):
        # Pydantic v2 model
        return redact_sensitive_data(value.model_dump())

    return value


def redact_http_headers(headers: dict[str, str]) -> dict[str, str]:
    """Redact sensitive HTTP header values (Authorization, Cookie, API keys)."""
    sanitized: dict[str, str] = {}
    for key, val in headers.items():
        k_lower = key.lower()
        if k_lower in {"authorization", "cookie", "set-cookie", "x-api-key", "proxy-authorization"}:
            sanitized[key] = REDACTED_PLACEHOLDER
        else:
            sanitized[key] = redact_string(val)
    return sanitized


def redact_exception(exc: BaseException) -> str:
    """Format an exception to a string with sensitive tokens and passwords redacted."""
    raw_str = f"{type(exc).__name__}: {str(exc)}"
    return redact_string(raw_str)
