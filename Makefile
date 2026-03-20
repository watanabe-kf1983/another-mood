.PHONY: ci format-check lint typecheck format

ci: format-check lint typecheck

format-check:
	uv run ruff format --check .

lint:
	uv run ruff check .

typecheck:
	uv run pyright

format:
	uv run ruff format .
