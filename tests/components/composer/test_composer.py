"""Tests for Composer — passthrough copy and query application."""

from pathlib import Path

import yaml

from another_mood.components.composer.composer import compose


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestCompose:
    def test_passthrough_and_query(self, tmp_path: Path) -> None:
        contents = tmp_path / "contents" / "data"
        _write(
            contents / "items.yaml",
            "items:\n  - {name: a, value: 1}\n  - {name: b, value: 2}\n",
        )

        # Queries dir simulates query_deriver output: queries plus their
        # derived view entities under __definition.
        queries = tmp_path / "queries" / "data"
        _write(
            queries / "name_query.yaml",
            "__definition:\n"
            "  queries:\n"
            "    - id: names\n"
            "      from: items\n"
            "      select:\n"
            "        - {item: name}\n"
            "  entities:\n"
            "    - id: names\n"
            "      item_type:\n"
            "        id: names.item\n"
            "        attributes:\n"
            "          - {id: name, type: string, required: true}\n"
            "      builtin: false\n"
            "      view: true\n",
        )

        data_catalog = tmp_path / "data-catalog" / "data"
        _write(
            data_catalog / "schema.yaml",
            "__definition:\n"
            "  entities:\n"
            "    - id: items\n"
            "      item_type:\n"
            "        id: items.item\n"
            "        attributes:\n"
            "          - {id: name, type: string, required: true}\n"
            "          - {id: value, type: integer, required: true}\n",
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
