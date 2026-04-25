"""Tests for SchemaTree — unit tests derived from schema-inspector.md spec rules."""

import yaml

from another_mood.components.preprocess.data_catalog import (
    CatalogEntity,
    CatalogAttribute,
)
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
    """collect_entities: SchemaTree → flat CatalogEntity list."""

    def test_top_level_object(self) -> None:
        """Top-level ObjectNode → single entity."""
        tree = ObjectNode(properties=[
            SchemaProperty("name", True,  ValueNode(type="string")),
            SchemaProperty("age",  False, ValueNode(type="integer")),
        ])
        entities: list[CatalogEntity] = []
        collect_entities("person", tree, entities)
        assert entities == [CatalogEntity("person", attributes=[
            CatalogAttribute("name", "string",  True),
            CatalogAttribute("age",  "integer", False),
        ])]

    def test_top_level_array_of_objects(self) -> None:
        """Top-level ArrayNode → ObjectNode → entity."""
        tree = ArrayNode(child=ObjectNode(properties=[
            SchemaProperty("x", True, ValueNode(type="number")),
        ]))
        entities: list[CatalogEntity] = []
        collect_entities("points", tree, entities)
        assert entities == [CatalogEntity("points", attributes=[
            CatalogAttribute("x", "number", True),
        ])]

    def test_nested_object_prefix_flattened(self) -> None:
        """ObjectNode inside properties → prefix.name flat attributes."""
        tree = ObjectNode(properties=[
            SchemaProperty("address", True, ObjectNode(properties=[
                SchemaProperty("city",    True,  ValueNode(type="string")),
                SchemaProperty("zipcode", False, ValueNode(type="string")),
            ])),
        ])
        entities: list[CatalogEntity] = []
        collect_entities("person", tree, entities)
        assert entities == [CatalogEntity("person", attributes=[
            CatalogAttribute("address",         "object", True),
            CatalogAttribute("address.city",    "string", True),
            CatalogAttribute("address.zipcode", "string", False),
        ])]

    def test_array_object_creates_child_entity(self) -> None:
        """ArrayNode → ObjectNode inside properties → object[] attribute + linked child entity."""
        tree = ObjectNode(properties=[
            SchemaProperty("items", False, ArrayNode(child=ObjectNode(properties=[
                SchemaProperty("name", True, ValueNode(type="string")),
            ]))),
        ])
        entities: list[CatalogEntity] = []
        collect_entities("order", tree, entities)
        assert entities == [
            CatalogEntity("order", attributes=[
                CatalogAttribute("items", "object[]", False, child_entity="order.items"),
            ]),
            CatalogEntity(
                "order.items",
                attributes=[CatalogAttribute("name", "string", True)],
                parent_entity="order",
            ),
        ]

    def test_array_value_type_bracket(self) -> None:
        """ArrayNode → ValueNode → type[] attribute."""
        tree = ObjectNode(properties=[
            SchemaProperty("tags", False, ArrayNode(child=ValueNode(type="string"))),
        ])
        entities: list[CatalogEntity] = []
        collect_entities("article", tree, entities)
        assert entities == [CatalogEntity("article", attributes=[
            CatalogAttribute("tags", "string[]", False),
        ])]

    def test_nested_array_type_brackets(self) -> None:
        """ArrayNode → ArrayNode → type[][] attribute."""
        tree = ObjectNode(properties=[
            SchemaProperty("matrix", False, ArrayNode(child=ArrayNode(child=ValueNode(type="number")))),
        ])
        entities: list[CatalogEntity] = []
        collect_entities("sheet", tree, entities)
        assert entities == [CatalogEntity("sheet", attributes=[
            CatalogAttribute("matrix", "number[][]", False),
        ])]

    def test_nested_array_of_objects_creates_child_entity(self) -> None:
        """ArrayNode → ArrayNode → ObjectNode inside properties → object[][] attribute + child entity."""
        tree = ObjectNode(properties=[
            SchemaProperty("grid", False, ArrayNode(child=ArrayNode(child=ObjectNode(properties=[
                SchemaProperty("v", True, ValueNode(type="number")),
            ])))),
        ])
        entities: list[CatalogEntity] = []
        collect_entities("board", tree, entities)
        assert entities == [
            CatalogEntity("board", attributes=[
                CatalogAttribute("grid", "object[][]", False, child_entity="board.grid"),
            ]),
            CatalogEntity(
                "board.grid",
                attributes=[CatalogAttribute("v", "number", True)],
                parent_entity="board",
            ),
        ]

    def test_entity_metadata_from_array_node(self) -> None:
        """ArrayNode.metadata → CatalogEntity.metadata (not ObjectNode's)."""
        tree = ArrayNode(
            child=ObjectNode(properties=[
                SchemaProperty("x", True, ValueNode(type="string")),
            ]),
            metadata={"title": "My Collection"},
        )
        entities: list[CatalogEntity] = []
        collect_entities("things", tree, entities)
        assert entities[0].metadata == {"title": "My Collection"}

    def test_attribute_metadata_and_validation(self) -> None:
        """ValueNode metadata/validation → CatalogAttribute metadata/validation."""
        tree = ObjectNode(properties=[
            SchemaProperty("score", True, ValueNode(
                type="integer",
                metadata={"description": "Player score"},
                validation={"minimum": 0, "maximum": 100},
            )),
        ])
        entities: list[CatalogEntity] = []
        collect_entities("game", tree, entities)
        assert entities[0].attributes[0] == CatalogAttribute(
            "score", "integer", True,
            metadata={"description": "Player score"},
            validation={"minimum": 0, "maximum": 100},
        )

    def test_required_transferred(self) -> None:
        """SchemaProperty.required → CatalogAttribute.required."""
        tree = ObjectNode(properties=[
            SchemaProperty("a", True,  ValueNode(type="string")),
            SchemaProperty("b", False, ValueNode(type="string")),
        ])
        entities: list[CatalogEntity] = []
        collect_entities("t", tree, entities)
        assert [(a.id, a.required) for a in entities[0].attributes] == [
            ("a", True), ("b", False),
        ]

# fmt: on
