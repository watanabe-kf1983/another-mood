.PHONY: ci format-check lint typecheck test secrets build-projects format

ci: format-check lint typecheck test secrets build-projects

format-check:
	uv run ruff format --check .

lint:
	uv run ruff check .

typecheck:
	uv run pyright --warnings

test:
	uv run pytest --cov --cov-fail-under=90 --junitxml=reports/junit.xml --cov-report=xml:reports/coverage.xml --cov-report=html:reports/htmlcov

secrets:
	uv run pre-commit run gitleaks --all-files

build-projects:
	uv run reqs build docs-src
	uv run reqs build example-project

format:
	uv run ruff format .
