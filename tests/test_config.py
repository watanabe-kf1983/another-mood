"""Tests for ProjectConfig path defaults and publish-destination resolution."""

from pathlib import Path

from another_mood.config import ProjectConfig


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

    def test_absolute_project_dir_outside_cwd(self) -> None:
        # Outside CWD: fall back to the basename so output never lands inside
        # the project directory itself.
        config = ProjectConfig(
            project_dir=Path("/some/elsewhere/docs")
        ).resolved_for_build()
        assert config.out_dir == Path(".another-mood/docs/output")


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
