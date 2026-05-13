from __future__ import annotations

import re

REDACTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b1[3-9]\d{9}\b"), "[REDACTED_PHONE]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"\b\d{17}[0-9Xx]\b"), "[REDACTED_ID_CARD]"),
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "[REDACTED_BANK_CARD]"),
    (re.compile(r"^(\s*Authorization\s*:\s*)[^\r\n]+", re.IGNORECASE | re.MULTILINE), r"\1[REDACTED_SECRET]"),
    (re.compile(r"^(\s*(?:Set-Cookie|Cookie)\s*:\s*).+$", re.IGNORECASE | re.MULTILINE), r"\1[REDACTED_SECRET]"),
    (re.compile(r"\b(session_?id)\s*=\s*[^\s,;]+", re.IGNORECASE), r"\1=[REDACTED_SECRET]"),
    (re.compile(r"\b(?:sk|pk|api|token|secret)[-_][A-Za-z0-9_-]{10,}\b", re.IGNORECASE), "[REDACTED_SECRET]"),
    (re.compile(r"(?i)(password|passwd|secret|token|api_key|apikey)\s*[:=]\s*[^\s,;]+"), r"\1=[REDACTED_SECRET]"),
]


def redact_sensitive_text(text: str) -> str:
    redacted = text
    for pattern, replacement in REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted