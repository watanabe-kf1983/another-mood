"""CLI entry point."""

import sys
from collections.abc import Callable
from datetime import datetime
from logging import INFO, basicConfig
from pathlib import Path

import typer

from another_mood import command
from another_mood.command import BuildResult
from another_mood.components.scaffold.blueprints import ScaffoldResult
from another_mood.config import ConfigValidationError, ProjectConfig

app = typer.Typer()
blueprint_app = typer.Typer(help="Manage built-in blueprints (sample projects).")
app.add_typer(blueprint_app, name="blueprint")
docs_app = typer.Typer(help="Inspect bundled documentation (also exposed via MCP).")
app.add_typer(docs_app, name="docs")


@app.callback()
def callback() -> None:
    """Another Mood: a processor of source-based databases, keeping related documents in sync."""


def _load_config(**kwargs: object) -> ProjectConfig:
    """Build and verify ProjectConfig, exiting cleanly on validation failure."""
    config = ProjectConfig(**kwargs)  # type: ignore[arg-type]
    try:
        config.verify()
    except ConfigValidationError as exc:
        print(str(exc), file=sys.stderr)
        raise typer.Exit(1) from exc
    return config


@blueprint_app.command("list")
def list_blueprints() -> None:
    """List available blueprints."""
    for blueprint in command.list_blueprints():
        print(blueprint.name)
        print(f"  {blueprint.description}")


def _render_scaffold(result: ScaffoldResult) -> None:
    """Print created / skipped lines for a scaffold pass."""
    for path in result.created:
        print(f"  created: {path}", file=sys.stderr)
    for path in result.skipped:
        print(f"warning: skipped (already exists): {path}", file=sys.stderr)


@blueprint_app.command("apply")
def apply_blueprint(
    name: str = typer.Argument(help="Blueprint name."),
    project_dir: str = typer.Argument(help="Project directory."),
) -> None:
    """Apply a blueprint into a project directory."""
    available = [b.name for b in command.list_blueprints()]
    if name not in available:
        print(
            f"unknown blueprint: {name!r} (available: {', '.join(available)})",
            file=sys.stderr,
        )
        raise typer.Exit(1)
    target = Path(project_dir)
    print(f"Scaffolding {target}/ from blueprint: {name}", file=sys.stderr)
    result = command.apply_blueprint(name, target)
    _render_scaffold(result)
    if not result.all_written:
        raise typer.Exit(1)


@docs_app.command("list")
def list_docs() -> None:
    """List bundled documentation entries with their `docs://` URIs."""
    for entry in command.list_docs():
        print(entry.uri)
        print(f"  {entry.description}")


@docs_app.command("read")
def read_doc(
    uri: str = typer.Argument(
        help="Doc URI from `mood docs list`, e.g. docs://reference/cli.md"
    ),
) -> None:
    """Print the contents of a bundled doc by its `docs://` URI."""
    known_uris = {entry.uri for entry in command.list_docs()}
    if uri not in known_uris:
        print(
            f"unknown doc URI: {uri!r} (run `mood docs list` to see available URIs)",
            file=sys.stderr,
        )
        raise typer.Exit(1)
    print(command.read_doc(uri))


@app.command()
def init(project_dir: str = typer.Argument(help="Project directory")) -> None:
    """Initialize a new project. Shortcut for `mood blueprint apply starter`."""
    target = Path(project_dir)
    print(f"Scaffolding {target}/ from default blueprint", file=sys.stderr)
    result = command.init(target)
    _render_scaffold(result)
    if not result.all_written:
        raise typer.Exit(1)


_BUILD_MESSAGES = {
    (True, True): "Build successfully completed",
    (True, False): "Build failed",
    (False, True): "Files updated, and re-build successfully completed",
    (False, False): "Files updated, but re-build failed",
}


def _build_listener() -> Callable[[BuildResult], None]:
    """Return an on_report listener that prints the iteration result to stderr."""
    first = True

    def on_report(result: BuildResult) -> None:
        nonlocal first
        msg = _BUILD_MESSAGES[first, not result.has_errors()]
        first = False
        print(f"{msg} at {datetime.now():%H:%M:%S}.", file=sys.stderr, flush=True)

    return on_report


@app.command()
def build(
    project_dir: str = typer.Argument(help="Project directory"),
    out_dir: str | None = typer.Option(
        None, "--out-dir", help="Published output directory."
    ),
    render_dir: str | None = typer.Option(
        None, "--render-dir", help="Hugo render directory."
    ),
) -> None:
    """Build the project to Markdown and rendered HTML."""
    overrides: dict[str, Path] = {}
    if out_dir is not None:
        overrides["out_dir"] = Path(out_dir)
    if render_dir is not None:
        overrides["render_dir"] = Path(render_dir)
    config = _load_config(project_dir=Path(project_dir), **overrides)
    result = command.build(config, on_report=_build_listener())
    if result.has_errors():
        raise SystemExit(1)


@app.command()
def watch(
    project_dir: str = typer.Argument(help="Project directory"),
    port: int = typer.Option(5077, help="Preview server port"),
) -> None:
    """Watch for changes and rebuild automatically with live preview."""
    config = _load_config(project_dir=Path(project_dir), port=port)
    with command.watch(config, on_report=_build_listener()) as shutdown:
        try:
            print(
                f"Server running at http://localhost:{config.port}/\n"
                f"  Reports: http://localhost:{config.port}/reports/",
                file=sys.stderr,
                flush=True,
            )
            print("Press Ctrl+C to stop.", file=sys.stderr, flush=True)
            shutdown.wait()
        except KeyboardInterrupt:
            pass


def main() -> None:
    basicConfig(stream=sys.stderr, format="%(message)s", level=INFO)
    app()
