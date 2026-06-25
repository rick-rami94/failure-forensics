"""Thin wrapper around the Anthropic client.

Phase 0 scope: model constants + a client factory that reads ``ANTHROPIC_API_KEY``
from the environment (never hardcoded, never logged). Actual pipeline/judge calls are
implemented in Phase 1 (extraction/classification) and Phase 3 (LLM-as-judge).
"""

from __future__ import annotations

# Deliberate cost/quality split:
#   - high-volume extraction & classification run on the fast, cheap model
#   - the low-volume, high-stakes LLM-as-judge runs on the most capable model
MODEL_EXTRACT = "claude-haiku-4-5"
MODEL_JUDGE = "claude-opus-4-8"

# Conservative default; individual call sites override as needed.
DEFAULT_MAX_TOKENS = 4096


def get_client() -> object:
    """Return an Anthropic client.

    The SDK resolves credentials from the ``ANTHROPIC_API_KEY`` environment variable.
    The key is never passed as a literal here and never written to logs or trace spans.
    """
    import anthropic  # imported lazily so the package imports without the key present

    return anthropic.Anthropic()
