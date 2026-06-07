.PHONY: ci format-check lint typecheck test secrets build-projects format mirror-schemas stats

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

# Project-size overview. cloc (the de-facto line counter) is run via the
# bundled `cloc-python`, fetched and cached by `uvx` — no system install.
# `--vcs=git` with a path counts only git-tracked files under that area.
STAT_AREAS = src tests

stats:
	@uvx cloc-python --vcs=git .
	@for d in $(STAT_AREAS); do \
		echo ""; \
		echo "== $$d =="; \
		uvx cloc-python --vcs=git "$$d"; \
	done
