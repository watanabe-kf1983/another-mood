"""CLI entry point."""

import socket
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

# add_completion=False drops typer's `--install-completion` / `--show-completion`
# options. Shell completion is rarely set up for a `uv tool install`-distributed
# CLI, and the two options only clutter the `mood --help` surface that readers
# (humans and coding agents alike) scan to discover commands.
app = typer.Typer(add_completion=False)
blueprint_app = typer.Typer(help="Manage built-in blueprints (sample projects).")
app.add_typer(blueprint_app, name="blueprint")
docs_app = typer.Typer(help="Inspect bundled documentation (also exposed via MCP).")
app.add_typer(docs_app, name="docs")


@app.callback()
def callback() -> None:
    """Another Mood: a processor of source-based databases, keeping related documents in sync.

    Before authoring or editing schema, queries, or templates, read the spec:
    run `mood docs list`, then `mood docs read <uri>` for the relevant page.
    """


def _load_config(**kwargs: object) -> ProjectConfig:
    """Build and verify ProjectConfig, exiting cleanly on validation failure.

    ``None`` kwargs are dropped so callers can forward typer Options
    (``--flag`` defaulted to ``None``) directly without a per-flag
    ``if x is not None`` dance.
    """
    fields = {k: v for k, v in kwargs.items() if v is not None}
    config = ProjectConfig(**fields)  # type: ignore[arg-type]
    try:
        config.verify()
    except ConfigValidationError as exc:
        print(str(exc), file=sys.stderr)
        raise typer.Exit(1) from exc
    return config


@blueprint_app.command("list")
def list_blueprints(
    names_only: bool = typer.Option(
        False,
        "--names-only",
        help="Print only blueprint names, one per line (machine-readable).",
    ),
) -> None:
    """List the bundled blueprints (sample projects)."""
    for blueprint in command.list_blueprints():
        print(blueprint.name)
        if not names_only:
            print(f"  {blueprint.description}")


def _render_scaffold(result: ScaffoldResult) -> None:
    """Print created / skipped lines for a scaffold pass."""
    for path in result.created:
        print(f"  created: {path}", file=sys.stderr)
    for path in result.skipped:
        print(f"warning: skipped (already exists): {path}", file=sys.stderr)


@blueprint_app.command("apply")
def apply_blueprint(
    name: str = typer.Argument(help="Blueprint name"),
    project_dir: str = typer.Argument(help="Project directory"),
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
        None, "--out-dir", help="Published output directory"
    ),
    render_dir: str | None = typer.Option(
        None, "--render-dir", help="Hugo render directory"
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Fail the build if any warning is reported.",
    ),
) -> None:
    """Build the project to Markdown and rendered HTML."""
    config = _load_config(
        project_dir=Path(project_dir),
        out_dir=out_dir,
        render_dir=render_dir,
    )
    result = command.build(config, on_report=_build_listener())
    if result.has_errors() or (strict and result.has_warnings()):
        raise SystemExit(1)


@app.command()
def watch(
    project_dir: str = typer.Argument(help="Project directory"),
    host: str | None = typer.Option(
        None,
        "--host",
        help="Preview server bind address (default: 127.0.0.1).",
    ),
    port: int | None = typer.Option(
        None, "--port", help="Preview server port (default: 5077)."
    ),
) -> None:
    """Watch for file changes, rebuild incrementally, and serve a live preview."""
    config = _load_config(project_dir=Path(project_dir), host=host, port=port)
    try:
        with command.watch(config, on_report=_build_listener()) as session:
            base = f"http://{_display_host(session.host)}:{session.port}"
            print(
                f"Server running at {base}/\n  Reports: {base}/default/",
                file=sys.stderr,
                flush=True,
            )
            print("Press Ctrl+C to stop.", file=sys.stderr, flush=True)
            # Loop with a short timeout: on Windows, threading.Event.wait()
            # without a timeout is not interruptible by Ctrl+C, so the main
            # thread would block indefinitely. The timeout returns control
            # to the interpreter periodically so pending KeyboardInterrupt
            # can be raised.
            while not session.shutdown.wait(timeout=0.1):
                pass
    except command.WatchStartupError as exc:
        raise typer.Exit(1) from exc
    except KeyboardInterrupt:
        pass


_WILDCARD_BIND_HOSTS = frozenset({"0.0.0.0", "::", "[::]"})


def _display_host(bind: str) -> str:
    """Pick a copy-pasteable host for the printed preview URL.

    Hugo binds to ``bind`` literally, but a wildcard like ``0.0.0.0`` is not
    a useful URL to share. Resolve a routable LAN address in that case so a
    collaborative-authoring host can hand the URL to attendees verbatim.
    """
    if bind not in _WILDCARD_BIND_HOSTS:
        return bind
    return _local_ip() or bind


def _local_ip() -> str | None:
    """Return the source IP the OS would use for an outbound connection.

    UDP ``connect`` does not send a packet — it only fixes the destination so
    the kernel can choose an interface. The dest IP is unreachable but
    irrelevant; we just read back the chosen source. Returns ``None`` on any
    socket error (e.g. no routable interface).
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 1))
            return s.getsockname()[0]
    except OSError:
        return None


def main() -> None:
    basicConfig(stream=sys.stderr, format="%(message)s", level=INFO)
    app()
