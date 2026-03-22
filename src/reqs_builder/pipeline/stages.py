"""Pipeline definition — stage factories and pipeline composition."""

import shutil
from pathlib import Path

from reqs_builder.config import ProjectConfig
from reqs_builder.pipeline.base import NormalStage, Pipeline, Stage
from reqs_builder.pipeline.render import RenderStage


def _copy(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True)


def copy_stage(config: ProjectConfig) -> Stage:
    """Copy contents_dir to out_dir."""
    return NormalStage(
        output_dir=config.out_dir,
        dir_writer_fn=lambda out_dir: _copy(config.contents_dir, out_dir),
        watch_paths=[config.contents_dir],
    )


def render_stage(config: ProjectConfig) -> Stage:
    """Prepare Hugo content and render to HTML."""
    return RenderStage(config)


def pipeline(config: ProjectConfig) -> Pipeline:
    """Create the full pipeline: copy_contents → render."""
    return Pipeline(
        [
            copy_stage(config),
            render_stage(config),
        ]
    )
