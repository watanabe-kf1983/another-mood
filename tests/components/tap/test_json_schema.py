"""Tests for json_schema — the tap document's schema from the catalog tree."""

from another_mood.components.shared import data_catalog as dc
from another_mood.components.tap.json_schema import SCHEMA_DIALECT, document_schema


def _edge(
    name: str, type_: str = "string", *, required: bool = True, **kw: object
) -> dc.Edge:
    return dc.Edge(name=name, type=type_, required=required, **kw)  # type: ignore[arg-type]


class TestRoot:
    def test_top_level_keys_become_properties(self) -> None:
        root = dc.Node(
            children=[
                (_edge("title"), dc.Node()),
                (_edge("count", "integer", required=False), dc.Node()),
            ]
        )
        assert document_schema(root) == {
            "$schema": SCHEMA_DIALECT,
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["title"],
        }

    def test_required_is_omitted_when_no_key_is_required(self) -> None:
        root = dc.Node(
            children=[(_edge("members", "object[]", required=False), dc.Node())]
        )
        assert "required" not in document_schema(root)

    def test_empty_tree_is_an_open_object(self) -> None:
        assert document_schema(dc.Node()) == {
            "$schema": SCHEMA_DIALECT,
            "type": "object",
            "properties": {},
        }


class TestShapes:
    def test_singleton_object_nests_properties(self) -> None:
        address = dc.Node(children=[(_edge("city"), dc.Node())])
        root = dc.Node(children=[(_edge("address", "object"), address)])
        assert document_schema(root)["properties"] == {
            "address": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            }
        }

    def test_collection_wraps_the_record_in_an_array(self) -> None:
        item = dc.Node(children=[(_edge("id"), dc.Node())])
        root = dc.Node(children=[(_edge("members", "object[]"), item)])
        assert document_schema(root)["properties"] == {
            "members": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                },
            }
        }

    def test_each_array_suffix_is_one_layer(self) -> None:
        root = dc.Node(children=[(_edge("grid", "integer[][]"), dc.Node())])
        assert document_schema(root)["properties"] == {
            "grid": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "integer"}},
            }
        }

    def test_object_leaf_stays_open(self) -> None:
        root = dc.Node(children=[(_edge("metadata", "object"), dc.Node())])
        assert document_schema(root)["properties"] == {"metadata": {"type": "object"}}


class TestAnnotations:
    def test_scalar_metadata_and_validation_pass_through(self) -> None:
        edge = _edge(
            "role",
            metadata={"title": "Role", "description": "What the member does."},
            validation={"enum": ["engineer", "designer"]},
        )
        root = dc.Node(children=[(edge, dc.Node())])
        assert document_schema(root)["properties"] == {
            "role": {
                "title": "Role",
                "description": "What the member does.",
                "type": "string",
                "enum": ["engineer", "designer"],
            }
        }

    def test_validation_rides_down_to_the_items(self) -> None:
        edge = _edge("tags", "string[]", validation={"minLength": 1})
        root = dc.Node(children=[(edge, dc.Node())])
        assert document_schema(root)["properties"] == {
            "tags": {"type": "array", "items": {"type": "string", "minLength": 1}}
        }

    def test_collection_metadata_annotates_the_array_and_record_metadata_the_items(
        self,
    ) -> None:
        edge = _edge("members", "object[]", metadata={"title": "Members"})
        item = dc.Node(
            metadata={"description": "One member."},
            children=[(_edge("id"), dc.Node())],
        )
        root = dc.Node(children=[(edge, item)])
        assert document_schema(root)["properties"] == {
            "members": {
                "title": "Members",
                "type": "array",
                "items": {
                    "description": "One member.",
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                },
            }
        }

    def test_x_ref_is_not_a_schema_keyword(self) -> None:
        edge = _edge("owner", x_ref=dc.XRef(entity="members", attribute="id"))
        root = dc.Node(children=[(edge, dc.Node())])
        assert document_schema(root)["properties"] == {"owner": {"type": "string"}}


class TestFromFlatCatalog:
    def test_dotted_attribute_ids_come_back_as_nesting(self) -> None:
        catalog = [
            dc.Entity(
                id=dc.ROOT_ENTITY_ID,
                item_type=dc.ObjectType(
                    id="__root.item",
                    origin_item_type="__root.item",
                    attributes=[
                        dc.Attribute(
                            id="members",
                            type="object[]",
                            required=False,
                            child_entity="members",
                            child_item_type="members.item",
                        ),
                    ],
                ),
            ),
            dc.Entity(
                id="members",
                parent_entity=dc.ROOT_ENTITY_ID,
                item_type=dc.ObjectType(
                    id="members.item",
                    origin_item_type="members.item",
                    attributes=[
                        dc.Attribute(id="id", type="string", required=True),
                        dc.Attribute(id="address", type="object", required=False),
                        dc.Attribute(id="address.city", type="string", required=True),
                    ],
                ),
            ),
        ]
        schema = document_schema(dc.build_tree(catalog))
        assert schema["properties"] == {
            "members": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "address": {
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                            "required": ["city"],
                        },
                    },
                    "required": ["id"],
                },
            }
        }
        assert "required" not in schema
