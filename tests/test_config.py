"""Tests for environment-driven configuration."""

from __future__ import annotations

from forensics import config

_ENV_KEYS = [
    "FORENSICS_EXTRACT_MODEL",
    "FORENSICS_JUDGE_MODEL",
    "FORENSICS_TRACE_DIR",
    "FORENSICS_RCA_THRESHOLD",
    "FORENSICS_MAX_TOKENS",
    "FORENSICS_LOG_LEVEL",
]


def test_defaults(monkeypatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    settings = config.load_settings()
    assert settings.extract_model == "claude-haiku-4-5"
    assert settings.judge_model == "claude-opus-4-8"
    assert settings.trace_dir == "traces"
    assert settings.rca_threshold == 3
    assert settings.max_tokens == 4096


def test_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("FORENSICS_TRACE_DIR", "/var/traces")
    monkeypatch.setenv("FORENSICS_RCA_THRESHOLD", "4")
    monkeypatch.setenv("FORENSICS_EXTRACT_MODEL", "claude-haiku-4-5")
    settings = config.load_settings()
    assert settings.trace_dir == "/var/traces"
    assert settings.rca_threshold == 4
