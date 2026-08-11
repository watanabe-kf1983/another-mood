#!/usr/bin/env bash
# Refresh uv.lock to the latest dependency versions and open a lock-only PR.
# Merging is manual: check CI, then `gh pr merge <branch> --squash --delete-branch`.
set -euo pipefail

branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$branch" != "main" ]; then
    echo "error: run from main (current branch: $branch)" >&2
    exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
    echo "error: working tree is not clean" >&2
    exit 1
fi

uv lock --upgrade
uv sync

if git diff --quiet -- uv.lock; then
    echo "uv.lock is already fresh."
    exit 0
fi

# Safety check: this script ships uv.lock and nothing else. Anything further
# means an unexpected state; stop before it rides along into the PR.
if [ "$(git status --porcelain)" != " M uv.lock" ]; then
    echo "error: unexpected changes besides uv.lock:" >&2
    git status --porcelain >&2
    exit 1
fi

pr_branch="deps/lock-refresh-$(date -u +%Y-%m-%d)"
git checkout -b "$pr_branch"
git commit -m "Refresh uv.lock (routine dependency upgrade)" -- uv.lock
git push -u origin "$pr_branch"
gh pr create \
    --title "Refresh uv.lock to the latest dependency versions" \
    --body "Routine lock refresh: re-resolve all dependencies to the latest versions our constraints allow. No constraint changes."
git checkout main

echo
echo "PR created. After CI passes, merge with:"
echo "  gh pr merge $pr_branch --squash --delete-branch"
