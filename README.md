# Another Mood

A processor of source-based databases, keeping related documents in sync.

Requirements specifications, product catalogs, maintenance manuals, training materials — documents like these keep describing the same things in different shapes. Introduce one new thing and you have to chase the same edit through several files, miss one, and let the set drift out of sync.

Another Mood keeps that set consistent. You write the data once as **sources** — YAML records and Markdown prose — alongside templates that say how pages are built from them. Edit a source, rebuild, and every page derived from it regenerates together.

## Install

Requires Python 3.12 or later.

```bash
pipx install git+https://github.com/watanabe-kf1983/another-mood.git
```

If you use [uv](https://docs.astral.sh/uv/), `uv tool install` takes the same argument and fetches a suitable Python for you. Either way you get the `mood` command on your PATH, along with `mood-mcp` for coding agents.

## Quick start

```bash
mood init my-project
mood build my-project
```

`mood init` scaffolds a small sample database; `mood build` turns it into Markdown and HTML under `.another-mood/my-project/`.

## Documentation

[User guide](https://github.com/watanabe-kf1983/another-mood/blob/main/docs/index.md) — concepts and walkthrough, per-feature reference, and how to give coding agents the same operations over MCP. It ships with the package too, so an agent can read it through the MCP server without leaving your project.
