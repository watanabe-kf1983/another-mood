# Another Mood

A processor of source-based databases, keeping related documents in sync.

Software specifications, product catalogs, maintenance manuals, training materials — documents like these keep describing the same things in different places. For instance, in a software specification, a single screen is listed in the screen inventory, named as the destination of other screens' transitions, crossed with tables in a CRUD matrix, and cited by the requirements. Rename it and every one of those mentions has to change with it; miss one, and the specification contradicts itself.

Another Mood keeps such documents consistent. You write the data once as **sources** — YAML records and Markdown prose — alongside templates that say how pages are built from them. Edit a source, rebuild, and every page derived from it regenerates together.

To see it at work, browse a [requirements specification and a design document](https://watanabe-kf1983.github.io/another-mood/showcase/system-dev-docs-en/web/index.html) for a small inventory system, both built from one set of sources, with the design document linking into the requirements throughout.

## Install

Requires Python 3.12 or later.

```bash
pipx install another-mood
```

If you use [uv](https://docs.astral.sh/uv/), `uv tool install` takes the same argument and fetches a suitable Python for you. Either way you get the `mood` command on your PATH.

## Quick start

```bash
mood init my-project
mood build my-project
```

`mood init` scaffolds a small sample database; `mood build` turns it into Markdown and HTML under `.another-mood/my-project/`.

## Documentation

[User guide](https://github.com/watanabe-kf1983/another-mood/blob/main/docs/index.md) — concepts and walkthrough, and per-feature reference. It ships with the package too, so a coding agent can read it with `mood docs read` without leaving your project.

[Showcases](https://watanabe-kf1983.github.io/another-mood/) — the sample projects, built and hosted, each linked to its sources.

## Status

Another Mood is complete for my own use and is now passively maintained (as of 2026-11). I intend to respond to requests and issues, but can't promise to. Forks are welcome.
