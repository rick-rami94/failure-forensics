"""Smoke test: the offline demo runs end-to-end with no API key and diagnoses the
seeded misclassification."""

from __future__ import annotations

from forensics import demo


def test_demo_runs_offline(capsys, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    demo.main()
    out = capsys.readouterr().out
    assert "misclassification" in out
    assert "eval case" in out.lower()
