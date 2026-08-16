"""The run's own facts, and the store Workspace projects them into."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from another_mood.components.manifest import Manifest
from another_mood.config import ProjectConfig
from another_mood.layout import SourceLayout
from another_mood.pipeline.workspace import (
    ProcessorInfo,
    Workspace,
    make_processor_info,
)


def test_processor_info_stamps_an_aware_moment() -> None:
    # A naive stamp would flatten to a timestamp with no offset at all.
    assert make_processor_info("build").started_at.utcoffset() is not None


def test_build_info_flattens_the_processor_namespace(tmp_path: Path) -> None:
    processor = ProcessorInfo(
        name="another-mood",
        version="1.2.3",
        started_at=datetime(
            2026, 8, 16, 14, 23, 45, 678, tzinfo=timezone(timedelta(hours=9))
        ),
        command="watch",
    )
    # An unpinned tmp_dir: no config row, but the throwaway working dir it
    # left out still has to reach the store. `vars` is a config field that
    # yields no row either.
    workspace = Workspace(
        ProjectConfig(
            namespace_root=tmp_path,
            project_dir=tmp_path / "project",
            vars={"git_sha": "abc123"},
        ),
        tmp_path / "work",
        SourceLayout.for_project(tmp_path / "project"),
        Manifest(),
        processor,
        temporary=True,
    )

    assert dict(workspace.build_info) == {
        "processor.name": "another-mood",
        "processor.version": "1.2.3",
        "processor.started_at": "2026-08-16T14:23:45+09:00",
        "processor.command": "watch",
        "processor.config.namespace_root": str(tmp_path),
        "processor.config.project_dir": str(tmp_path / "project"),
        "processor.config.host": "127.0.0.1",
        "processor.config.port": "5077",
        "processor.workspace.root": str(tmp_path / "work"),
        "processor.workspace.temporary": "true",
    }
