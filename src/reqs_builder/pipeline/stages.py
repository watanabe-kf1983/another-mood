"""Pipeline definition — stage factories and pipeline composition."""

import shutil
from pathlib import Path

from reqs_builder.atomic_dir_writer import AtomicDirWriter
from reqs_builder.config import ProjectConfig
from reqs_builder.generator import generate
from reqs_builder.pipeline.base import NormalStage, Pipeline, Stage
from reqs_builder.pipeline.render import RenderStage


def _copy(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True)


def copy_stage(config: ProjectConfig) -> Stage:
    """Copy contents_dir to out_dir."""
    writer = AtomicDirWriter(
        config.out_dir,
        lambda out_dir: _copy(config.contents_dir, out_dir),
    )
    return NormalStage(
        run_fn=writer.run,
        watch_paths=[config.contents_dir],
        name="Copy",
    )


def generator_stage(config: ProjectConfig) -> Stage:
    """Generate Markdown from views YAML + Jinja2 templates.

    Temporary: reads from contents_dir instead of views_dir
    until Composer is implemented.
    """
    writer = AtomicDirWriter(
        config.out_dir,
        lambda out_dir: generate(config.contents_dir, config.templates_dir, out_dir),
    )
    return NormalStage(
        run_fn=writer.run,
        watch_paths=[config.contents_dir, config.templates_dir],
        name="Generate",
    )


def render_stage(config: ProjectConfig) -> Stage:
    """Prepare Hugo content and render to HTML."""
    return RenderStage(config)


def pipeline(config: ProjectConfig) -> Pipeline:
    """Create the full pipeline, branching on definition_dir existence."""
    if config.definition_dir.is_dir():
        content_stage: Stage = generator_stage(config)
    else:
        content_stage = copy_stage(config)
    return Pipeline([content_stage, render_stage(config)])
