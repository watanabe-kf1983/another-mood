# Development Guide

## Conventions (Must Read)

### Development workflow

- At the start of a task, run `make ci` to confirm that the development environment and the existing code are in a healthy state
- At the start of a task, also check the freshness of uv.lock with `make upgrade-deps`. If there is a diff, the script goes as far as creating a lock-only PR (including the push); merge that PR before starting (the full convention is in [dev/dependencies.md](.another-mood/dev-docs/output/web/prose/30-dev/20-dependencies.md))

### Setup

Environment setup is in [dev/environment.md](.another-mood/dev-docs/output/web/prose/30-dev/10-environment.md).

This project manages its own documentation with Another Mood. At the start of a task, build the documentation with `mood build dev-docs` so that the specifications can be consulted. The starting point is [.another-mood/dev-docs/output/web/index.md](.another-mood/dev-docs/output/web/index.md).

The sample projects for users are in `showcase/` (the templates `starter` / `music` and so on). Build one with `mood build showcase/{name}`.

### Documentation

When you want to know something, there is one place to open per kind of information. What can be read from the code (mechanisms, current behavior) is read from the code. The documents hold only what cannot be recovered from the code (promises, intent, invariants, the course of decisions).

Where to open is decided on two axes: what it is about, and how deep. Read each row from the left, and move right only when needed:

| | Pointers and promises (read first) | Precise conditions (open when needed) | The actual state (a copy of the implementation) |
|---|---|---|---|
| User-visible behavior | `docs/reference/` | The external design in `dev-docs/design/` (behavior kept on purpose, and why) | Fixture tests |
| Internal structure | The internal structure in `dev-docs/design/` (the arrangement of layers and stages, and the promises that keep it) | Docstrings (the caller's contract), comments (handover notes) | The code |
| How development proceeds | This file | `dev-docs/dev/` | The Makefile, CI, and other configuration |

The contract is only the top-left `docs/reference/`, and breaking changes are judged by its diff. The other cells may be meant to stay stable, but they are not promises, and changing them creates no release-note obligation.

The grid holds "what is the case now". "Why it came to be" and "what to do next" do not fit in a cell, so they are read elsewhere:

- **Why it came to be** — the intent is in the same place as its object (one sentence in the relevant cell). The course that led there (comparisons, rejected options, history) is in the PR body, that is, the git log of main
- **What to do next** — the goals are in `dev-docs/concept/`, the tasks in GitHub Issues

The writer's conventions (the readers of each location, what to write and what not to, updating the indexes) are in [dev/documentation.md](.another-mood/dev-docs/output/web/prose/30-dev/30-documentation.md).

### Implementation

- In prose, `Another Mood`; in identifiers such as paths and package names, `another-mood` / `another_mood`; the command is `mood` (the notation convention is the "The product name and the self-definition" section of [dev/documentation.md](.another-mood/dev-docs/output/web/prose/30-dev/30-documentation.md))
- A library is adopted after comparing the strong candidates at the time. **Leave the reason for the choice in one sentence in a comment or docstring where the library is used, and write how they were compared in the PR body.** Version constraints are floors only (the convention is in [dev/dependencies.md](.another-mood/dev-docs/output/web/prose/30-dev/20-dependencies.md))
- Docstrings hold only contracts the API's caller needs beyond the signature (express it in the signature when possible). Comments are handover notes to future maintainers only. If the reason for the note lies in a contract or in the external design, name that section or heading

#### Package layout and dependency rules

The main players. Not exhaustive:

```
another_mood/
├── cli.py                  # CLI entry point
├── command.py              # the operation layer behind the CLI (returns BuildResult etc.)
├── config.py               # configuration
├── components/             # business logic
│   ├── shared/             #   shared foundation
│   ├── preprocess/         #   input normalization, schema interpretation, query derivation
│   ├── composer/           #   composition: data + queries → views
│   ├── generator/          #   generation: views + templates → Markdown
│   └── publish/            #   writing out the output
├── pipeline/               # orchestration: running the stages
│   └── adapters/           #   integration with external tools (Hugo, watchdog)
└── resources/              # static resources
```

Dependency direction: `cli` → `command` → `pipeline` → `components/*` → `components/shared`. Components import neither each other nor the pipeline. The role of each layer and the arrangement of the stages are in [design/Architecture](.another-mood/dev-docs/output/web/prose/20-design/20-internal/10-architecture.md).

#### Code style

- **Prefer a functional style**: comprehensions over `for` loops, `map/filter`, and so on. Arguments and return values use immutable types (`dict` → `Mapping`, `list` → `Sequence`, etc.)
- **Avoid `Any` where possible**: keep type safety with `object` and the like
- **Name after the module**: in a `source` module, `is_source_file`, `build_source`
- **Function order (newspaper style)**: public API first, helpers after. Helpers in pipeline order
- **`@dataclass` is `frozen=True`**: the purpose is to cut `__init__` boilerplate, and immutable is the default
- **Shape control flow after the logic**: a *symmetric branch*, where both arms return results of equal standing, is `if/else` (do not fold the `else` even when both arms `return`). Only an *asymmetric bail-out*, which peels off a failed precondition, an error, or an edge case at the top, is a guard clause (early `return`)
    - The `else` and the indentation are boundary information for the conditional region, so they stay even when functionally redundant (*explicit is better than implicit*)

#### Tests

- **Unit tests cover `components/`**: business logic goes there, and `cli` / `command` / `pipeline` are kept thin. Coverage (statements + branches) is held at 90% by `make ci`
- **Fixtures**: file-based, next to the module. Expected values are written in the test code
- **A test that keeps a promise names the promise it keeps**: on the first line of the docstring, write the contract's section (`Keeps: docs/reference/view.md › Missing-key placement`) or the external design's heading (`Keeps: design/View › A flattened row keeps the parent's attributes and puts the element under as:`)
    - Only the test that fails first when the promise is broken needs to name it; exhaustiveness is not required. When changing a section of the contract or the external design, grep for the section name and fix the tests that name it

#### Checking by hand

To check a template change on a real run, bring up a preview with `mood watch <project_dir> --port <port>`, and look at it with the Playwright MCP if needed (where the working files go is the "Playwright's working files" section of [dev/environment.md](.another-mood/dev-docs/output/web/prose/30-dev/10-environment.md)).

### Pull requests

The PR body becomes the squash commit body on main as it is (the commit messages on the branch do not survive). The summary of the change and the background and course of the design decisions go here. The title appears in the release notes that users read, so put no internal vocabulary in it.

A PR you want among the highlights at the top of the release notes writes a trailer on one line, starting at the beginning of a line, at the end of the PR body. The kind is `breaking` / `feature` / `fix`:

    Release-Highlight: <kind>

Only `breaking` is mandatory, and it comes with a `## Breaking change` section. How to choose the kind, the obligations of a PR with a breaking change (a supported format generation dropping out, or breaking a user-facing contract such as the CLI), and the release procedure are in [dev/release.md](.another-mood/dev-docs/output/web/prose/30-dev/40-release.md).

## Documentation (Reference)

The documentation is read at `.another-mood/dev-docs/output/web/`.

- [index.md](.another-mood/dev-docs/output/web/index.md) — specifications and design
- [concept/product.md](.another-mood/dev-docs/output/web/prose/10-concept/10-product.md) — the product vision
- [dev/documentation.md](.another-mood/dev-docs/output/web/prose/30-dev/30-documentation.md) — writing documentation (the readers and conventions of each location, the notation of the product name and the self-definition)
