"""Pipeline definition — stage factories and pipeline composition."""

from reqs_builder.components import compose, generate, normalize
from reqs_builder.config import ProjectConfig
from reqs_builder.pipeline.base import Pipeline, Stage, Task
from reqs_builder.pipeline.render import RenderStage


def normalize_contents_stage(config: ProjectConfig) -> Task:
    """Normalize contents_dir to normalized_contents_dir (passthrough)."""
    return Stage(
        run_fn=normalize.bind(
            src_dir=config.contents_dir,
            out_dir=config.normalized_contents_dir,
        ),
        watch_paths=[config.contents_dir],
        name="Normalize",
    )


def compose_stage(config: ProjectConfig) -> Task:
    """Compose views from normalized contents + query evaluation."""
    return Stage(
        run_fn=compose.bind(
            contents_dir=config.normalized_contents_dir,
            queries_dir=config.queries_dir,
            out_dir=config.views_dir,
        ),
        watch_paths=[config.normalized_contents_dir, config.queries_dir],
        name="Compose",
    )


def generator_stage(config: ProjectConfig) -> Task:
    """Generate Markdown from views YAML + Jinja2 templates."""
    return Stage(
        run_fn=generate.bind(
            data_dir=config.views_dir,
            templates_dir=config.templates_dir,
            out_dir=config.out_dir,
        ),
        watch_paths=[config.views_dir, config.templates_dir],
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
    """Create the full pipeline: Normalize → Compose → Generate → Render."""
    stages: list[Task] = [
        normalize_contents_stage(config),
        compose_stage(config),
        generator_stage(config),
        render_stage(config),
    ]
    return Pipeline(stages)
