"""Tests for ProjectConfig path defaults and publish-destination resolution."""

from pathlib import Path

import pytest

from another_mood.config import ConfigValidationError, ProjectConfig


def _scaffold_project(project_dir: Path) -> None:
    """Create the minimal source layout ``ProjectConfig.verify`` requires."""
    definition = project_dir / "definition"
    (definition / "queries").mkdir(parents=True)
    (definition / "templates").mkdir(parents=True)
    (project_dir / "contents").mkdir(parents=True)
    (definition / "schema.yaml").write_text("")
    (definition / "reports.yaml").write_text("")


class TestAnotherMoodRoot:
    def test_relative_project_dir(self) -> None:
        config = ProjectConfig(project_dir=Path("docs")).resolved_for_build()
        assert config.out_dir == Path(".another-mood/docs/output")
        assert config.render_dir == Path(".another-mood/docs/render")

    def test_relative_multi_component_project_dir(self) -> None:
        config = ProjectConfig(
            project_dir=Path("showcase/starter")
        ).resolved_for_build()
        assert config.out_dir == Path(".another-mood/showcase/starter/output")

    def test_absolute_project_dir_under_cwd(self, tmp_path: Path) -> None:
        # An absolute path that lies under CWD should resolve as if relative.
        config = ProjectConfig(project_dir=Path.cwd() / "docs").resolved_for_build()
        assert config.out_dir == Path(".another-mood/docs/output")


class TestVerifyProjectDirUnderCwd:
    """project_dir must resolve under CWD; external paths are rejected (G8).

    The CWD-under check runs before the existence/source checks, so an external
    path is rejected regardless of whether it (or its sources) exist — pinning
    the check ordering via the error message.
    """

    def test_accepts_subdir_under_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _scaffold_project(tmp_path / "docs")
        ProjectConfig(project_dir=Path("docs")).verify()  # no raise

    def test_accepts_cwd_itself(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _scaffold_project(tmp_path)
        ProjectConfig(project_dir=Path(".")).verify()  # no raise

    def test_rejects_absolute_outside_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        config = ProjectConfig(project_dir=tmp_path.parent / "elsewhere")
        with pytest.raises(ConfigValidationError, match="under the current directory"):
            config.verify()

    def test_rejects_relative_parent_escape(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        config = ProjectConfig(project_dir=Path("../elsewhere/docs"))
        with pytest.raises(ConfigValidationError, match="under the current directory"):
            config.verify()


class TestPublishDestinations:
    def test_unset_by_default(self) -> None:
        config = ProjectConfig(project_dir=Path("docs"))
        assert config.out_dir is None
        assert config.render_dir is None

    def test_build_keeps_explicit_dirs(self) -> None:
        config = ProjectConfig(
            project_dir=Path("docs"),
            out_dir=Path("/pin/out"),
            render_dir=Path("/pin/render"),
        ).resolved_for_build()
        assert config.out_dir == Path("/pin/out")
        assert config.render_dir == Path("/pin/render")

    def test_watch_publishes_nothing_by_default(self) -> None:
        config = ProjectConfig(project_dir=Path("docs")).resolved_for_watch()
        assert config.out_dir is None
        assert config.render_dir is None

    def test_watch_opts_into_md_via_out_dir(self) -> None:
        config = ProjectConfig(
            project_dir=Path("docs"), out_dir=Path("/pin/out")
        ).resolved_for_watch()
        assert config.out_dir == Path("/pin/out")

    def test_watch_never_publishes_render(self) -> None:
        # Even a pinned render_dir (e.g. RB_RENDER_DIR) is dropped: the live
        # server is watch's only HTML consumer.
        config = ProjectConfig(
            project_dir=Path("docs"), render_dir=Path("/pin/render")
        ).resolved_for_watch()
        assert config.render_dir is None
