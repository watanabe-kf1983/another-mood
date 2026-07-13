"""Tests for Composer — passthrough copy and query application."""

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


class TestCompose:
    def test_passthrough_and_query(self, tmp_path: Path) -> None:
        contents = tmp_path / "contents" / "data"
        _write(
            contents / "items.yaml",
            dedent("""\
                items:
                  - {name: a, value: 1}
                  - {name: b, value: 2}
            """),
        )

        # Queries dir simulates query_deriver output: queries plus their
        # derived view entities under __definition.
        queries = tmp_path / "queries" / "data"
        _write(
            queries / "name_query.yaml",
            dedent("""\
                __definition:
                  queries:
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
        _write(
            data_catalog / "schema.yaml",
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

        out = tmp_path / "views"
        compose(
            contents_dir=tmp_path / "contents",
            queries_dir=tmp_path / "queries",
            data_catalog_dir=tmp_path / "data-catalog",
            out_dir=out,
        )

        data_out = out / "data"
        # Passthrough: each input file is copied bytewise into a dedicated subdir.
        for src, sub in (
            (contents, "contents"),
            (data_catalog, "data-catalog"),
            (queries, "queries"),
        ):
            for f in src.rglob("*.yaml"):
                dst = data_out / sub / f.relative_to(src)
                assert dst.read_text() == f.read_text()

        # Query result: applied records only; entities flow via the queries passthrough.
        assert yaml.safe_load(
            (data_out / "query-results" / "names.yaml").read_text()
        ) == {"names": [{"name": "a"}, {"name": "b"}]}

    def test_rejects_reserved_query_id(self, tmp_path: Path) -> None:
        # A query whose id is `con` would write query-results/con.yaml — a
        # Windows device name. Caught here, before the generator, since an
        # unrendered query never reaches the page-path check. Uses
        # ``compose.fn`` so the raise surfaces directly rather than as a
        # recorded build-report error.
        contents = tmp_path / "contents"
        _write(
            contents / "items.yaml",
            dedent("""\
                items:
                  - {name: a, value: 1}
            """),
        )
        queries = tmp_path / "queries"
        _write(
            queries / "con_query.yaml",
            dedent("""\
                __definition:
                  queries:
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
                queries_dir=queries,
                data_catalog_dir=data_catalog,
                out_dir=tmp_path / "views",
            )

    def test_empty_queries_dir(self, tmp_path: Path) -> None:
        contents = tmp_path / "contents" / "data"
        _write(contents / "data.yaml", "key: value\n")

        (tmp_path / "queries" / "data").mkdir(parents=True)
        (tmp_path / "data-catalog" / "data").mkdir(parents=True)

        out = tmp_path / "views"
        compose(
            contents_dir=tmp_path / "contents",
            queries_dir=tmp_path / "queries",
            data_catalog_dir=tmp_path / "data-catalog",
            out_dir=out,
        )

        assert (out / "data" / "contents" / "data.yaml").read_text() == "key: value\n"

    def test_query_reads_another_query_out_of_file_order(self, tmp_path: Path) -> None:
        """A query whose ``from:`` names another query is evaluated after
        its source, regardless of the order queries appear in the file.

        ``high_values`` reads the ``projected`` view; it is listed *first*
        so file order alone would apply it before ``projected`` exists in
        ``sources``.  Correct output proves evaluation follows dependency
        (topological) order, not file order.

        Only ``__definition.queries`` drives evaluation, so the derived
        view entities and the data catalog are irrelevant here and left
        out.  ``compose.fn`` runs the bare function without the Component
        wrapper's ``data/`` output subdir.
        """
        contents = tmp_path / "contents"
        _write(
            contents / "items.yaml",
            dedent("""\
                items:
                  - {name: a, value: 1}
                  - {name: b, value: 3}
            """),
        )

        queries = tmp_path / "queries"
        _write(
            queries / "chain.yaml",
            dedent("""\
                __definition:
                  queries:
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

        out = tmp_path / "views"
        compose.fn(
            contents_dir=contents,
            queries_dir=queries,
            data_catalog_dir=data_catalog,
            out_dir=out,
        )

        results = out / "query-results"
        assert yaml.safe_load((results / "projected.yaml").read_text()) == {
            "projected": [{"name": "a", "value": 1}, {"name": "b", "value": 3}]
        }
        assert yaml.safe_load((results / "high_values.yaml").read_text()) == {
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
        _write(
            data_catalog / "schema.yaml",
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

        queries = tmp_path / "queries" / "data"
        _write(
            queries / "all_entities.yaml",
            dedent("""\
                __definition:
                  queries:
                    - id: entity_ids
                      from: __definition.entities
                      select:
                        - {item: id, as: id}
                  entities: []
            """),
        )

        out = tmp_path / "views"
        compose(
            contents_dir=tmp_path / "contents",
            queries_dir=tmp_path / "queries",
            data_catalog_dir=tmp_path / "data-catalog",
            out_dir=out,
        )

        assert yaml.safe_load(
            (out / "data" / "query-results" / "entity_ids.yaml").read_text()
        ) == {"entity_ids": [{"id": "alpha"}, {"id": "beta"}]}
