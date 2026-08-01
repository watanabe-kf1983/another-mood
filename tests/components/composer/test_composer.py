"""Tests for Composer — passthrough copy and query application."""

import json
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from another_mood.components.composer.composer import compose
from another_mood.components.shared.windows_reserved_name import (
    WindowsReservedNameError,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_model(path: Path, yaml_text: str) -> None:
    """Write an intermediate-representation file from readable YAML text.

    Stage outputs are JSON; the fixtures stay YAML so the shape of the
    data remains legible in the test source.
    """
    _write(path, json.dumps(yaml.safe_load(yaml_text)))


class TestCompose:
    def test_passthrough_and_query(self, tmp_path: Path) -> None:
        contents = tmp_path / "contents" / "data"
        _write_model(
            contents / "items.json",
            dedent("""\
                items:
                  - {name: a, value: 1}
                  - {name: b, value: 2}
            """),
        )

        # Views dir simulates query_deriver output: views plus their
        # derived view entities under __definition.
        views = tmp_path / "views" / "data"
        _write_model(
            views / "name_query.json",
            dedent("""\
                __definition:
                  views:
                    - id: names
                      from: items
                      select:
                        - {item: name, as: name}
                  entities:
                    - id: names
                      item_type:
                        id: names.item
                        attributes:
                          - {id: name, type: string, required: true}
                      builtin: false
                      view: true
            """),
        )

        data_catalog = tmp_path / "data-catalog" / "data"
        _write_model(
            data_catalog / "schema.json",
            dedent("""\
                __definition:
                  entities:
                    - id: items
                      item_type:
                        id: items.item
                        attributes:
                          - {id: name, type: string, required: true}
                          - {id: value, type: integer, required: true}
            """),
        )

        out = tmp_path / "composed"
        compose(
            contents_dir=tmp_path / "contents",
            views_dir=tmp_path / "views",
            data_catalog_dir=tmp_path / "data-catalog",
            out_dir=out,
        )

        data_out = out / "data"
        # Passthrough: each input file is copied bytewise into a dedicated subdir.
        for src, sub in (
            (contents, "contents"),
            (data_catalog, "data-catalog"),
            (views, "views"),
        ):
            for f in src.rglob("*.json"):
                dst = data_out / sub / f.relative_to(src)
                assert dst.read_text() == f.read_text()

        # View result: applied records only; entities flow via the views passthrough.
        assert json.loads((data_out / "view-results" / "names.json").read_text()) == {
            "names": [{"name": "a"}, {"name": "b"}]
        }

    def test_rejects_reserved_query_id(self, tmp_path: Path) -> None:
        # A query whose id is `con` would write view-results/con.json — a
        # Windows device name. Caught here, before the generator, since an
        # unrendered query never reaches the page-path check. Uses
        # ``compose.fn`` so the raise surfaces directly rather than as a
        # recorded build-report error.
        contents = tmp_path / "contents"
        _write_model(
            contents / "items.json",
            dedent("""\
                items:
                  - {name: a, value: 1}
            """),
        )
        views = tmp_path / "views"
        _write_model(
            views / "con_query.json",
            dedent("""\
                __definition:
                  views:
                    - id: con
                      from: items
                      select:
                        - {item: name, as: name}
            """),
        )
        data_catalog = tmp_path / "data-catalog"
        data_catalog.mkdir()

        with pytest.raises(WindowsReservedNameError):
            compose.fn(
                contents_dir=contents,
                views_dir=views,
                data_catalog_dir=data_catalog,
                out_dir=tmp_path / "composed",
            )

    def test_empty_views_dir(self, tmp_path: Path) -> None:
        contents = tmp_path / "contents" / "data"
        _write(contents / "data.json", '{"key": "value"}')

        (tmp_path / "views" / "data").mkdir(parents=True)
        (tmp_path / "data-catalog" / "data").mkdir(parents=True)

        out = tmp_path / "composed"
        compose(
            contents_dir=tmp_path / "contents",
            views_dir=tmp_path / "views",
            data_catalog_dir=tmp_path / "data-catalog",
            out_dir=out,
        )

        assert (
            out / "data" / "contents" / "data.json"
        ).read_text() == '{"key": "value"}'

    def test_query_reads_another_query_out_of_file_order(self, tmp_path: Path) -> None:
        """A query whose ``from:`` names another query is evaluated after
        its source, regardless of the order queries appear in the file.

        ``high_values`` reads the ``projected`` view; it is listed *first*
        so file order alone would apply it before ``projected`` exists in
        ``sources``.  Correct output proves evaluation follows dependency
        (topological) order, not file order.

        Only ``__definition.views`` drives evaluation, so the derived
        view entities and the data catalog are irrelevant here and left
        out.  ``compose.fn`` runs the bare function without the Component
        wrapper's ``data/`` output subdir.
        """
        contents = tmp_path / "contents"
        _write_model(
            contents / "items.json",
            dedent("""\
                items:
                  - {name: a, value: 1}
                  - {name: b, value: 3}
            """),
        )

        views = tmp_path / "views"
        _write_model(
            views / "chain.json",
            dedent("""\
                __definition:
                  views:
                    - id: high_values
                      from: projected
                      where: {value: {gte: 3}}
                    - id: projected
                      from: items
                      select:
                        - {item: name, as: name}
                        - {item: value, as: value}
            """),
        )

        data_catalog = tmp_path / "data-catalog"
        data_catalog.mkdir()

        out = tmp_path / "composed"
        compose.fn(
            contents_dir=contents,
            views_dir=views,
            data_catalog_dir=data_catalog,
            out_dir=out,
        )

        results = out / "view-results"
        assert json.loads((results / "projected.json").read_text()) == {
            "projected": [{"name": "a", "value": 1}, {"name": "b", "value": 3}]
        }
        assert json.loads((results / "high_values.json").read_text()) == {
            "high_values": [{"name": "b", "value": 3}]
        }

    def test_query_can_walk_definition_entities(self, tmp_path: Path) -> None:
        """``from: __definition.entities`` returns the catalog records as data.

        Demonstrates that the data catalog (under data_catalog_dir) is
        merged into ``sources`` alongside contents and queries, so a
        query can walk the catalog itself — the F8 self-description
        plumbing lands here.
        """
        (tmp_path / "contents" / "data").mkdir(parents=True)

        # Two catalog entries (one user-defined, one builtin) so the
        # query result can be checked for both pass-through and filtering.
        data_catalog = tmp_path / "data-catalog" / "data"
        _write_model(
            data_catalog / "schema.json",
            dedent("""\
                __definition:
                  entities:
                    - id: alpha
                      item_type: {id: alpha.item, attributes: []}
                      builtin: false
                    - id: beta
                      item_type: {id: beta.item, attributes: []}
                      builtin: true
            """),
        )

        views = tmp_path / "views" / "data"
        _write_model(
            views / "all_entities.json",
            dedent("""\
                __definition:
                  views:
                    - id: entity_ids
                      from: __definition.entities
                      select:
                        - {item: id, as: id}
                  entities: []
            """),
        )

        out = tmp_path / "composed"
        compose(
            contents_dir=tmp_path / "contents",
            views_dir=tmp_path / "views",
            data_catalog_dir=tmp_path / "data-catalog",
            out_dir=out,
        )

        assert json.loads(
            (out / "data" / "view-results" / "entity_ids.json").read_text()
        ) == {"entity_ids": [{"id": "alpha"}, {"id": "beta"}]}
