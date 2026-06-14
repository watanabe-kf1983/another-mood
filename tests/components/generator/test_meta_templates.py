"""Tests for the system-only Jinja2 filters used by built-in templates."""

import pytest
from jinja2 import Undefined

from another_mood.components.generator.data_tree import wrap_tree
from another_mood.components.generator.meta_templates import (
    META_REPORTS_CONFIG,
    pluck,
    to_yaml,
    walk_entity,
)


class TestMetaReportsConfig:
    """The meta render's fixed ``file_per`` splits each built-in meta
    query's result items onto their own anchor-derived ``{view}/{id}.md``
    page.  This is the contract that keeps the diagnostics from inlining
    back into ``index.md`` — ``page_path`` returns ``index.md`` for a
    non-split node, so asserting the path covers both the split decision
    and its derivation."""

    @pytest.mark.parametrize("view", ["__meta_entity", "__table_view", "__meta_query"])
    def test_meta_query_item_splits_to_its_page(self, view: str) -> None:
        node = wrap_tree({view: [{"id": "sample"}]})[view][0]
        assert META_REPORTS_CONFIG.page_path(node) == f"{view}/sample.md"


class TestPluckFilter:
    """Unit tests for the `pluck` filter function."""

    def test_dotted_path_returns_raw_value(self) -> None:
        # Regression: a nested collection reached via a dotted path
        # (e.g. `hobby.pets` after E10's singleton flattening) must
        # come back as a raw list so the table-view template can
        # `length`-count it. Falsy real values must pass through, not
        # be folded into "missing".
        row = {"hobby": {"pets": [{"id": "dog1"}]}, "done": False}
        assert pluck(row, "hobby.pets") == [{"id": "dog1"}]
        assert pluck(row, "done") is False

    def test_unreachable_path_yields_undefined(self) -> None:
        assert isinstance(pluck({"x": 1}, "missing"), Undefined)
        assert isinstance(pluck({"x": 1}, "x.y"), Undefined)


class TestWalkEntityFilter:
    """Unit tests for the `walk_entity` filter function."""

    def test_root_entity_returns_views_list(self) -> None:
        views = {"posts": [{"id": "a"}, {"id": "b"}]}
        entities = [{"id": "posts"}]
        assert walk_entity(views, "posts", entities) == [{"id": "a"}, {"id": "b"}]

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
        assert walk_entity(views, "entities.fields", entities) == [
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
        assert walk_entity(
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
        assert walk_entity(views, "erds.entities.fields", entities) == [
            {"id": "id"},
            {"id": "name"},
            {"id": "perm"},
        ]

    def test_missing_root_yields_empty(self) -> None:
        # An entity declared in the catalog but with no records yet:
        # template's `{% if rows %}` guard renders `(no records)`.
        entities = [{"id": "posts"}]
        assert walk_entity({}, "posts", entities) == []

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
        assert walk_entity(views, "entities.fields", entities) == [{"id": "id"}]


class TestToYamlFilter:
    """Unit tests for the `to_yaml` filter function."""

    def test_flat_mapping(self) -> None:
        assert to_yaml({"title": "Hello", "description": "world"}) == (
            "title: Hello\ndescription: world"
        )

    def test_preserves_key_order(self) -> None:
        # `enum: [easy, medium, hard]` style validation values must keep
        # author-defined ordering.
        assert to_yaml({"enum": ["easy", "medium", "hard"]}) == (
            "enum:\n- easy\n- medium\n- hard"
        )

    def test_nested(self) -> None:
        assert to_yaml({"a": {"b": 1}}) == "a:\n  b: 1"

    def test_none_yields_empty(self) -> None:
        assert to_yaml(None) == ""

    def test_undefined_yields_empty(self) -> None:
        assert to_yaml(Undefined()) == ""

    def test_flow_style_single_line(self) -> None:
        # `flow=True` keeps the output on a single line — used in Markdown
        # table cells where embedded newlines would break the row.
        assert to_yaml({"title": "Hi", "n": 1}, True) == "{title: Hi, n: 1}"
        assert to_yaml({"enum": ["easy", "medium"]}, True) == ("{enum: [easy, medium]}")

    def test_flow_style_no_soft_wrap_for_long_values(self) -> None:
        # PyYAML wraps flow output at width=80 by default; that newline would
        # break the Markdown table row this filter is rendered into.
        long_description = (
            "Stable identifier derived from the Markdown file's path "
            "(without extension)."
        )
        result = to_yaml({"description": long_description, "title": "Prose id"}, True)
        assert "\n" not in result

    def test_flow_style_embedded_newlines_become_escapes(self) -> None:
        # A string value carrying real newlines would otherwise be emitted
        # as a multi-line single-quoted scalar, breaking the surrounding
        # table row. The flow dumper forces double-quoted style so newlines
        # become `\n` escapes and the cell stays on one line.
        result = to_yaml({"description": "first\n\nsecond"}, True)
        assert "\n" not in result
        assert "first\\n\\nsecond" in result
