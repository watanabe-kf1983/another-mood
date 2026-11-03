# Release Flow

A release is fixing the version and pushing a git tag. main stays a trunk, and "merging to main" is not "releasing". Every judgment and description a release needs is put in place at PR time, and the release itself is only their consumption (read, tag, paste); there is no branching of the procedure by role.

## Versioning

- The one source of truth for the version declaration is the git tag. The version in pyproject is derived from the tag by hatch-vcs. There is no bump-commit step
- The manifests of showcase and dev-docs do not write `minimum_version`. They grow together with HEAD in the same repository, so they may depend on unreleased features. The honest floor (the next version) is greater than the dev version, so it would fail the gate. Writing an existing version would be a false declaration, and following each release would reinvent the bump commit
- Release tags have the form `vN.N.N` (no hyphen). The trigger condition of the release workflow and hatch-vcs's version derivation (the describe filter in pyproject) share this form. Marker tags that are not releases go in the `milestone/` namespace
- A release's kind is one of three values: breaking / compatible feature / compatible fix. Breaking is the umbrella for two kinds:
    - **A format break** — a supported generation dropping out (old_supported − new_supported ≠ ∅. **Adding** a generation is itself not a break. Generation management belongs to [Manifest](../20-design/10-external/20-manifest.md))
    - **A tool break** — breaking the tool's user-facing contract, such as the CLI
- The mapping from kind to version digit. Only this table holds the digit correspondence; every other description speaks in kind words:

  | Kind | 0.x era | 1.0.0 and later |
  |---|---|---|
  | Breaking | 0.MINOR+1 | MAJOR+1 |
  | Compatible feature | 0.x.PATCH+1 | MINOR+1 |
  | Compatible fix | 0.x.PATCH+1 | PATCH+1 |

- When to release is discretionary. 1.0.0 is cut at launch
- Once a breaking PR is merged, no compatible release can be cut from main thereafter. "Merge when you are ready for the next release to be a breaking one." If demand for a fix to an old series actually arises, cut a backport branch from the old tag and cherry-pick (`git switch -c release-<series> <the series' last tag>`)

## Discipline on the PR side

The PR body becomes the squash commit body on main, and the commit messages on the branch do not survive. For this, the repository settings allow squash merges only, and use the PR body as the squash body.

Allowing merge commits or rebases would mean the bodies of PRs merged that way never enter history, and the background of design decisions and the trailers would be silently lost.

No internal vocabulary in PR titles. The title goes as is into the auto-generated ledger and also serves as the highlight's heading; both are surfaces users read.

### The Release-Highlight trailer

A PR you want among the highlights at the top of the release notes writes one line, starting at the beginning of a line, at the end of the PR body:

    Release-Highlight: fix

- The key is `Release-Highlight`, and the kind is one of three values: breaking / feature / fix. Nothing but the kind is written (the heading is served by the PR title). Always at the beginning of a line (the release procedure collects it by a line-anchored grep)
- Only breaking is mandatory. feature / fix are discretionary
- The criterion for feature vs fix is "**did the set of promises in docs/reference grow or shrink**". If it did, feature (documenting existing behavior for the first time is feature too: it brings something from outside the contract inside). Restating, clarifying, or restructuring the same promises is fix or below. The judgment is semantic, not machine-checked; it is the author's
- One PR may declare several kinds (one per line)

### Description sections

Description beyond the PR title is written in the PR body as sections. There is one heading per group of kinds, corresponding to a section of the release notes. This division makes the PR's writing surface and the Release's sections one-to-one, so that a lint can mechanically catch a mismatch between section and kind:

| Heading | Accompanying kind | Written? | Section in the Release |
|---|---|---|---|
| `## Breaking change` | breaking | Mandatory | Breaking changes |
| `## Release highlight` | feature / fix | Discretionary | Highlights |

- Free-form English for users, with no internal vocabulary. Copied as is to the top of the Release at release time
- `## Breaking change` holds a summary of the migration and a pointer to the migration steps in docs
- One PR may have both. For a PR that brings a feature at the cost of a break, write the migration in the former and what is newly possible in the latter, declaring both breaking and feature

### Obligations of a breaking PR

A breaking PR (a format break or a tool break alike) includes all of the following in itself. Only the trailer and the `## Breaking change` section are written in the PR body; the rest is repository content under review:

1. **Migration steps and more (format breaks only)** — write the user-facing migration steps in docs (the source of truth is docs, not the release notes; the location is settled at the first breaking change)
   - Plus the full set of follow-ups around the generation number: the supported set in the code, the scaffold output, the manifests of showcase / dev-docs. A missed update is caught by the existing CI, since the builds and tests are pinned to the generation number
2. **The `Release-Highlight: breaking` trailer and the `## Breaking change` section** — in the PR body, in the format above

### Automatic checks by lint

Whenever a PR is opened, reopened, has its body edited, or is pushed, the `PR lint` workflow runs and looks only at the mechanically decidable part of the discipline above. It sticks to cross-checking existing signals, and makes no semantic judgment of "whether the content is breaking".

There are two outcomes: a clear-cut violation of format or consistency fails; the fit between the diff and the trailers is flagged by a non-blocking sticky comment. The correspondence between description sections and kinds (the table above) belongs to consistency, and a mismatch in either direction fails.

## Release procedure

One procedure regardless of kind. There is no commit to main. The aim is a lightness that runs in 5 minutes. The only value entered by hand is the next version number; the previous tag is derived (leaving no room for a typo).

### 1. Derive the next version number

Derive the previous tag (take it before tagging; afterwards it would point at itself), collect the kinds since, and pass the highest through the mapping table.

```bash
PREV=$(git describe --tags --abbrev=0 --match 'v[0-9]*.[0-9]*.[0-9]*' --exclude '*-*')
git log "$PREV"..HEAD --format=%B | grep -E '^Release-Highlight: '
```

As a cross-check, read through once and look for missing declarations (a missed record of a break is prevented by the PR-side discipline; what is caught here is at most a forgotten feature kind).

```bash
git log "$PREV"..HEAD --oneline
```

### 2. Tag and push

Put the derived number in `NEW`. The tag is lightweight: nothing reads a tag object, and the release description and date are held by the GH Release (switch to annotated if signing is introduced).

```bash
NEW=vX.Y.Z
git tag "$NEW" && git push origin "$NEW"
```

Confirm the workflow runs to completion (build → PyPI publish → automatic creation of the GH Release).

### 3. Add the highlights to the top of the GH Release

If the collection is empty, nothing. The material is the following output. If the line wrapping of long bodies is a nuisance, the originals are on the PR pages (the #number at the end of the title).

```bash
git log "$PREV".."$NEW" --grep='^Release-Highlight: ' --format='=== %s%n%n%b'
```

Place the following two sections at the top, in this order. A section with no matching PR is omitted. Within each section, in PR number order:

- `## Breaking changes` — PRs that declared breaking. Make the PR title a `### Title (#number)` heading, followed by the body of the `## Breaking change` section
- `## Highlights` — PRs that declared feature / fix. A PR with a `## Release highlight` section gets the same `###` heading and body; a PR without one becomes a one-line list item of its title (giving a heading to an item with no body makes an empty section)
  - When there are `###` items, put the list under `### Other highlights` (otherwise it looks like part of the preceding item)

Relative links in the bodies cannot be resolved from the Release page, so rewrite them to tag-pinned absolute URLs (`https://github.com/<owner>/<repo>/blob/<NEW>/docs/...`).

To add them from the CLI, take out the auto-generated part, prepend the highlights, and put it back. The body is replaced wholesale, so never write it back without reading it. Run `gh` inside the repository (moving the working directory fails with `not a git repository`).

```bash
gh release view "$NEW" --json body --jq .body > /tmp/notes.md
# prepend the highlights to /tmp/notes.md
gh release edit "$NEW" --notes-file /tmp/notes.md
```
