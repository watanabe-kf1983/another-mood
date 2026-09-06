#!/usr/bin/env bash
# Refresh uv.lock to the latest dependency versions and open a lock-only PR.
# Merging is manual: check CI, then `gh pr merge <branch> --squash --delete-branch`.
set -euo pipefail

if [ -n "$(git status --porcelain)" ]; then
    echo "error: working tree is not clean" >&2
    exit 1
fi

original=$(git rev-parse --abbrev-ref HEAD)
pr_branch="deps/lock-refresh-$(date -u +%Y-%m-%d)"
if git show-ref --verify --quiet "refs/heads/$pr_branch"; then
    echo "error: branch $pr_branch already exists" >&2
    exit 1
fi

git fetch origin
git switch --detach origin/main

uv lock --upgrade
uv sync

if git diff --quiet -- uv.lock; then
    echo "uv.lock is already fresh."
    git switch "$original"
    exit 0
fi

# Safety check: this script ships uv.lock and nothing else. Anything further
# means an unexpected state; stop before it rides along into the PR.
if [ "$(git status --porcelain)" != " M uv.lock" ]; then
    echo "error: unexpected changes besides uv.lock:" >&2
    git status --porcelain >&2
    echo "left on detached origin/main for inspection (was on $original)" >&2
    exit 1
fi

git switch -c "$pr_branch"
git commit -m "Refresh uv.lock (routine dependency upgrade)" -- uv.lock
git push -u origin "$pr_branch"
gh pr create \
    --title "Refresh uv.lock to the latest dependency versions" \
    --body "Routine lock refresh: re-resolve all dependencies to the latest versions our constraints allow. No constraint changes."
git switch "$original"

echo
echo "PR created. After CI passes, merge with:"
echo "  gh pr merge $pr_branch --squash --delete-branch"
