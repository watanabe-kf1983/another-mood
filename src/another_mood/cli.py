"""CLI entry point."""

import sys
from collections.abc import Callable
from datetime import datetime
from logging import INFO, basicConfig
from pathlib import Path

import typer

from another_mood.components.shared.component.build_report import BuildReport
from another_mood.config import ConfigValidationError, ProjectConfig
from another_mood.components.scaffold import blueprints as bp
from another_mood.pipeline.stages import pipeline

app = typer.Typer()
blueprint_app = typer.Typer(help="Manage built-in blueprints (sample projects).")
app.add_typer(blueprint_app, name="blueprint")


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
    for name, description in bp.available_blueprints().items():
        print(name)
        print(f"  {description}")


@blueprint_app.command("apply")
def apply_blueprint(
    name: str = typer.Argument(help="Blueprint name."),
    project_dir: str = typer.Argument(help="Project directory."),
) -> None:
    """Apply a blueprint into a project directory."""
    blueprints = bp.available_blueprints()
    if name not in blueprints:
        print(
            f"unknown blueprint: {name!r} (available: {', '.join(blueprints)})",
            file=sys.stderr,
        )
        raise typer.Exit(1)
    target = Path(project_dir)
    print(f"Scaffolding {target}/ from blueprint: {name}", file=sys.stderr)
    result = bp.apply_blueprint(name, target)
    for path in result.created:
        print(f"  created: {path}", file=sys.stderr)
    for path in result.skipped:
        print(f"warning: skipped (already exists): {path}", file=sys.stderr)
    if not result.all_written:
        raise typer.Exit(1)


@app.command()
def init(project_dir: str = typer.Argument(help="Project directory")) -> None:
    """Initialize a new project. Shortcut for `mood blueprint apply starter`."""
    apply_blueprint(bp.DEFAULT_BLUEPRINT, project_dir)


_BUILD_MESSAGES = {
    (True, True): "Build successfully completed",
    (True, False): "Build failed",
    (False, True): "Files updated, and re-build successfully completed",
    (False, False): "Files updated, but re-build failed",
}


def _build_listener() -> Callable[[BuildReport], None]:
    """Return an on_report listener that prints the iteration result to stderr."""
    first = True

    def on_report(report: BuildReport) -> None:
        nonlocal first
        msg = _BUILD_MESSAGES[first, not report.has_errors()]
        first = False
        print(f"{msg} at {datetime.now():%H:%M:%S}.", file=sys.stderr, flush=True)

    return on_report


@app.command()
def build(project_dir: str = typer.Argument(help="Project directory")) -> None:
    """Build the project to Markdown and rendered HTML."""
    config = _load_config(project_dir=Path(project_dir))
    report = pipeline(config, on_report=_build_listener()).run()
    if report.has_errors():
        raise SystemExit(1)


@app.command()
def watch(
    project_dir: str = typer.Argument(help="Project directory"),
    port: int = typer.Option(5077, help="Preview server port"),
) -> None:
    """Watch for changes and rebuild automatically with live preview."""
    config = _load_config(project_dir=Path(project_dir), port=port)
    with pipeline(config, on_report=_build_listener()).start_watching() as shutdown:
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
