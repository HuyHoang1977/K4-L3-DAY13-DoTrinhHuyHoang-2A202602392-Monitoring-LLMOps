from __future__ import annotations

import hashlib
import re

# PII patterns for scrubbing sensitive data from logs
# Order matters: more specific patterns must come before generic ones to avoid misclassification
PII_PATTERNS: dict[str, str] = {
    "email": r"(?<![\w.+-])[\w.!#$%&'*+/=?^`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}\b",
    "phone_vn": r"(?<!\d)(?:\+84|0)[ .-]?(?:3|5|7|8|9)(?:[ .-]?\d){8}(?!\d)",
    "cccd": r"\b\d{12}\b",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    # Vietnamese-specific ID patterns (must come before the generic address pattern)
    "vietnamese_id": r"\b\d{9}\b",
    "vietnamese_passport": r"\b[A-Z]\d{8}\b",
    "vietnamese_driver_license": r"\b[A-Z]{2}\d{6}\b",
    "vietnamese_health_insurance": r"\b\d{10}\b",
    # Vietnamese address: anchored on a street keyword so ordinary numerics
    # (versions, latencies, counts) are never mangled.
    "vietnamese_address": (
        r"\b(?:\d+[A-Za-z]?\s+)?"
        r"(?:đường|duong|pho|phường|phuong|quận|quan|hẻm|hem|ấp|ap)\s+"
        r"[^\s,;]+(?:\s+[^\s,;]+){0,4}"
    ),
}


def scrub_text(text: str) -> str:
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
