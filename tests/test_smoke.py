"""Phase 0 smoke tests: the package imports and the secured skeleton is wired up."""

import forensics
from forensics.pipeline import llm


def test_version() -> None:
    assert forensics.__version__ == "0.1.0"


def test_model_constants() -> None:
    # The deliberate cost/quality split is part of the design contract.
    assert llm.MODEL_EXTRACT == "claude-haiku-4-5"
    assert llm.MODEL_JUDGE == "claude-opus-4-8"
