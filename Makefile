.PHONY: ci format-check lint format

ci: format-check lint

format-check:
	uv run ruff format --check .

lint:
	uv run ruff check .

format:
	uv run ruff format .
