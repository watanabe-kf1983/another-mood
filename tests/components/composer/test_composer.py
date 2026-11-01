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

        # Catalog dir simulates query_deriver output: the data catalog
        # and the views with their derived entities.
        catalog = tmp_path / "catalog" / "data"
        _write_model(
            catalog / "views" / "name_query.json",
            dedent("""\
                __definition:
                  views:
                    - id: doc.names
                      from: [items]
                      select:
                        - {item: [name], as: [name]}
                  entities:
                    - id: doc.names
                      item_type:
                        id: doc.names.item
                        attributes:
                          - {id: name, type: string, required: true}
                      builtin: false
                      view: true
            """),
        )

        _write_model(
            catalog / "data-catalog" / "schema.json",
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
            catalog_dir=tmp_path / "catalog",
            out_dir=out,
        )

        data_out = out / "data"
        # Passthrough: each input file is copied bytewise into a dedicated subdir.
        for src, sub in ((contents, "contents"), (catalog, "catalog")):
            for f in src.rglob("*.json"):
                dst = data_out / sub / f.relative_to(src)
                assert dst.read_text() == f.read_text()

        # View result: applied records only, at the path the view name
        # spells; entities flow via the catalog passthrough.
        assert json.loads(
            (data_out / "view-results" / "doc.names.json").read_text()
        ) == {"doc": {"names": [{"name": "a"}, {"name": "b"}]}}

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
        catalog = tmp_path / "catalog"
        _write_model(
            catalog / "con_query.json",
            dedent("""\
                __definition:
                  views:
                    - id: con
                      from: [items]
                      select:
                        - {item: [name], as: [name]}
            """),
        )
        with pytest.raises(WindowsReservedNameError):
            compose.fn(
                contents_dir=contents,
                catalog_dir=catalog,
                out_dir=tmp_path / "composed",
            )

    def test_empty_catalog_dir(self, tmp_path: Path) -> None:
        contents = tmp_path / "contents" / "data"
        _write(contents / "data.json", '{"key": "value"}')

        (tmp_path / "catalog" / "data").mkdir(parents=True)

        out = tmp_path / "composed"
        compose(
            contents_dir=tmp_path / "contents",
            catalog_dir=tmp_path / "catalog",
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

        catalog = tmp_path / "catalog"
        _write_model(
            catalog / "chain.json",
            dedent("""\
                __definition:
                  views:
                    - id: high_values
                      from: [projected]
                      where: {field: [value], operator: gte, target: 3}
                    - id: projected
                      from: [items]
                      select:
                        - {item: [name], as: [name]}
                        - {item: [value], as: [value]}
            """),
        )

        out = tmp_path / "composed"
        compose.fn(
            contents_dir=contents,
            catalog_dir=catalog,
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

        Demonstrates that the data catalog (under catalog_dir) is
        merged into ``sources`` alongside contents and queries, so a
        query can walk the catalog itself — the F8 self-description
        plumbing lands here.
        """
        (tmp_path / "contents" / "data").mkdir(parents=True)

        # Two catalog entries (one user-defined, one builtin) so the
        # query result can be checked for both pass-through and filtering.
        catalog = tmp_path / "catalog" / "data"
        _write_model(
            catalog / "data-catalog" / "schema.json",
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

        _write_model(
            catalog / "views" / "all_entities.json",
            dedent("""\
                __definition:
                  views:
                    - id: entity_ids
                      from: [__definition, entities]
                      select:
                        - {item: [id], as: [id]}
                  entities: []
            """),
        )

        out = tmp_path / "composed"
        compose(
            contents_dir=tmp_path / "contents",
            catalog_dir=tmp_path / "catalog",
            out_dir=out,
        )

        assert json.loads(
            (out / "data" / "view-results" / "entity_ids.json").read_text()
        ) == {"entity_ids": [{"id": "alpha"}, {"id": "beta"}]}
