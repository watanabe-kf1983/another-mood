.PHONY: ci format-check lint typecheck test format

ci: format-check lint typecheck test

format-check:
	uv run ruff format --check .

lint:
	uv run ruff check .

typecheck:
	uv run pyright --warnings

test:
	uv run pytest --cov --cov-fail-under=85

format:
	uv run ruff format .
