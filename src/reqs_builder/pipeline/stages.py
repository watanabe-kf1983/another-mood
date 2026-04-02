"""Pipeline definition — stage factories and pipeline composition."""

from reqs_builder.components import compose, generate, inspect_schema, normalize
from reqs_builder.config import ProjectConfig
from reqs_builder.pipeline.base import Pipeline, Stage, Task
from reqs_builder.pipeline.render import RenderStage


def inspect_schema_stage(config: ProjectConfig) -> Task:
    """Validate schema files against SchemaSchema."""
    call = inspect_schema.on_stage("inspect_schema").bind(
        schema_dir=config.schema_dir,
        out_dir=config.data_catalog_dir,
    )
    return Stage(run_fn=call, watch_paths=call.input_dirs)


def normalize_contents_stage(config: ProjectConfig) -> Task:
    """Normalize contents_dir to normalized_contents_dir (passthrough)."""
    call = normalize.on_stage("normalize_contents").bind(
        src_dir=config.contents_dir,
        out_dir=config.normalized_contents_dir,
        upstream_dir=config.data_catalog_dir,
        schema_dir=config.schema_dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[config.contents_dir, config.data_catalog_dir],
    )


def compose_stage(config: ProjectConfig) -> Task:
    """Compose views from normalized contents + query evaluation."""
    call = compose.on_stage("compose").bind(
        contents_dir=config.normalized_contents_dir,
        queries_dir=config.queries_dir,
        out_dir=config.views_dir,
    )
    return Stage(run_fn=call, watch_paths=call.input_dirs)


def generator_stage(config: ProjectConfig) -> Task:
    """Generate Markdown from views YAML + Jinja2 templates."""
    call = generate.on_stage("generate").bind(
        data_dir=config.views_dir,
        templates_dir=config.templates_dir,
        out_dir=config.out_dir,
    )
    return Stage(run_fn=call, watch_paths=call.input_dirs)


def render_stage(config: ProjectConfig) -> Task:
    """Prepare Hugo content and render to HTML."""
    return RenderStage(
        src_dir=config.out_dir,
        render_input_dir=config.render_in_dir,
        render_output_dir=config.render_out_dir,
        port=config.port,
    )


def pipeline(config: ProjectConfig) -> Pipeline:
    """Create the full pipeline: [Inspect Schema →] Normalize → Compose → Generate → Render."""
    stages: list[Task] = [
        inspect_schema_stage(config),
        normalize_contents_stage(config),
        compose_stage(config),
        generator_stage(config),
        render_stage(config),
    ]
    return Pipeline(stages)
