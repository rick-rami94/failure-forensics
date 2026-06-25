"""Phase 2 security tests — redaction.

Two layers:
1. Unit tests that each pattern is scrubbed.
2. An end-to-end proof that secrets planted in a document never appear in ANY file the
   trace store writes to disk.

Secret-shaped values are assembled at runtime from harmless fragments, so no secret
literal is ever committed to the repo (and nothing for gitleaks to flag).
"""

from __future__ import annotations

from pathlib import Path

from forensics.tracing import redaction
from forensics.tracing.instrument import run_traced
from forensics.tracing.store import TraceStore

# Assembled at runtime — these fragments are individually meaningless, so the repo
# never contains a complete secret-shaped literal.
AWS_KEY = "AKIA" + "IOSFODNN7" + "EXAMPLE"
ANTHROPIC_KEY = "sk-" + "ant-" + "A1B2C3D4E5F6G7H8"
BEARER = "Bearer " + "abcdef0123456789"
SSN = "123" + "-45-" + "6789"
EMAIL = "alice" + "@example.com"
PLANTED = [AWS_KEY, ANTHROPIC_KEY, BEARER, SSN, EMAIL]


def test_each_pattern_is_redacted() -> None:
    assert redaction.redact(AWS_KEY) == "[REDACTED:AWS_ACCESS_KEY]"
    assert redaction.redact(ANTHROPIC_KEY) == "[REDACTED:ANTHROPIC_KEY]"
    assert redaction.redact(SSN) == "[REDACTED:SSN]"
    assert "[REDACTED:BEARER_TOKEN]" in redaction.redact(f"auth: {BEARER}")
    assert "[REDACTED:EMAIL]" in redaction.redact(f"contact {EMAIL} please")
    assert "[REDACTED:SECRET_ASSIGNMENT]" in redaction.redact("api_key = hunter2value")


def test_redact_is_none_safe() -> None:
    assert redaction.redact(None) is None


def test_redact_obj_walks_structures() -> None:
    out = redaction.redact_obj({"a": AWS_KEY, "b": [EMAIL, 7], "c": 1})
    assert out == {"a": "[REDACTED:AWS_ACCESS_KEY]", "b": ["[REDACTED:EMAIL]", 7], "c": 1}


def _all_persisted_bytes(root: Path) -> bytes:
    blob = b""
    for path in Path(root).rglob("*"):
        if path.is_file():
            blob += path.read_bytes()
    return blob


def test_planted_secrets_never_reach_disk(scripted_llm, tmp_path) -> None:
    from forensics.pipeline import steps

    poisoned_text = (
        "Access review export.\n"
        f"AWS key {AWS_KEY}\nAnthropic key {ANTHROPIC_KEY}\n"
        f"Authorization: {BEARER}\nSSN {SSN}\nOwner {EMAIL}\n"
    )
    document = steps.intake(doc_id="poison-1", source="unit-test", text=poisoned_text)

    store = TraceStore(root=tmp_path)
    run_traced(document, scripted_llm, store=store)

    persisted = _all_persisted_bytes(tmp_path)
    for secret in PLANTED:
        assert secret.encode() not in persisted, f"secret leaked to disk: {secret!r}"

    # And confirm redaction actually fired (markers are present in the trace JSON).
    assert b"[REDACTED:" in persisted
