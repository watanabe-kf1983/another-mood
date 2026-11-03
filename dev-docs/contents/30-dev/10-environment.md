# Development Environment

What development needs, how to install it, and what the environment does automatically. The list of what is installed is not kept here: the lineup of tools and the purpose of each are in the comments of `.devcontainer/devcontainer.json` and `.vscode/`, and the MCP servers in `.mcp.json`.

## Supported Python versions

The supported floor is **3.12** (`requires-python` in `pyproject.toml`), and development is on **3.13** (`.python-version`). CI runs a matrix on both ends.

The floor is 3.12 so that the install instructions hold. The system Python of Ubuntu 24.04 LTS (supported until 2029) is 3.12; with a floor of 3.13, `pipx install` would not go through cleanly, and users would be forced onto uv, which procures its own interpreter.

It is not lowered further because PEP 695 syntax (the `type` statement, the new generics) is used widely, and 3.12 is the syntactic floor.

## Setup

The DevContainer is recommended. Install the Dev Containers extension in VS Code, open the repository, and run "Reopen in Container"; postCreateCommand installs the tools.

Without the DevContainer, read `.devcontainer/devcontainer.json` and install by hand what the features and postCreateCommand install (the Python version is above). If you do not use Claude Code and the MCP servers, all you need is Python + [uv](https://docs.astral.sh/uv/), make, and the GitHub CLI.

In either case, finish with the common steps:

```bash
uv sync                      # install the Python dependencies (ruff, pyright, pytest, ...)
uv run pre-commit install    # enable the pre-commit hook
make ci                      # run every check to confirm the environment
```

## When the checks run

Where each column is configured:

- IDE — `.vscode/settings.json`
- Claude Code — `.claude/settings.json` (PostToolUse hook)
- Git commit — `.pre-commit-config.yaml`
- CI — `ci.yml` (runs `make ci` as a matrix on both ends of the supported Python versions; the range and the reason are in "Supported Python versions" above)

| Check | IDE (on save) | Claude Code (after edit) | Git commit | CI |
|---|---|---|---|---|
| Format | ✓ | ✓ | ✓ | ✓ (check) |
| Lint | | | | ✓ |
| Type check | | | | ✓ |
| Tests + coverage | | | | ✓ |
| Secret detection | | | ✓ | ✓ |
| Paragraph length ([Writing documentation](30-documentation.md#paragraph-length)) | | | | ✓ |
| Build (dev-docs / pages / showcase) | | | | ✓ |

## Playwright's working files

The working files of the Playwright MCP server are gathered under `.playwright-mcp/`, which is already in `.gitignore`. The MCP server writes page snapshots and console logs there automatically.

For screenshots, pass `.playwright-mcp/<name>.png` as the `filename` of `browser_take_screenshot` (by default they land directly under the cwd and make a mess).
