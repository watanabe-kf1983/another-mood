from pathlib import Path

from reqs_builder.config import ProjectConfig


class TestProjectConfigDefaults:
    def test_contents_dir_defaults_to_project_dir_contents(self) -> None:
        paths = ProjectConfig(project_dir=Path("myproject"))
        assert paths.contents_dir == Path("myproject/contents")

    def test_out_dir_defaults_to_reqs_builder_output(self) -> None:
        paths = ProjectConfig(project_dir=Path("myproject"))
        assert paths.out_dir == Path(".reqs-builder/myproject/output")

    def test_render_out_dir_defaults_to_reqs_builder_render(self) -> None:
        paths = ProjectConfig(project_dir=Path("myproject"))
        assert paths.render_out_dir == Path(".reqs-builder/myproject/render")

    def test_hugo_content_dir_defaults_to_reqs_builder_hugo_content(self) -> None:
        paths = ProjectConfig(project_dir=Path("myproject"))
        assert paths.hugo_content_dir == Path(".reqs-builder/myproject/hugo-content")

    def test_port_defaults_to_1313(self) -> None:
        config = ProjectConfig(project_dir=Path("myproject"))
        assert config.port == 1313

    def test_definition_dir_defaults_to_project_dir_definition(self) -> None:
        paths = ProjectConfig(project_dir=Path("myproject"))
        assert paths.definition_dir == Path("myproject/definition")

    def test_templates_dir_defaults_to_definition_templates(self) -> None:
        paths = ProjectConfig(project_dir=Path("myproject"))
        assert paths.templates_dir == Path("myproject/definition/templates")

    def test_normalized_contents_dir_defaults(self) -> None:
        paths = ProjectConfig(project_dir=Path("myproject"))
        assert paths.normalized_contents_dir == Path(
            ".reqs-builder/myproject/tmp/normalized/contents"
        )

    def test_subdir_project_dir(self) -> None:
        paths = ProjectConfig(project_dir=Path("docs/api"))
        assert paths.contents_dir == Path("docs/api/contents")
        assert paths.definition_dir == Path("docs/api/definition")
        assert paths.templates_dir == Path("docs/api/definition/templates")
        assert paths.out_dir == Path(".reqs-builder/docs/api/output")
        assert paths.render_out_dir == Path(".reqs-builder/docs/api/render")
        assert paths.hugo_content_dir == Path(".reqs-builder/docs/api/hugo-content")
        assert paths.normalized_contents_dir == Path(
            ".reqs-builder/docs/api/tmp/normalized/contents"
        )
