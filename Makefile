.PHONY: install test lint sast audit types check demo app

install:
	uv sync --extra dev

test:
	uv run pytest

lint:
	uv run ruff check .

sast:
	uv run bandit -c pyproject.toml -r src

audit:
	uv run pip-audit

types:
	uv run mypy src/forensics

# Everything the CI gate runs.
check: lint types sast audit test

demo:
	uv run python -m forensics.demo

app:
	uv run streamlit run src/forensics/app/main.py
