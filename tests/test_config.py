from pathlib import Path

from reqs_builder.config import ProjectPaths


class TestProjectPathsDefaults:
    def test_contents_dir_defaults_to_project_dir_contents(self) -> None:
        paths = ProjectPaths(project_dir=Path("myproject"))
        assert paths.contents_dir == Path("myproject/contents")

    def test_out_dir_defaults_to_reqs_builder_output(self) -> None:
        paths = ProjectPaths(project_dir=Path("myproject"))
        assert paths.out_dir == Path(".reqs-builder/myproject/output")

    def test_render_out_dir_defaults_to_reqs_builder_render(self) -> None:
        paths = ProjectPaths(project_dir=Path("myproject"))
        assert paths.render_out_dir == Path(".reqs-builder/myproject/render")

    def test_hugo_content_dir_defaults_to_reqs_builder_hugo_content(self) -> None:
        paths = ProjectPaths(project_dir=Path("myproject"))
        assert paths.hugo_content_dir == Path(".reqs-builder/myproject/hugo-content")

    def test_subdir_project_dir(self) -> None:
        paths = ProjectPaths(project_dir=Path("docs/api"))
        assert paths.contents_dir == Path("docs/api/contents")
        assert paths.out_dir == Path(".reqs-builder/docs/api/output")
        assert paths.render_out_dir == Path(".reqs-builder/docs/api/render")
        assert paths.hugo_content_dir == Path(".reqs-builder/docs/api/hugo-content")
