"""Pipeline definition — stage factories and pipeline composition."""

import shutil
from pathlib import Path

from reqs_builder.atomic_dir_writer import AtomicDirWriter
from reqs_builder.config import ProjectConfig
from reqs_builder.generator import generate
from reqs_builder.normalizer import normalize
from reqs_builder.pipeline.base import Pipeline, Stage, Task
from reqs_builder.pipeline.render import RenderStage


def _copy(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True)


def copy_stage(config: ProjectConfig) -> Task:
    """Copy contents_dir to out_dir."""
    writer = AtomicDirWriter(
        lambda out_dir: _copy(config.contents_dir, out_dir),
        config.out_dir,
    )
    return Stage(
        run_fn=writer.run,
        watch_paths=[config.contents_dir],
        name="Copy",
    )


def normalize_contents_stage(config: ProjectConfig) -> Task:
    """Normalize contents_dir to normalized_contents_dir (passthrough)."""
    writer = AtomicDirWriter(
        lambda out_dir: normalize(config.contents_dir, out_dir),
        config.normalized_contents_dir,
    )
    return Stage(
        run_fn=writer.run,
        watch_paths=[config.contents_dir],
        name="Normalize",
    )


def generator_stage(config: ProjectConfig) -> Task:
    """Generate Markdown from views YAML + Jinja2 templates.

    Temporary: reads from normalized_contents_dir instead of views_dir
    until Composer is implemented.
    """
    writer = AtomicDirWriter(
        lambda out_dir: generate(
            config.normalized_contents_dir, config.templates_dir, out_dir
        ),
        config.out_dir,
    )
    return Stage(
        run_fn=writer.run,
        watch_paths=[config.normalized_contents_dir, config.templates_dir],
        name="Generate",
    )


def render_stage(config: ProjectConfig) -> Task:
    """Prepare Hugo content and render to HTML."""
    return RenderStage(
        src_dir=config.out_dir,
        render_input_dir=config.hugo_content_dir,
        render_output_dir=config.render_out_dir,
        port=config.port,
    )


def pipeline(config: ProjectConfig) -> Pipeline:
    """Create the full pipeline, branching on definition_dir existence."""
    if config.definition_dir.is_dir():
        stages: list[Task] = [
            normalize_contents_stage(config),
            generator_stage(config),
            render_stage(config),
        ]
    else:
        stages = [copy_stage(config), render_stage(config)]
    return Pipeline(stages)
