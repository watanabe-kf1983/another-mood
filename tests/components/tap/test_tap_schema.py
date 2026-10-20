"""Tests for Tap schema — the catalog's records become the document's schema."""

import json
from pathlib import Path

from another_mood.components.shared import data_catalog as dc
from another_mood.components.tap.tap_schema import TAP_SCHEMA_NAME, tap_schema


def _root_entity(*attributes: dc.Attribute) -> dict[str, object]:
    return dict(
        dc.Entity(
            id=dc.ROOT_ENTITY_ID,
            item_type=dc.ObjectType(
                id="__root.item", origin_item_type="__root.item", attributes=attributes
            ),
        ).to_dict()
    )


class TestTapSchema:
    def test_writes_the_schema_the_catalog_describes(self, tmp_path: Path) -> None:
        root = _root_entity(
            dc.Attribute(id="items", type="integer[]", required=True),
            dc.Attribute(id="names", type="string[]", required=False),
        )
        catalog = tmp_path / "upstream" / "data"
        catalog.mkdir(parents=True)
        (catalog / "catalog.json").write_text(
            json.dumps({"__definition": {"entities": [root]}}), encoding="utf-8"
        )

        out = tmp_path / "tap_schema"
        tap_schema(catalog_dir=tmp_path / "upstream", out_dir=out)

        schema = json.loads(
            (out / "data" / TAP_SCHEMA_NAME).read_text(encoding="utf-8")
        )
        assert schema["properties"] == {
            "items": {"type": "array", "items": {"type": "integer"}},
            "names": {"type": "array", "items": {"type": "string"}},
        }
        assert schema["required"] == ["items"]
