"""LLM access behind an injectable interface.

The pipeline depends on the ``LLMClient`` protocol, never on a concrete client. That
gives two things at once:

1. **Offline, key-free testing** — tests inject a scripted fake, so the whole pipeline
   runs (and CI passes) with no ``ANTHROPIC_API_KEY`` and no network.
2. **Prompt/data separation** — the protocol forces the caller to pass instructions
   (``system``) and untrusted document text (``document_text``) through *separate*
   parameters. The real client wraps the document as data inside a user message; it can
   never be concatenated into the system prompt. This is the prompt-injection mitigation
   from the threat model (see SECURITY.md), enforced by the type signature.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

# Deliberate cost/quality split:
#   - high-volume extraction & classification run on the fast, cheap model
#   - the low-volume, high-stakes LLM-as-judge (Phase 3) runs on the most capable model
MODEL_EXTRACT = "claude-haiku-4-5"
MODEL_JUDGE = "claude-opus-4-8"

DEFAULT_MAX_TOKENS = 4096

T = TypeVar("T", bound=BaseModel)


def wrap_document(text: str) -> str:
    """Wrap untrusted document text so the model treats it as data, not instructions."""
    return f"<document>\n{text}\n</document>"


class LLMClient(Protocol):
    """Structured-output LLM call. Implementations must keep ``document_text`` out of
    the system prompt — it is untrusted input."""

    def parse(
        self,
        *,
        model: str,
        system: str,
        document_text: str,
        schema: type[T],
        context: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> T: ...


class AnthropicLLM:
    """Real client. Reads ``ANTHROPIC_API_KEY`` from the environment (never hardcoded,
    never logged, never written to a trace span). Instantiating this class does not
    require the key; only ``parse`` does, so imports stay key-free."""

    def __init__(self) -> None:
        self._client: object | None = None
        # Usage from the most recent call, so tracing can record token counts.
        self.last_usage: object | None = None

    def _ensure_client(self) -> object:
        if self._client is None:
            import anthropic  # lazy: keeps the package importable without the SDK/key

            self._client = anthropic.Anthropic()
        return self._client

    def parse(
        self,
        *,
        model: str,
        system: str,
        document_text: str,
        schema: type[T],
        context: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> T:
        client = self._ensure_client()
        # Upstream step outputs (trusted, our own structured data) go in the system
        # prompt; the untrusted document goes in the user turn, wrapped as data.
        system_full = system
        if context is not None:
            system_full = (
                f"{system}\n\nUpstream pipeline context "
                f"(trusted, derived from earlier steps):\n{context}"
            )
        response = client.messages.parse(  # type: ignore[attr-defined]
            model=model,
            max_tokens=max_tokens,
            system=system_full,
            messages=[{"role": "user", "content": wrap_document(document_text)}],
            output_format=schema,
        )
        self.last_usage = getattr(response, "usage", None)
        return response.parsed_output


def get_client() -> AnthropicLLM:
    """Return the real Anthropic-backed client (requires ANTHROPIC_API_KEY at call time)."""
    return AnthropicLLM()
