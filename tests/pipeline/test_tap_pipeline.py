"""The tap pipeline's documented contract: rendering stages never run,
so the data layer stays extractable while templates are broken."""

from pathlib import Path

from another_mood import command
from another_mood.components.manifest import Manifest
from another_mood.config import ProjectConfig
from another_mood.layout import resolve_layout
from another_mood.pipeline.stages import tap_pipeline
from another_mood.pipeline.workspace import Workspace


def test_broken_templates_do_not_fail_the_tap_pipeline(tmp_path: Path) -> None:
    project = tmp_path / "project"
    command.init(project)
    for template in (project / "definition" / "templates").rglob("*"):
        if template.is_file():
            template.write_text("{% broken", encoding="utf-8")
    config = ProjectConfig(project_dir=project, tap_dir=tmp_path / "out")
    workspace = Workspace(
        config, tmp_path / "work", resolve_layout(project), Manifest()
    )

    report = tap_pipeline(workspace).run()

    assert not report.has_errors()
    assert (tmp_path / "out" / "data.json").exists()
