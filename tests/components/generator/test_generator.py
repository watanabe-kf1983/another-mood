"""Tests for generate and reconcile — the Markdown-producing components."""

from pathlib import Path
from typing import Any

import yaml

from another_mood.components.generator.generator import generate, reconcile
from another_mood.components.shared.build_report import BuildReport


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write a Python dict as a YAML file."""
    path.write_text(yaml.safe_dump(data, allow_unicode=True))


class TestGenerate:
    def test_renders_normal_output(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data" / "data"
        data_dir.mkdir(parents=True)
        _write_yaml(data_dir / "data.yaml", {"title": "Hello"})

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "index.md").write_text("# {{ title }}\n")

        out_dir = tmp_path / "output"
        generate(
            data_dir=tmp_path / "data",
            templates_dir=templates_dir,
            out_dir=out_dir,
        )

        assert (out_dir / "data" / "index.md").read_text() == "# Hello\n"
        # __meta_root is always rendered alongside __root.
        assert (out_dir / "data" / "__reference" / "index.md").exists()

    def test_writes_error_to_reports_on_template_error(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data" / "data"
        data_dir.mkdir(parents=True)
        _write_yaml(data_dir / "data.yaml", {"x": 1})

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "index.md").write_text('{% section "bad" with x %}')

        out_dir = tmp_path / "output"
        generate(
            data_dir=tmp_path / "data",
            templates_dir=templates_dir,
            out_dir=out_dir,
        )

        # Generate no longer renders an error page itself; it just records
        # the failure in reports/ and Reconcile turns it into a page later.
        report = yaml.safe_load(
            (out_dir / "reports" / "__build_report.yaml").read_text()
        )
        assert report["__build_report"]["generate"]["result"] == "ng"
        assert report["__build_report"]["errors"]


class TestReconcile:
    def test_passes_through_normal_output(self, tmp_path: Path) -> None:
        upstream = tmp_path / "generate"
        (upstream / "data").mkdir(parents=True)
        (upstream / "data" / "index.md").write_text("# Hello\n")
        (upstream / "data" / "__reference" / "index.md").parent.mkdir()
        (upstream / "data" / "__reference" / "index.md").write_text("# Reference\n")
        (upstream / "reports").mkdir()

        out_dir = tmp_path / "reconcile"
        reconcile(data_dir=upstream, out_dir=out_dir)

        assert (out_dir / "data" / "index.md").read_text() == "# Hello\n"
        assert (
            out_dir / "data" / "__reference" / "index.md"
        ).read_text() == "# Reference\n"

    def test_renders_error_page_when_upstream_has_errors(self, tmp_path: Path) -> None:
        upstream = tmp_path / "generate"
        (upstream / "data").mkdir(parents=True)
        # Stale data left over from a previous successful run.
        (upstream / "data" / "stale.md").write_text("stale\n")
        report = BuildReport({"errors": [{"message": "boom"}]})
        report.write(upstream / "reports")

        out_dir = tmp_path / "reconcile"
        reconcile(data_dir=upstream, out_dir=out_dir)

        # Build report page is rendered, stale upstream data is not propagated.
        error_page = (out_dir / "data" / "index.md").read_text()
        assert error_page.startswith("# Build Report")
        assert not (out_dir / "data" / "stale.md").exists()
