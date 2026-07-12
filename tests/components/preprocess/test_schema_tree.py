"""Tests for SchemaTree — unit tests derived from schema-inspector.md spec rules."""

import yaml

from another_mood.components.shared import data_catalog as dc
from another_mood.components.preprocess.schema_tree import (
    ArrayNode,
    ObjectNode,
    SchemaProperty,
    ValueNode,
    build_schema_tree,
    to_catalog_node,
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

    def test_metadata_preserves_schema_key_order(self) -> None:
        """metadata keys keep the schema's authoring order, not the keyword
        set's hash order — otherwise the emitted order varies per process
        (PYTHONHASHSEED) and builds are non-deterministic."""
        tree = build_schema_tree(yaml.safe_load("""
            type: object
            description: D
            title: T
            properties:
              x: { type: string }
        """))
        assert isinstance(tree, ObjectNode)
        assert tree.metadata is not None
        assert list(tree.metadata.keys()) == ["description", "title"]

    def test_validation_preserves_schema_key_order(self) -> None:
        """validation keys keep the schema's authoring order (see
        ``test_metadata_preserves_schema_key_order``)."""
        tree = build_schema_tree(yaml.safe_load("""
            type: string
            maxLength: 9
            minLength: 1
        """))
        assert isinstance(tree, ValueNode)
        assert tree.validation is not None
        assert list(tree.validation.keys()) == ["maxLength", "minLength"]

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

    def test_x_ref_entity_only(self) -> None:
        """x-ref is stashed as the raw mapping on SchemaProperty.x_ref."""
        tree = build_schema_tree(yaml.safe_load("""
            type: object
            properties:
              artist_id:
                type: string
                x-ref:
                  entity: artists
            additionalProperties: false
        """))
        assert tree == ObjectNode(properties=[
            SchemaProperty(
                "artist_id", False, ValueNode(type="string"),
                x_ref={"entity": "artists"},
            ),
        ])

    def test_x_ref_with_attribute(self) -> None:
        """Both entity and attribute survive in the raw mapping."""
        tree = build_schema_tree(yaml.safe_load("""
            type: object
            properties:
              curator:
                type: string
                x-ref:
                  entity: users
                  attribute: name
            additionalProperties: false
        """))
        assert tree == ObjectNode(properties=[
            SchemaProperty(
                "curator", False, ValueNode(type="string"),
                x_ref={"entity": "users", "attribute": "name"},
            ),
        ])

    def test_no_x_ref(self) -> None:
        """Properties without x-ref produce SchemaProperty.x_ref=None."""
        tree = build_schema_tree(yaml.safe_load("""
            type: object
            properties:
              plain: { type: string }
            additionalProperties: false
        """))
        assert isinstance(tree, ObjectNode)
        assert tree.properties[0].x_ref is None


# ── B→C: to_catalog_node + dc.flatten_tree ──────────────────────
#
# Spec: "SchemaTree → データカタログの変換ルール" (schema-inspector.md)
#
# Each test wraps its inner ObjectNode in an ArrayNode at the top to
# match the spec's convention that every top-level entity is a
# collection (the user schema must be ``additionalProperties`` or
# ``array``-rooted; bare top-level ``properties`` is not supported).


class TestToCatalogNode:
    """to_catalog_node + dc.flatten_tree: SchemaTree → flat Entity list."""

    def test_top_level_array_of_objects(self) -> None:
        """Top-level ArrayNode → ObjectNode → entity with item_type.id == name + .item."""
        tree = ArrayNode(child=ObjectNode(properties=[
            SchemaProperty("x", True, ValueNode(type="number")),
        ]))
        assert dc.flatten_tree(to_catalog_node(tree),"points") == [
            dc.Entity("points", item_type=dc.ObjectType("points.item", origin_item_type="points.item", attributes=[
                dc.Attribute("x", "number", True),
            ])),
        ]

    def test_nested_object_prefix_flattened(self) -> None:
        """ObjectNode inside properties → prefix.name flat attributes."""
        tree = ArrayNode(child=ObjectNode(properties=[
            SchemaProperty("address", True, ObjectNode(properties=[
                SchemaProperty("city",    True,  ValueNode(type="string")),
                SchemaProperty("zipcode", False, ValueNode(type="string")),
            ])),
        ]))
        assert dc.flatten_tree(to_catalog_node(tree),"persons") == [
            dc.Entity("persons", item_type=dc.ObjectType("persons.item", origin_item_type="persons.item", attributes=[
                dc.Attribute("address",         "object", True),
                dc.Attribute("address.city",    "string", True),
                dc.Attribute("address.zipcode", "string", False),
            ])),
        ]

    def test_array_object_creates_child_entity(self) -> None:
        """ArrayNode → ObjectNode child → object[] attribute + linked child entity (with .item)."""
        tree = ArrayNode(child=ObjectNode(properties=[
            SchemaProperty("items", False, ArrayNode(child=ObjectNode(properties=[
                SchemaProperty("name", True, ValueNode(type="string")),
            ]))),
        ]))
        assert dc.flatten_tree(to_catalog_node(tree),"orders") == [
            dc.Entity("orders", item_type=dc.ObjectType("orders.item", origin_item_type="orders.item", attributes=[
                dc.Attribute("items", "object[]", False,
                             child_entity="orders.items",
                             child_item_type="orders.item.items.item"),
            ])),
            dc.Entity(
                "orders.items",
                item_type=dc.ObjectType("orders.item.items.item", origin_item_type="orders.item.items.item", attributes=[
                    dc.Attribute("name", "string", True),
                ]),
                parent_entity="orders",
            ),
        ]

    def test_array_value_type_bracket(self) -> None:
        """ArrayNode → ValueNode → type[] attribute."""
        tree = ArrayNode(child=ObjectNode(properties=[
            SchemaProperty("tags", False, ArrayNode(child=ValueNode(type="string"))),
        ]))
        assert dc.flatten_tree(to_catalog_node(tree),"articles") == [
            dc.Entity("articles", item_type=dc.ObjectType("articles.item", origin_item_type="articles.item", attributes=[
                dc.Attribute("tags", "string[]", False),
            ])),
        ]

    def test_nested_array_type_brackets(self) -> None:
        """ArrayNode → ArrayNode → type[][] attribute."""
        tree = ArrayNode(child=ObjectNode(properties=[
            SchemaProperty("matrix", False, ArrayNode(child=ArrayNode(child=ValueNode(type="number")))),
        ]))
        assert dc.flatten_tree(to_catalog_node(tree),"sheets") == [
            dc.Entity("sheets", item_type=dc.ObjectType("sheets.item", origin_item_type="sheets.item", attributes=[
                dc.Attribute("matrix", "number[][]", False),
            ])),
        ]

    def test_nested_array_of_objects_creates_child_entity(self) -> None:
        """ArrayNode → ArrayNode → ObjectNode → object[][] attribute + child entity (with .item)."""
        tree = ArrayNode(child=ObjectNode(properties=[
            SchemaProperty("grid", False, ArrayNode(child=ArrayNode(child=ObjectNode(properties=[
                SchemaProperty("v", True, ValueNode(type="number")),
            ])))),
        ]))
        assert dc.flatten_tree(to_catalog_node(tree),"boards") == [
            dc.Entity("boards", item_type=dc.ObjectType("boards.item", origin_item_type="boards.item", attributes=[
                dc.Attribute("grid", "object[][]", False,
                             child_entity="boards.grid",
                             child_item_type="boards.item.grid.item"),
            ])),
            dc.Entity(
                "boards.grid",
                item_type=dc.ObjectType("boards.item.grid.item", origin_item_type="boards.item.grid.item", attributes=[
                    dc.Attribute("v", "number", True),
                ]),
                parent_entity="boards",
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
        assert dc.flatten_tree(to_catalog_node(tree),"things")[0].item_type.metadata == {"title": "My Collection"}

    def test_attribute_metadata_and_validation(self) -> None:
        """ValueNode metadata/validation → Attribute metadata/validation."""
        tree = ArrayNode(child=ObjectNode(properties=[
            SchemaProperty("score", True, ValueNode(
                type="integer",
                metadata={"description": "Player score"},
                validation={"minimum": 0, "maximum": 100},
            )),
        ]))
        assert dc.flatten_tree(to_catalog_node(tree),"games")[0].item_type.attributes[0] == dc.Attribute(
            "score", "integer", True,
            metadata={"description": "Player score"},
            validation={"minimum": 0, "maximum": 100},
        )

    def test_required_transferred(self) -> None:
        """SchemaProperty.required → Attribute.required."""
        tree = ArrayNode(child=ObjectNode(properties=[
            SchemaProperty("a", True,  ValueNode(type="string")),
            SchemaProperty("b", False, ValueNode(type="string")),
        ]))
        assert [(a.id, a.required) for a in dc.flatten_tree(to_catalog_node(tree),"ts")[0].item_type.attributes] == [
            ("a", True), ("b", False),
        ]

    def test_singleton_with_collection_subproperty_creates_child_entity(self) -> None:
        """Singleton ObjectNode containing an object[] sub-property keeps the child entity link.

        Singleton-flatten emits the singleton itself as a type='object'
        scalar attribute and its sub-properties as dotted-name edges; for
        ArrayNode(ObjectNode) sub-properties the child entity must be
        registered so that ``from: <singleton>.<collection>`` walks.
        """
        tree = ArrayNode(child=ObjectNode(properties=[
            SchemaProperty("name", True, ValueNode(type="string")),
            SchemaProperty("hobby", True, ObjectNode(properties=[
                SchemaProperty("pets", False, ArrayNode(child=ObjectNode(properties=[
                    SchemaProperty("name", True, ValueNode(type="string")),
                    SchemaProperty("kind", False, ValueNode(type="string")),
                ]))),
            ])),
        ]))
        assert dc.flatten_tree(to_catalog_node(tree), "members") == [
            dc.Entity("members", item_type=dc.ObjectType("members.item", origin_item_type="members.item", attributes=[
                dc.Attribute("name", "string", True),
                dc.Attribute("hobby", "object", True),
                dc.Attribute("hobby.pets", "object[]", False,
                             child_entity="members.hobby.pets",
                             child_item_type="members.item.hobby.pets.item"),
            ])),
            dc.Entity(
                "members.hobby.pets",
                item_type=dc.ObjectType("members.item.hobby.pets.item", origin_item_type="members.item.hobby.pets.item", attributes=[
                    dc.Attribute("name", "string", True),
                    dc.Attribute("kind", "string", False),
                ]),
                parent_entity="members",
            ),
        ]

    def test_singleton_with_scalar_subproperties_stays_flat(self) -> None:
        """Singleton with only scalar/scalar-array sub-properties remains flat (no child entity).

        Guards against over-eager promotion: scalar sub-properties of a
        singleton must stay as dotted-name attributes on the parent, never
        become entities.
        """
        tree = ArrayNode(child=ObjectNode(properties=[
            SchemaProperty("address", True, ObjectNode(properties=[
                SchemaProperty("city",     True,  ValueNode(type="string")),
                SchemaProperty("aliases",  False, ArrayNode(child=ValueNode(type="string"))),
            ])),
        ]))
        assert dc.flatten_tree(to_catalog_node(tree), "persons") == [
            dc.Entity("persons", item_type=dc.ObjectType("persons.item", origin_item_type="persons.item", attributes=[
                dc.Attribute("address",         "object",   True),
                dc.Attribute("address.city",    "string",   True),
                dc.Attribute("address.aliases", "string[]", False),
            ])),
        ]

    def test_x_ref_propagates_to_attribute(self) -> None:
        """SchemaProperty.x_ref (raw mapping) becomes dc.XRef at the catalog boundary;
        omitted 'attribute' is filled with the implicit-id default."""
        tree = ArrayNode(child=ObjectNode(properties=[
            SchemaProperty("artist_id", True, ValueNode(type="string"),
                           x_ref={"entity": "artists"}),
            SchemaProperty("curator", False, ValueNode(type="string"),
                           x_ref={"entity": "users", "attribute": "name"}),
        ]))
        assert dc.flatten_tree(to_catalog_node(tree), "albums") == [
            dc.Entity("albums", item_type=dc.ObjectType("albums.item", origin_item_type="albums.item", attributes=[
                dc.Attribute("artist_id", "string", True,
                             x_ref=dc.XRef(entity="artists", attribute="id")),
                dc.Attribute("curator", "string", False,
                             x_ref=dc.XRef(entity="users", attribute="name")),
            ])),
        ]

    def test_x_ref_on_dotted_singleton_subproperty(self) -> None:
        """x-ref on a sub-property of a singleton ObjectNode is carried by the dotted edge."""
        tree = ArrayNode(child=ObjectNode(properties=[
            SchemaProperty("address", True, ObjectNode(properties=[
                SchemaProperty("city_id", True, ValueNode(type="string"),
                               x_ref={"entity": "cities"}),
            ])),
        ]))
        assert dc.flatten_tree(to_catalog_node(tree), "users") == [
            dc.Entity("users", item_type=dc.ObjectType("users.item", origin_item_type="users.item", attributes=[
                dc.Attribute("address",         "object", True),
                dc.Attribute("address.city_id", "string", True,
                             x_ref=dc.XRef(entity="cities", attribute="id")),
            ])),
        ]

# fmt: on
