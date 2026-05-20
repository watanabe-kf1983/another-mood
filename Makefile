.PHONY: ci format-check lint typecheck test secrets build-projects format mirror-schemas

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
	uv run mood build dev-docs
	@for name in $$(uv run mood blueprint list --names-only); do \
		echo "uv run mood build showcase/$$name"; \
		uv run mood build showcase/$$name || exit 1; \
	done

format:
	uv run ruff format .

mirror-schemas:
	cp src/another_mood/resources/schemas/*.yaml docs/reference/schemas/
