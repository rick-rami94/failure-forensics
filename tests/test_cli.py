"""Tests for the CLI argument parser (the live run needs a key and is not unit-tested)."""

from __future__ import annotations

from forensics.cli import build_parser


def test_parser_defaults() -> None:
    args = build_parser().parse_args(["doc.txt"])
    assert args.document == "doc.txt"
    assert args.diagnose is False
    assert args.trace_dir is None


def test_parser_flags() -> None:
    args = build_parser().parse_args(["d.txt", "--diagnose", "--trace-dir", "out"])
    assert args.diagnose is True
    assert args.trace_dir == "out"
