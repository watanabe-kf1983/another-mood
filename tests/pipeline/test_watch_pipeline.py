"""The watch pipeline serves the site instead of building it, and still
reports errors whether or not it publishes."""

from pathlib import Path

import pytest

from another_mood import command
from another_mood.components.manifest import Manifest
from another_mood.config import ProjectConfig
from another_mood.layout import resolve_layout
from another_mood.pipeline.stages import watch_pipeline
from another_mood.pipeline.workspace import Workspace, make_processor_info


def test_watch_never_runs_hugo_build(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path, out_dir=None)

    report = watch_pipeline(workspace).run()

    assert not report.has_errors()
    assert (workspace.root / "prepare_site" / "data").is_dir()
    assert not (workspace.root / "hugo_build").exists()


@pytest.mark.parametrize("publishes", [False, True], ids=["no-out-dir", "out-dir"])
def test_watch_reports_errors(tmp_path: Path, publishes: bool) -> None:
    out_dir = tmp_path / "published" if publishes else None
    workspace = _make_workspace(tmp_path, out_dir=out_dir)
    (workspace.config.project_dir / "definition" / "schema.yaml").write_text(
        "this: [is: broken\n", encoding="utf-8"
    )

    report = watch_pipeline(workspace).run()

    assert report.has_errors()


def _make_workspace(tmp_path: Path, *, out_dir: Path | None) -> Workspace:
    project = tmp_path / "project"
    command.init(project)
    config = ProjectConfig(
        namespace_root=tmp_path, project_dir=project, out_dir=out_dir
    )
    return Workspace(
        config,
        tmp_path / "work",
        resolve_layout(project),
        Manifest(sbdb_version=1),
        make_processor_info("watch"),
    )
