"""Secret / PII redaction applied to span content *before* it is persisted.

The trace store is a sensitive data sink: captured prompts and step I/O can contain
secrets or PII lifted from input documents. This module scrubs known patterns so they
never reach disk. It is pattern-based and best-effort — defense in depth, not a guarantee
(see SECURITY.md). ``test_redaction.py`` asserts that planted secrets never appear in any
persisted file.
"""

from __future__ import annotations

import re

# (label, pattern) — order matters: more specific patterns run before generic ones.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "PEM_PRIVATE_KEY",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
    ("ANTHROPIC_KEY", re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}")),
    ("OPENAI_KEY", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("AWS_ACCESS_KEY", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("BEARER_TOKEN", re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{8,}")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    (
        "SECRET_ASSIGNMENT",
        re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd|pwd)\b\s*[:=]\s*\S+"),
    ),
]


def redact(text: str | None) -> str | None:
    """Return ``text`` with known secret/PII patterns replaced by ``[REDACTED:LABEL]``."""
    if text is None:
        return None
    result = text
    for label, pattern in _PATTERNS:
        result = pattern.sub(f"[REDACTED:{label}]", result)
    return result


def redact_obj(obj: object) -> object:
    """Recursively redact strings inside dicts/lists; pass other types through."""
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {key: redact_obj(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(value) for value in obj]
    return obj
