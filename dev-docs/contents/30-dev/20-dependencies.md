# Dependency Management

The conventions for how dependency versions are declared, and when and how they are updated.

## Principles for constraints

- The dependency declarations in `pyproject.toml` are floors only (`>=`). Upper bounds (caps) are not written as a rule
- A cap is limited to a stopgap "when a release that breaks us is known to exist". **A cap always comes with its removal condition (the corresponding migration task)**

Background: mood is a tool distributed to users, installed into an isolated venv by `uv tool install`, and users do not receive uv.lock; they always resolve to the latest. Without caps, a dependency's vulnerability fix flows to users automatically the moment it is released (self-healing). A cap dams this self-healing, so no permanent cap is placed.

## Three instruments

| Instrument | What it looks at | Trigger | What it protects | Response |
|---|---|---|---|---|
| Fresh dependency check | The environment pyproject resolves to at the latest versions | Weekly | Users (a proxy for the resolution a fresh install receives) | A cap (with removal condition) or a fix |
| Dependabot security updates (version updates are not used) | uv.lock + pyproject | When a CVE is published | The development environment and CI (the only place that runs on the lock) | Merge the bump PR immediately |
| `make upgrade-deps` | The freshness of uv.lock | At the start of a task | Staleness of the development environment; keeping lock diffs small | A lock-only PR |

- The Fresh dependency check deliberately takes on the role of stepping on a malicious release (the canary). Its environment is a disposable VM, and writes to the Actions cache are blocked (`enable-cache: false` in fresh-deps.yml), so the damage surface is limited
- Dependabot version updates (periodic bump PRs) are not used. The bot does not solve the neglect problem (a human still has to merge), and because its own commits keep evading the 60-day automatic suspension of scheduled workflows, it keeps mutating main unattended even after development pauses
- Skipping `make upgrade-deps` does not harm correctness (correctness is secured weekly by the Fresh dependency check). The value of the ritual is pulling the alarm (measuring again yourself each time you start developing, instead of waiting for a notification) and keeping diffs small

## The ritual at the start of a task

`make upgrade-deps` re-resolves uv.lock to the latest the constraints allow. It can be run from any branch as long as the working tree is clean; the resolution is done on top of `origin/main`, and it returns to the branch you were on.

- No diff → start the task as is
- A diff → the script creates a lock-only PR on a `deps/lock-refresh-<date>` branch. Confirm CI is green, merge with `gh pr merge <branch> --squash --delete-branch`, and then start. If red, respond with a fix or a cap with removal condition
- **A lock update never rides along in a feature PR.** Keep the shape in which the cause of a regression can be separated into the feature change or the dependency bump
- When a specific version is needed in the middle of a task, `uv lock --upgrade-package <name>` may be used directly
