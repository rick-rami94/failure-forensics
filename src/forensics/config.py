"""Environment-driven configuration.

Centralizes the few knobs the system exposes so deployments configure via environment
variables rather than code edits. Defaults match the values used throughout the codebase.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .pipeline.llm import MODEL_EXTRACT, MODEL_JUDGE


@dataclass(frozen=True)
class Settings:
    """Resolved runtime configuration."""

    extract_model: str
    judge_model: str
    trace_dir: str
    rca_threshold: int
    max_tokens: int
    log_level: str


def load_settings() -> Settings:
    """Build Settings from the environment, falling back to sensible defaults."""
    return Settings(
        extract_model=os.environ.get("FORENSICS_EXTRACT_MODEL", MODEL_EXTRACT),
        judge_model=os.environ.get("FORENSICS_JUDGE_MODEL", MODEL_JUDGE),
        trace_dir=os.environ.get("FORENSICS_TRACE_DIR", "traces"),
        rca_threshold=int(os.environ.get("FORENSICS_RCA_THRESHOLD", "3")),
        max_tokens=int(os.environ.get("FORENSICS_MAX_TOKENS", "4096")),
        log_level=os.environ.get("FORENSICS_LOG_LEVEL", "INFO"),
    )
