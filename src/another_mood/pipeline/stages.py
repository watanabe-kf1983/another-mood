"""Pipeline definition — stage factories and pipeline composition."""

import shutil
import sys
from datetime import datetime

from another_mood.components import (
    compose,
    generate,
    inspect_schema,
    normalize_contents,
    normalize_queries,
    reconcile,
)
from another_mood.components.shared.build_report import BuildReport
from another_mood.components.shared.dir_lock import dir_lock, exclusive_write
from another_mood.config import ProjectConfig
from another_mood.pipeline.base import Pipeline, ReportingStage, Stage, Task
from another_mood.pipeline.render import RenderStage


def inspect_schema_stage(config: ProjectConfig) -> Task:
    """Validate schema files against SchemaSchema."""
    out = config.component_output(inspect_schema)
    call = inspect_schema.bind(
        schema_dir=config.schema_dir,
        out_dir=out.dir,
    )
    return Stage(run_fn=call, watch_paths=[config.schema_dir])


def normalize_contents_stage(config: ProjectConfig) -> Task:
    """Normalize contents_dir to normalized_contents_dir (passthrough)."""
    inspect_out = config.component_output(inspect_schema)
    out = config.component_output(normalize_contents)
    call = normalize_contents.bind(
        src_dir=config.contents_dir,
        data_catalog_dir=inspect_out.dir,
        schema_dir=config.schema_dir,
        out_dir=out.dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[config.contents_dir],
        upstreams=[inspect_out],
    )


def normalize_queries_stage(config: ProjectConfig) -> Task:
    """Validate and normalize query files."""
    out = config.component_output(normalize_queries)
    call = normalize_queries.bind(
        queries_dir=config.queries_dir,
        out_dir=out.dir,
    )
    return Stage(run_fn=call, watch_paths=[config.queries_dir])


def compose_stage(config: ProjectConfig) -> Task:
    """Compose views from normalized contents + query evaluation."""
    contents_out = config.component_output(normalize_contents)
    queries_out = config.component_output(normalize_queries)
    inspect_out = config.component_output(inspect_schema)
    out = config.component_output(compose)
    call = compose.bind(
        contents_dir=contents_out.dir,
        queries_dir=queries_out.dir,
        data_catalog_dir=inspect_out.dir,
        out_dir=out.dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[],
        upstreams=[contents_out, queries_out, inspect_out],
    )


def generator_stage(config: ProjectConfig) -> Task:
    """Generate Markdown from views YAML + Jinja2 templates."""
    compose_out = config.component_output(compose)
    out = config.component_output(generate)
    call = generate.bind(
        data_dir=compose_out.dir,
        templates_dir=config.templates_dir,
        out_dir=out.dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[config.templates_dir],
        upstreams=[compose_out],
    )


def reconcile_stage(config: ProjectConfig) -> Task:
    """Pass Generator output through, or replace with build report on errors."""
    generate_out = config.component_output(generate)
    out = config.component_output(reconcile)
    call = reconcile.bind(
        data_dir=generate_out.dir,
        out_dir=out.dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[],
        upstreams=[generate_out],
    )


def render_stage(config: ProjectConfig) -> Task:
    """Prepare Hugo content and render to HTML."""
    reconcile_out = config.component_output(reconcile)
    return RenderStage(
        src_dir=reconcile_out.dir / "data",
        render_input_dir=config.tmp_subdir("render_input"),
        render_dir=config.tmp_subdir("render"),
        port=config.port,
    )


def publish_stage(config: ProjectConfig) -> Task:
    """Copy final artifacts from tmp to output directories."""
    reconcile_out = config.component_output(reconcile)
    src_dirs = {
        reconcile_out.dir / "data": config.out_dir,
        config.tmp_subdir("render"): config.render_dir,
    }

    def publish() -> None:
        for src, dst in src_dirs.items():
            if src.exists():
                with exclusive_write(dst) as tmp:
                    shutil.copytree(src, tmp, dirs_exist_ok=True)

    return Stage(
        run_fn=publish,
        watch_paths=[config.tmp_subdir("render")],
    )


def build_report_stage(config: ProjectConfig) -> ReportingStage:
    """Report build result to user. Exposes BuildReport for CLI."""
    reconcile_out = config.component_output(reconcile)
    first = True

    def report() -> BuildReport:
        nonlocal first
        with dir_lock(reconcile_out.dir):
            result = BuildReport.collect(reconcile_out.dir / "reports")
        succeeded = not result.has_errors()
        messages = {
            (True, True): "Build successfully completed",
            (True, False): "Build failed",
            (False, True): "Files updated, and re-build successfully completed",
            (False, False): "Files updated, but re-build failed",
        }
        msg = messages[first, succeeded]
        first = False
        print(f"{msg} at {datetime.now():%H:%M:%S}.", file=sys.stderr, flush=True)
        return result

    return ReportingStage(
        report_fn=report,
        upstreams=[reconcile_out],
    )


def pipeline(config: ProjectConfig) -> Pipeline:
    """Create the full pipeline."""
    stages: list[Task] = [
        inspect_schema_stage(config),
        normalize_contents_stage(config),
        normalize_queries_stage(config),
        compose_stage(config),
        generator_stage(config),
        reconcile_stage(config),
        render_stage(config),
        publish_stage(config),
    ]
    return Pipeline(stages, reporting=build_report_stage(config))
