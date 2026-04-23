"""Tests for generate and reconcile — the Markdown-producing components."""

from pathlib import Path
from typing import Any

import yaml

from another_mood.components.generator.generator import (
    _at,  # pyright: ignore[reportPrivateUsage]
    _query_from,  # pyright: ignore[reportPrivateUsage]
    generate,
    reconcile,
)
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

        # User reports are rendered under reports/.
        assert (out_dir / "data" / "reports" / "index.md").read_text() == "# Hello\n"
        # Metadata root is always rendered at the site root.
        assert (out_dir / "data" / "index.md").exists()

    def test_views_snapshot_excludes_self(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data" / "data"
        data_dir.mkdir(parents=True)
        _write_yaml(data_dir / "data.yaml", {"x": 1})

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "index.md").write_text(
            "{% if '__views' in __views[0] %}yes{% else %}no{% endif %}"
        )

        out_dir = tmp_path / "output"
        generate(
            data_dir=tmp_path / "data",
            templates_dir=templates_dir,
            out_dir=out_dir,
        )

        assert (out_dir / "data" / "reports" / "index.md").read_text() == "no"

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


class TestAtFilter:
    """Unit tests for the `at` filter function."""

    def test_scalar(self) -> None:
        assert _at({"x": "hi"}, "x") == "hi"

    def test_nested_dotted_path(self) -> None:
        assert _at({"m": {"title": "T"}}, "m.title") == "T"

    def test_missing_path_returns_empty(self) -> None:
        assert _at({"x": 1}, "missing") == ""

    def test_stringifies_non_str(self) -> None:
        assert _at({"x": True}, "x") == "True"
        assert _at({"x": [1, 2]}, "x") == "[1, 2]"


class TestQueryFromFilter:
    """Unit tests for the `query_from` filter function."""

    def test_resolves_entity_id(self) -> None:
        parents = [{"items": [{"id": "a"}, {"id": "b"}]}]
        assert _query_from(parents, "items") == [{"id": "a"}, {"id": "b"}]

    def test_flattens_nested_entity(self) -> None:
        parents = [
            {
                "parents": [
                    {"id": "p1", "children": [{"id": "c1"}, {"id": "c2"}]},
                    {"id": "p2", "children": [{"id": "c3"}]},
                ]
            }
        ]
        assert _query_from(parents, "parents.children") == [
            {"id": "c1"},
            {"id": "c2"},
            {"id": "c3"},
        ]

    def test_empty_for_missing_key(self) -> None:
        # Entity declared in the catalog but no records populated yet
        # (common in a scaffolded project). Should return [], not raise.
        assert _query_from([{"x": 1}], "missing") == []


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
        assert error_page.startswith("# Build Failed - Another Mood")
        assert not (out_dir / "data" / "stale.md").exists()
