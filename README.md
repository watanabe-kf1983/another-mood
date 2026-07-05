# Another Mood

A processor of source-based databases, keeping related documents in sync. Generates structured documents from related sources (YAML / Markdown) and templates.

## Quick Start

```bash
uv sync
uv run mood build showcase/music
```

Output is written to `.another-mood/showcase/music/output/`.

## Status

Under development (private).

For design decisions and background, see [background/product.md](dev-docs/contents/10-background/10-product.md).

## Documentation

- [docs/guides.md](docs/guides.md) — User guide
- [docs/mcp.md](docs/mcp.md) — Using Another Mood with AI agents (MCP)
- [DEVELOPMENT.md](DEVELOPMENT.md) — Developer guide
- [showcase/music/](showcase/music/) — Example project
