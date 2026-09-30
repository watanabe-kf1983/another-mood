.PHONY: ci format-check lint typecheck test secrets build-projects pages format mirror-schemas stats upgrade-deps

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
	uv run mood build pages
	@for name in $$(uv run mood blueprint list --names-only); do \
		echo "uv run mood build showcase/$$name"; \
		uv run mood build showcase/$$name || exit 1; \
	done

# The GitHub Pages site under _site/: the gallery page at the root and every
# showcase under showcase/<name>/. The gallery is one page, lifted out of its
# build's edition directory so that visitors land on it rather than on the
# cover that a build puts at its root.
pages:
	rm -rf _site && mkdir _site
	uv run mood build pages --var git_commit_id=$$(git rev-parse --short HEAD)
	cp .another-mood/pages/site/default/index.html _site/index.html
	@for name in $$(uv run mood blueprint list --names-only); do \
		echo "uv run mood build showcase/$$name --site-dir _site/showcase/$$name"; \
		uv run mood build showcase/$$name --site-dir _site/showcase/$$name || exit 1; \
	done

upgrade-deps:
	scripts/upgrade_deps.sh

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
