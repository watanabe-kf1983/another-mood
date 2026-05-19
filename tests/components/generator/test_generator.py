"""Tests for generate and reconcile — the Markdown-producing components."""

from pathlib import Path
from typing import Any

import yaml

from jinja2 import Undefined

from another_mood.components.generator.generator import (
    _pluck,  # pyright: ignore[reportPrivateUsage]
    _to_yaml,  # pyright: ignore[reportPrivateUsage]
    _walk_entity,  # pyright: ignore[reportPrivateUsage]
    generate,
    reconcile,
)
from another_mood.components.shared.component.build_report import (
    BuildReport,
    ErrorEntry,
)


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
            "{% if '__views' in __views %}yes{% else %}no{% endif %}"
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
        (templates_dir / "index.md").write_text('{% mood_view "bad" with x %}')

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
        stages = report["__build_report"]["stages"]
        assert any(s["component"] == "generate" and s["result"] == "ng" for s in stages)
        assert report["__build_report"]["errors"]


class TestPluckFilter:
    """Unit tests for the `pluck` filter function."""

    def test_dotted_path_returns_raw_value(self) -> None:
        # Regression: a nested collection reached via a dotted path
        # (e.g. `hobby.pets` after E10's singleton flattening) must
        # come back as a raw list so the table-view template can
        # `length`-count it. Falsy real values must pass through, not
        # be folded into "missing".
        row = {"hobby": {"pets": [{"id": "dog1"}]}, "done": False}
        assert _pluck(row, "hobby.pets") == [{"id": "dog1"}]
        assert _pluck(row, "done") is False

    def test_unreachable_path_yields_undefined(self) -> None:
        assert isinstance(_pluck({"x": 1}, "missing"), Undefined)
        assert isinstance(_pluck({"x": 1}, "x.y"), Undefined)


class TestWalkEntityFilter:
    """Unit tests for the `walk_entity` filter function."""

    def test_root_entity_returns_views_list(self) -> None:
        views = {"posts": [{"id": "a"}, {"id": "b"}]}
        entities = [{"id": "posts"}]
        assert _walk_entity(views, "posts", entities) == [{"id": "a"}, {"id": "b"}]

    def test_single_step_child_flattens_array_attribute(self) -> None:
        # A parent entity (`entities`) whose rows carry an array attribute
        # (`fields`): walking to the child entity flattens the per-parent
        # arrays into a single list. Same pattern is exercised end-to-end
        # by `artists.members` in showcase/music.
        views = {
            "entities": [
                {"id": "user", "fields": [{"id": "id"}, {"id": "name"}]},
                {"id": "role", "fields": [{"id": "id"}]},
            ]
        }
        entities = [
            {"id": "entities"},
            {"id": "entities.fields", "parent_entity": "entities"},
        ]
        assert _walk_entity(views, "entities.fields", entities) == [
            {"id": "id"},
            {"id": "name"},
            {"id": "id"},
        ]

    def test_singleton_traversed_suffix(self) -> None:
        # The catalog encodes `item_type.attributes` as the suffix that
        # carries the array attribute past a singleton (`item_type`).
        # `pluck`'s dotted lookup handles that step transparently.
        views = {
            "__definition": {
                "entities": [
                    {"id": "user", "item_type": {"attributes": [{"id": "id"}]}},
                    {"id": "role", "item_type": {"attributes": [{"id": "name"}]}},
                ]
            }
        }
        entities = [
            {"id": "__definition.entities"},
            {
                "id": "__definition.entities.item_type.attributes",
                "parent_entity": "__definition.entities",
            },
        ]
        assert _walk_entity(
            views, "__definition.entities.item_type.attributes", entities
        ) == [{"id": "id"}, {"id": "name"}]

    def test_multi_step_chain(self) -> None:
        # Three-level chain: erds → erds.entities → erds.entities.fields.
        views = {
            "erds": [
                {
                    "id": "user-management",
                    "entities": [
                        {"id": "user", "fields": [{"id": "id"}]},
                        {"id": "role", "fields": [{"id": "name"}, {"id": "perm"}]},
                    ],
                },
            ]
        }
        entities = [
            {"id": "erds"},
            {"id": "erds.entities", "parent_entity": "erds"},
            {"id": "erds.entities.fields", "parent_entity": "erds.entities"},
        ]
        assert _walk_entity(views, "erds.entities.fields", entities) == [
            {"id": "id"},
            {"id": "name"},
            {"id": "perm"},
        ]

    def test_missing_root_yields_empty(self) -> None:
        # An entity declared in the catalog but with no records yet:
        # template's `{% if rows %}` guard renders `(no records)`.
        entities = [{"id": "posts"}]
        assert _walk_entity({}, "posts", entities) == []

    def test_missing_intermediate_suffix_skips_row(self) -> None:
        # A parent row missing the child array contributes zero children
        # rather than raising — matches the silent-skip behaviour of the
        # previous query_from filter so partial data still renders.
        views = {
            "entities": [
                {"id": "user", "fields": [{"id": "id"}]},
                {"id": "role"},
            ]
        }
        entities = [
            {"id": "entities"},
            {"id": "entities.fields", "parent_entity": "entities"},
        ]
        assert _walk_entity(views, "entities.fields", entities) == [{"id": "id"}]


class TestToYamlFilter:
    """Unit tests for the `to_yaml` filter function."""

    def test_flat_mapping(self) -> None:
        assert _to_yaml({"title": "Hello", "description": "world"}) == (
            "title: Hello\ndescription: world"
        )

    def test_preserves_key_order(self) -> None:
        # `enum: [easy, medium, hard]` style validation values must keep
        # author-defined ordering.
        assert _to_yaml({"enum": ["easy", "medium", "hard"]}) == (
            "enum:\n- easy\n- medium\n- hard"
        )

    def test_nested(self) -> None:
        assert _to_yaml({"a": {"b": 1}}) == "a:\n  b: 1"

    def test_none_yields_empty(self) -> None:
        assert _to_yaml(None) == ""

    def test_undefined_yields_empty(self) -> None:
        assert _to_yaml(Undefined()) == ""

    def test_flow_style_single_line(self) -> None:
        # `flow=True` keeps the output on a single line — used in Markdown
        # table cells where embedded newlines would break the row.
        assert _to_yaml({"title": "Hi", "n": 1}, True) == "{title: Hi, n: 1}"
        assert _to_yaml({"enum": ["easy", "medium"]}, True) == (
            "{enum: [easy, medium]}"
        )

    def test_flow_style_no_soft_wrap_for_long_values(self) -> None:
        # PyYAML wraps flow output at width=80 by default; that newline would
        # break the Markdown table row this filter is rendered into.
        long_description = (
            "Stable identifier derived from the Markdown file's path "
            "(without extension)."
        )
        result = _to_yaml({"description": long_description, "title": "Prose id"}, True)
        assert "\n" not in result


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
        report = BuildReport(errors=(ErrorEntry(message="boom"),))
        report.write(upstream / "reports")

        out_dir = tmp_path / "reconcile"
        reconcile(data_dir=upstream, out_dir=out_dir)

        # Build report page is rendered, stale upstream data is not propagated.
        error_page = (out_dir / "data" / "index.md").read_text()
        assert error_page.startswith("# Build Failed - Another Mood")
        assert not (out_dir / "data" / "stale.md").exists()
