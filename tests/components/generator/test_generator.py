"""Tests for generate and reconcile — the Markdown-producing components."""

from pathlib import Path
from typing import Any

import yaml

from another_mood.components.generator.generator import (
    generate,
    reconcile,
)
from another_mood.components.generator.output_formats.md import md_escape
from another_mood.components.shared.component.build_report import (
    BuildReport,
    ErrorEntry,
)
from another_mood.components.shared.user_source.diagnostic import DiagnosticEntry


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write a Python dict as a YAML file."""
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


class TestGenerate:
    def test_renders_normal_output(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data" / "data"
        data_dir.mkdir(parents=True)
        _write_yaml(data_dir / "data.yaml", {"title": "Hello"})

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "index.md").write_text("# {{ title }}\n")

        out_dir = tmp_path / "output"
        reports_file = tmp_path / "reports.yaml"
        reports_file.write_text("file_per: []\n")
        generate(
            data_dir=tmp_path / "data",
            templates_dir=templates_dir,
            reports_file=reports_file,
            out_dir=out_dir,
        )

        # User reports are rendered under reports/; the root node's own
        # anchor is stamped at the top of index.md (C9 post_process).
        assert (out_dir / "data" / "reports" / "index.md").read_text() == (
            '<a id="/"></a>\n# Hello\n'
        )
        # Metadata root is always rendered at the site root.
        assert (out_dir / "data" / "index.md").exists()

    def test_writes_error_to_reports_on_template_error(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data" / "data"
        data_dir.mkdir(parents=True)
        _write_yaml(data_dir / "data.yaml", {"x": 1})

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "index.md").write_text('{% mood_view "bad.md" with x %}')

        out_dir = tmp_path / "output"
        reports_file = tmp_path / "reports.yaml"
        reports_file.write_text("file_per: []\n")
        generate(
            data_dir=tmp_path / "data",
            templates_dir=templates_dir,
            reports_file=reports_file,
            out_dir=out_dir,
        )

        # Generate no longer renders an error page itself; it just records
        # the failure in reports/ and Reconcile turns it into a page later.
        report = yaml.safe_load(
            (out_dir / "reports" / "__build_report.yaml").read_text()
        )
        stages = report["__build_report"]["stages"]
        assert any(s["component"] == "generate" and s["result"] == "ng" for s in stages)
        assert report["__build_report"]["errors"]


class TestReconcile:
    def test_passes_through_normal_output(self, tmp_path: Path) -> None:
        upstream = tmp_path / "generate"
        (upstream / "data").mkdir(parents=True)
        (upstream / "data" / "index.md").write_text("# Root\n")
        (upstream / "data" / "reports" / "index.md").parent.mkdir()
        (upstream / "data" / "reports" / "index.md").write_text("# Hello\n")
        (upstream / "reports").mkdir()

        out_dir = tmp_path / "reconcile"
        reconcile(data_dir=upstream, out_dir=out_dir)

        assert (out_dir / "data" / "index.md").read_text() == "# Root\n"
        assert (out_dir / "data" / "reports" / "index.md").read_text() == "# Hello\n"

    def test_renders_warnings_page_and_links_from_index(self, tmp_path: Path) -> None:
        upstream = tmp_path / "generate"
        (upstream / "data").mkdir(parents=True)
        (upstream / "data" / "index.md").write_text("# Root\n")
        report = BuildReport(
            diagnostics=(
                DiagnosticEntry(
                    file="albums.yaml",
                    line=3,
                    column=5,
                    message="x-ref albums.artist_id = 'ghost' has no match in artists.id",
                    severity="warning",
                    source="x-ref-data",
                ),
            ),
        )
        report.write(upstream / "reports")

        out_dir = tmp_path / "reconcile"
        reconcile(data_dir=upstream, out_dir=out_dir)

        index = (out_dir / "data" / "index.md").read_text()
        assert index.startswith("# Root\n")
        assert "## Warnings" in index
        assert "1 warning — [view](__warnings/)" in index

        warnings_page = (out_dir / "data" / "__warnings" / "index.md").read_text()
        assert "# Warnings" in warnings_page
        # md_escape is applied to bare substitutions by the finalize hook —
        # punctuation in path / message survives as backslash-escaped source
        # that CommonMark renders back to the original characters.
        assert f"**{md_escape('albums.yaml')}:3:5**" in warnings_page
        assert (
            md_escape("x-ref albums.artist_id = 'ghost' has no match in artists.id")
            in warnings_page
        )

    def test_pluralises_warning_count(self, tmp_path: Path) -> None:
        upstream = tmp_path / "generate"
        (upstream / "data").mkdir(parents=True)
        (upstream / "data" / "index.md").write_text("# Root\n")
        report = BuildReport(
            diagnostics=tuple(
                DiagnosticEntry(
                    file=f"f{i}.yaml",
                    line=i,
                    column=1,
                    message=f"problem {i}",
                    severity="warning",
                )
                for i in range(1, 4)
            ),
        )
        report.write(upstream / "reports")

        out_dir = tmp_path / "reconcile"
        reconcile(data_dir=upstream, out_dir=out_dir)

        assert (
            "3 warnings — [view](__warnings/)"
            in (out_dir / "data" / "index.md").read_text()
        )

    def test_renders_error_page_when_upstream_has_errors(self, tmp_path: Path) -> None:
        upstream = tmp_path / "generate"
        (upstream / "data").mkdir(parents=True)
        # Stale data left over from a previous successful run.
        (upstream / "data" / "stale.md").write_text("stale\n")
        report = BuildReport(errors=(ErrorEntry(message="boom"),))
        report.write(upstream / "reports")

        out_dir = tmp_path / "reconcile"
        reconcile(data_dir=upstream, out_dir=out_dir)

        # Build report page is rendered, stale upstream data is not propagated.
        error_page = (out_dir / "data" / "index.md").read_text()
        assert error_page.startswith("# Build Failed - Another Mood")
        assert not (out_dir / "data" / "stale.md").exists()
