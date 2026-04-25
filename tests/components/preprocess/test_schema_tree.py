"""Tests for SchemaTree — unit tests derived from schema-inspector.md spec rules."""

import yaml

from another_mood.components.preprocess import data_catalog as dc
from another_mood.components.preprocess.schema_tree import (
    ArrayNode,
    ObjectNode,
    SchemaProperty,
    ValueNode,
    build_schema_tree,
    collect_entities,
)

# fmt: off


# ── A→B: build_schema_tree ──────────────────────────────────────────
#
# Spec: "スキーマ → SchemaTree の変換ルール" (schema-inspector.md)


class TestBuildSchemaTree:
    """build_schema_tree: JSON Schema → SchemaTree node."""

    def test_object_properties(self) -> None:
        """object + properties → ObjectNode with Field per property."""
        tree = build_schema_tree(yaml.safe_load("""
            type: object
            properties:
              name: { type: string }
              age: { type: integer }
            additionalProperties: false
            required: [name]
        """))
        assert tree == ObjectNode(properties=[
            SchemaProperty("name", True,  ValueNode(type="string")),
            SchemaProperty("age",  False, ValueNode(type="integer")),
        ])

    def test_additional_properties_object(self) -> None:
        """object + additionalProperties: {type: object} → ArrayNode with implicit id."""
        tree = build_schema_tree(yaml.safe_load("""
            type: object
            additionalProperties:
              type: object
              properties:
                title: { type: string }
              additionalProperties: false
              required: [title]
        """))
        assert tree == ArrayNode(child=ObjectNode(properties=[
            SchemaProperty("id",    True, ValueNode(type="string")),
            SchemaProperty("title", True, ValueNode(type="string")),
        ]))

    def test_additional_properties_scalar(self) -> None:
        """object + additionalProperties: {type: T} (non-object) → ArrayNode({id, value})."""
        tree = build_schema_tree(yaml.safe_load("""
            type: object
            additionalProperties: { type: number }
        """))
        assert tree == ArrayNode(child=ObjectNode(properties=[
            SchemaProperty("id",    True, ValueNode(type="string")),
            SchemaProperty("value", True, ValueNode(type="number")),
        ]))

    def test_array_items(self) -> None:
        """array + items → ArrayNode(child=recursive)."""
        tree = build_schema_tree(yaml.safe_load("""
            type: array
            items:
              type: object
              properties:
                x: { type: integer }
              additionalProperties: false
        """))
        assert tree == ArrayNode(child=ObjectNode(properties=[
            SchemaProperty("x", False, ValueNode(type="integer")),
        ]))

    def test_array_scalar_items(self) -> None:
        """array + items: scalar → ArrayNode(child=ValueNode)."""
        tree = build_schema_tree(yaml.safe_load("""
            type: array
            items: { type: boolean }
        """))
        assert tree == ArrayNode(child=ValueNode(type="boolean"))

    def test_scalar_type(self) -> None:
        """scalar type → ValueNode."""
        tree = build_schema_tree(yaml.safe_load("type: number"))
        assert tree == ValueNode(type="number")

    def test_metadata_on_object(self) -> None:
        """metadata keywords are extracted to node.metadata on any node type."""
        tree = build_schema_tree(yaml.safe_load("""
            type: object
            title: My Object
            description: A test object
            properties:
              x: { type: string }
            additionalProperties: false
        """))
        assert isinstance(tree, ObjectNode)
        assert tree.metadata == {"title": "My Object", "description": "A test object"}

    def test_metadata_on_value(self) -> None:
        """metadata and validation on ValueNode."""
        tree = build_schema_tree(yaml.safe_load("""
            type: string
            title: A label
            minLength: 1
            pattern: "^[A-Z]"
        """))
        assert tree == ValueNode(
            type="string",
            metadata={"title": "A label"},
            validation={"minLength": 1, "pattern": "^[A-Z]"},
        )

    def test_required_propagation(self) -> None:
        """Field.required reflects parent's required list."""
        tree = build_schema_tree(yaml.safe_load("""
            type: object
            properties:
              a: { type: string }
              b: { type: string }
              c: { type: string }
            additionalProperties: false
            required: [a, c]
        """))
        assert isinstance(tree, ObjectNode)
        assert [(f.name, f.required) for f in tree.properties] == [
            ("a", True), ("b", False), ("c", True),
        ]

    def test_object_containing_object(self) -> None:
        """Object-Object: property with nested object (properties pattern)."""
        tree = build_schema_tree(yaml.safe_load("""
            type: object
            properties:
              address:
                type: object
                properties:
                  city: { type: string }
                additionalProperties: false
            additionalProperties: false
        """))
        assert tree == ObjectNode(properties=[
            SchemaProperty("address", False, ObjectNode(properties=[
                SchemaProperty("city", False, ValueNode(type="string")),
            ])),
        ])

    def test_object_containing_array(self) -> None:
        """Object-Array: property with array type."""
        tree = build_schema_tree(yaml.safe_load("""
            type: object
            properties:
              scores:
                type: array
                items: { type: integer }
            additionalProperties: false
        """))
        assert tree == ObjectNode(properties=[
            SchemaProperty("scores", False, ArrayNode(child=ValueNode(type="integer"))),
        ])

    def test_object_mixed_children(self) -> None:
        """Object-[Object, Array, Value]: properties with all three child types."""
        tree = build_schema_tree(yaml.safe_load("""
            type: object
            properties:
              name: { type: string }
              tags:
                type: array
                items: { type: string }
              address:
                type: object
                properties:
                  city: { type: string }
                additionalProperties: false
            additionalProperties: false
        """))
        assert tree == ObjectNode(properties=[
            SchemaProperty("name", False, ValueNode(type="string")),
            SchemaProperty("tags", False, ArrayNode(child=ValueNode(type="string"))),
            SchemaProperty("address", False, ObjectNode(properties=[
                SchemaProperty("city", False, ValueNode(type="string")),
            ])),
        ])

    def test_array_of_arrays(self) -> None:
        """array of arrays → ArrayNode(child=ArrayNode(child=ValueNode))."""
        tree = build_schema_tree(yaml.safe_load("""
            type: array
            items:
              type: array
              items: { type: string }
        """))
        assert tree == ArrayNode(child=ArrayNode(child=ValueNode(type="string")))


# ── B→C: collect_entities ────────────────────────────────────────────
#
# Spec: "SchemaTree → データカタログの変換ルール" (schema-inspector.md)


class TestCollectEntities:
    """collect_entities: SchemaTree → flat Entity list."""

    def test_top_level_object(self) -> None:
        """Top-level ObjectNode (singleton) → entity with item_type.id == name (no .item)."""
        tree = ObjectNode(properties=[
            SchemaProperty("name", True,  ValueNode(type="string")),
            SchemaProperty("age",  False, ValueNode(type="integer")),
        ])
        entities: list[dc.Entity] = []
        collect_entities("person", tree, entities)
        assert entities == [dc.Entity("person", item_type=dc.ObjectType("person", attributes=[
            dc.Attribute("name", "string",  True),
            dc.Attribute("age",  "integer", False),
        ]))]

    def test_top_level_array_of_objects(self) -> None:
        """Top-level ArrayNode → ObjectNode → entity with item_type.id == name + .item."""
        tree = ArrayNode(child=ObjectNode(properties=[
            SchemaProperty("x", True, ValueNode(type="number")),
        ]))
        entities: list[dc.Entity] = []
        collect_entities("points", tree, entities)
        assert entities == [dc.Entity("points", item_type=dc.ObjectType("points.item", attributes=[
            dc.Attribute("x", "number", True),
        ]))]

    def test_nested_object_prefix_flattened(self) -> None:
        """ObjectNode inside properties → prefix.name flat attributes."""
        tree = ObjectNode(properties=[
            SchemaProperty("address", True, ObjectNode(properties=[
                SchemaProperty("city",    True,  ValueNode(type="string")),
                SchemaProperty("zipcode", False, ValueNode(type="string")),
            ])),
        ])
        entities: list[dc.Entity] = []
        collect_entities("person", tree, entities)
        assert entities == [dc.Entity("person", item_type=dc.ObjectType("person", attributes=[
            dc.Attribute("address",         "object", True),
            dc.Attribute("address.city",    "string", True),
            dc.Attribute("address.zipcode", "string", False),
        ]))]

    def test_array_object_creates_child_entity(self) -> None:
        """ArrayNode → ObjectNode child → object[] attribute + linked child entity (with .item)."""
        tree = ObjectNode(properties=[
            SchemaProperty("items", False, ArrayNode(child=ObjectNode(properties=[
                SchemaProperty("name", True, ValueNode(type="string")),
            ]))),
        ])
        entities: list[dc.Entity] = []
        collect_entities("order", tree, entities)
        assert entities == [
            dc.Entity("order", item_type=dc.ObjectType("order", attributes=[
                dc.Attribute("items", "object[]", False,
                             entity="order.items",
                             item_type="order.items.item"),
            ])),
            dc.Entity(
                "order.items",
                item_type=dc.ObjectType("order.items.item", attributes=[
                    dc.Attribute("name", "string", True),
                ]),
                parent_entity="order",
            ),
        ]

    def test_array_value_type_bracket(self) -> None:
        """ArrayNode → ValueNode → type[] attribute."""
        tree = ObjectNode(properties=[
            SchemaProperty("tags", False, ArrayNode(child=ValueNode(type="string"))),
        ])
        entities: list[dc.Entity] = []
        collect_entities("article", tree, entities)
        assert entities == [dc.Entity("article", item_type=dc.ObjectType("article", attributes=[
            dc.Attribute("tags", "string[]", False),
        ]))]

    def test_nested_array_type_brackets(self) -> None:
        """ArrayNode → ArrayNode → type[][] attribute."""
        tree = ObjectNode(properties=[
            SchemaProperty("matrix", False, ArrayNode(child=ArrayNode(child=ValueNode(type="number")))),
        ])
        entities: list[dc.Entity] = []
        collect_entities("sheet", tree, entities)
        assert entities == [dc.Entity("sheet", item_type=dc.ObjectType("sheet", attributes=[
            dc.Attribute("matrix", "number[][]", False),
        ]))]

    def test_nested_array_of_objects_creates_child_entity(self) -> None:
        """ArrayNode → ArrayNode → ObjectNode → object[][] attribute + child entity (with .item)."""
        tree = ObjectNode(properties=[
            SchemaProperty("grid", False, ArrayNode(child=ArrayNode(child=ObjectNode(properties=[
                SchemaProperty("v", True, ValueNode(type="number")),
            ])))),
        ])
        entities: list[dc.Entity] = []
        collect_entities("board", tree, entities)
        assert entities == [
            dc.Entity("board", item_type=dc.ObjectType("board", attributes=[
                dc.Attribute("grid", "object[][]", False,
                             entity="board.grid",
                             item_type="board.grid.item"),
            ])),
            dc.Entity(
                "board.grid",
                item_type=dc.ObjectType("board.grid.item", attributes=[
                    dc.Attribute("v", "number", True),
                ]),
                parent_entity="board",
            ),
        ]

    def test_entity_metadata_from_array_node(self) -> None:
        """ArrayNode.metadata → ObjectType.metadata (not ObjectNode's)."""
        tree = ArrayNode(
            child=ObjectNode(properties=[
                SchemaProperty("x", True, ValueNode(type="string")),
            ]),
            metadata={"title": "My Collection"},
        )
        entities: list[dc.Entity] = []
        collect_entities("things", tree, entities)
        assert entities[0].item_type.metadata == {"title": "My Collection"}

    def test_attribute_metadata_and_validation(self) -> None:
        """ValueNode metadata/validation → Attribute metadata/validation."""
        tree = ObjectNode(properties=[
            SchemaProperty("score", True, ValueNode(
                type="integer",
                metadata={"description": "Player score"},
                validation={"minimum": 0, "maximum": 100},
            )),
        ])
        entities: list[dc.Entity] = []
        collect_entities("game", tree, entities)
        assert entities[0].item_type.attributes[0] == dc.Attribute(
            "score", "integer", True,
            metadata={"description": "Player score"},
            validation={"minimum": 0, "maximum": 100},
        )

    def test_required_transferred(self) -> None:
        """SchemaProperty.required → Attribute.required."""
        tree = ObjectNode(properties=[
            SchemaProperty("a", True,  ValueNode(type="string")),
            SchemaProperty("b", False, ValueNode(type="string")),
        ])
        entities: list[dc.Entity] = []
        collect_entities("t", tree, entities)
        assert [(a.id, a.required) for a in entities[0].item_type.attributes] == [
            ("a", True), ("b", False),
        ]

# fmt: on
