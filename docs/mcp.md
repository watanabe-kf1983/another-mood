# Using Another Mood with AI agents (MCP)

Another Mood ships an MCP server (`mood-mcp`) that exposes the same
operations as the `mood` CLI to AI agents.

Another Mood is typically used in an iterative loop — read your
schema and content, edit sources, call `build`, inspect the generated
output to verify changes. Letting an agent run this loop requires it
to have filesystem access to your project.

## What the agent gets

Each `mood` CLI command has an MCP counterpart, except `mood watch`:

| CLI command | MCP tool | Purpose |
|---|---|---|
| `mood init` | `init` | Initialize a project at `project_dir` from the `starter` blueprint |
| `mood blueprint list` | `list_blueprints` | List the bundled blueprints (sample projects) |
| `mood blueprint apply` | `apply_blueprint` | Apply the named blueprint by copying its sources into `project_dir` |
| `mood build` | `build` | Run a one-shot build of `project_dir`, generating Markdown and HTML and returning the result |
| `mood docs list` | `list_docs` | List bundled documentation as MCP resource links |
| `mood docs read` | `read_doc` | Read a bundled document by its `docs://` URI |
| `mood watch` | — | Watch for file changes, rebuild incrementally, and serve a live preview |

## Configure your client

This section covers only **coding agents** — agents with built-in
filesystem access to your project:

- **Claude Code**
- **VS Code Copilot Chat**

Chat-style agents (e.g., Claude Desktop's Chat tab, ChatGPT Desktop)
can still call this server's tools, but to edit project sources you
would also need a separate filesystem MCP server such as
[`@modelcontextprotocol/server-filesystem`][fs-mcp]; that setup is out
of scope here.

[fs-mcp]: https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem

### Claude Code

```bash
claude mcp add --transport stdio another-mood -- mood-mcp
```

The default scope registers the server for your current project only.
Add `--scope user` to make it available in all your projects, or
`--scope project` to write a shared `.mcp.json` at the project root
that you can commit:

```json
{
  "mcpServers": {
    "another-mood": {
      "command": "mood-mcp"
    }
  }
}
```

### VS Code Copilot Chat

In `.vscode/mcp.json` (project-local):

```json
{
  "servers": {
    "another-mood": {
      "type": "stdio",
      "command": "mood-mcp"
    }
  }
}
```

For a user-global registration, run **MCP: Open User Configuration**
from the command palette and add the same `"another-mood"` block to
the file it opens.
