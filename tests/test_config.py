"""Tests for ProjectConfig path defaults."""

from pathlib import Path

from another_mood.config import ProjectConfig


class TestAnotherMoodRoot:
    def test_relative_project_dir(self) -> None:
        config = ProjectConfig(project_dir=Path("docs"))
        assert config.out_dir == Path(".another-mood/docs/output")
        assert config.render_dir == Path(".another-mood/docs/render")

    def test_relative_multi_component_project_dir(self) -> None:
        config = ProjectConfig(project_dir=Path("showcase/starter"))
        assert config.out_dir == Path(".another-mood/showcase/starter/output")

    def test_absolute_project_dir_under_cwd(self, tmp_path: Path) -> None:
        # An absolute path that lies under CWD should resolve as if relative.
        config = ProjectConfig(project_dir=Path.cwd() / "docs")
        assert config.out_dir == Path(".another-mood/docs/output")

    def test_absolute_project_dir_outside_cwd(self) -> None:
        # Outside CWD: fall back to the basename so output never lands inside
        # the project directory itself.
        config = ProjectConfig(project_dir=Path("/some/elsewhere/docs"))
        assert config.out_dir == Path(".another-mood/docs/output")
