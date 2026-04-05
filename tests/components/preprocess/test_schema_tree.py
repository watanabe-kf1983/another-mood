"""Tests for SchemaTree — schema → tree → data catalog."""

import pytest
import yaml

from reqs_builder.components.preprocess.data_catalog import (
    CatalogEntity,
    CatalogField,
)
from reqs_builder.components.preprocess.schema_tree import (
    ArrayNode,
    ObjectNode,
    SchemaField,
    ValueNode,
    build_schema_tree,
    collect_entities,
    extract_entities,
)

# Each case: (schema_name, schema_yaml, expected_tree, expected_catalog)
_CASES = [
    pytest.param(
        "recipes",
        """
        type: object
        additionalProperties:
          type: object
          properties:
            title: { type: string }
            servings: { type: integer }
          additionalProperties: false
          required: [title]
        """,
        # B: SchemaTree
        ArrayNode(
            child=ObjectNode(
                fields=[
                    SchemaField("id", True, ValueNode(type="string")),
                    SchemaField("title", True, ValueNode(type="string")),
                    SchemaField("servings", False, ValueNode(type="integer")),
                ]
            )
        ),
        # C: DataCatalog
        [
            CatalogEntity(
                "recipes",
                fields=[
                    CatalogField("id", "string", True),
                    CatalogField("title", "string", True),
                    CatalogField("servings", "integer", False),
                ],
            )
        ],
        id="additionalProperties — entity with implicit id",
    ),
    pytest.param(
        "kitchen",
        """
        type: object
        properties:
          name: { type: string }
          capacity: { type: integer }
        additionalProperties: false
        required: [name]
        """,
        ObjectNode(
            fields=[
                SchemaField("name", True, ValueNode(type="string")),
                SchemaField("capacity", False, ValueNode(type="integer")),
            ]
        ),
        [
            CatalogEntity(
                "kitchen",
                fields=[
                    CatalogField("name", "string", True),
                    CatalogField("capacity", "integer", False),
                ],
            )
        ],
        id="properties — flat fields",
    ),
    pytest.param(
        "steps",
        """
        type: array
        items:
          type: object
          properties:
            order: { type: integer }
            instruction: { type: string }
          additionalProperties: false
          required: [order, instruction]
        """,
        ArrayNode(
            child=ObjectNode(
                fields=[
                    SchemaField("order", True, ValueNode(type="integer")),
                    SchemaField("instruction", True, ValueNode(type="string")),
                ]
            )
        ),
        [
            CatalogEntity(
                "steps",
                fields=[
                    CatalogField("order", "integer", True),
                    CatalogField("instruction", "string", True),
                ],
            )
        ],
        id="array of objects — entity without id",
    ),
    pytest.param(
        "recipe",
        """
        type: object
        properties:
          tags:
            type: array
            items: { type: string }
        additionalProperties: false
        """,
        ObjectNode(
            fields=[
                SchemaField("tags", False, ArrayNode(child=ValueNode(type="string"))),
            ]
        ),
        [
            CatalogEntity(
                "recipe",
                fields=[
                    CatalogField("tags", "string[]", False),
                ],
            )
        ],
        id="array of scalars — type[]",
    ),
    pytest.param(
        "recipes",
        """
        type: object
        additionalProperties:
          type: object
          properties:
            title: { type: string }
            ingredients:
              type: object
              additionalProperties:
                type: object
                properties:
                  name: { type: string }
                  amount: { type: string }
                additionalProperties: false
                required: [name, amount]
          additionalProperties: false
          required: [title, ingredients]
        """,
        ArrayNode(
            child=ObjectNode(
                fields=[
                    SchemaField("id", True, ValueNode(type="string")),
                    SchemaField("title", True, ValueNode(type="string")),
                    SchemaField(
                        "ingredients",
                        True,
                        ArrayNode(
                            child=ObjectNode(
                                fields=[
                                    SchemaField("id", True, ValueNode(type="string")),
                                    SchemaField("name", True, ValueNode(type="string")),
                                    SchemaField(
                                        "amount", True, ValueNode(type="string")
                                    ),
                                ]
                            )
                        ),
                    ),
                ]
            )
        ),
        [
            CatalogEntity(
                "recipes",
                fields=[
                    CatalogField("id", "string", True),
                    CatalogField("title", "string", True),
                    CatalogField("ingredients", "object[]", True),
                ],
            ),
            CatalogEntity(
                "recipes.ingredients",
                fields=[
                    CatalogField("id", "string", True),
                    CatalogField("name", "string", True),
                    CatalogField("amount", "string", True),
                ],
            ),
        ],
        id="nested additionalProperties — parent.child entity",
    ),
    pytest.param(
        "recipe",
        """
        type: object
        properties:
          nutrition:
            type: object
            properties:
              calories: { type: number }
              protein: { type: number }
            additionalProperties: false
            required: [calories]
        additionalProperties: false
        required: [nutrition]
        """,
        ObjectNode(
            fields=[
                SchemaField(
                    "nutrition",
                    True,
                    ObjectNode(
                        fields=[
                            SchemaField("calories", True, ValueNode(type="number")),
                            SchemaField("protein", False, ValueNode(type="number")),
                        ]
                    ),
                ),
            ]
        ),
        [
            CatalogEntity(
                "recipe",
                fields=[
                    CatalogField("nutrition", "object", True),
                    CatalogField("nutrition.calories", "number", True),
                    CatalogField("nutrition.protein", "number", False),
                ],
            )
        ],
        id="nested properties — prefix-separated fields",
    ),
    pytest.param(
        "recipe",
        """
        type: object
        properties:
          steps:
            type: array
            items:
              type: object
              properties:
                instruction: { type: string }
                duration_min: { type: integer }
              additionalProperties: false
              required: [instruction]
        additionalProperties: false
        """,
        ObjectNode(
            fields=[
                SchemaField(
                    "steps",
                    False,
                    ArrayNode(
                        child=ObjectNode(
                            fields=[
                                SchemaField(
                                    "instruction", True, ValueNode(type="string")
                                ),
                                SchemaField(
                                    "duration_min", False, ValueNode(type="integer")
                                ),
                            ]
                        )
                    ),
                ),
            ]
        ),
        [
            CatalogEntity(
                "recipe",
                fields=[
                    CatalogField("steps", "object[]", False),
                ],
            ),
            CatalogEntity(
                "recipe.steps",
                fields=[
                    CatalogField("instruction", "string", True),
                    CatalogField("duration_min", "integer", False),
                ],
            ),
        ],
        id="array of objects inside properties — new entity without id",
    ),
    pytest.param(
        "recipes",
        """
        type: object
        title: Recipe collection
        description: All recipes in the cookbook
        additionalProperties:
          type: object
          properties:
            title: { type: string }
          additionalProperties: false
        """,
        ArrayNode(
            child=ObjectNode(
                fields=[
                    SchemaField("id", True, ValueNode(type="string")),
                    SchemaField("title", False, ValueNode(type="string")),
                ]
            ),
            metadata={
                "title": "Recipe collection",
                "description": "All recipes in the cookbook",
            },
        ),
        [
            CatalogEntity(
                "recipes",
                fields=[
                    CatalogField("id", "string", True),
                    CatalogField("title", "string", False),
                ],
                metadata={
                    "title": "Recipe collection",
                    "description": "All recipes in the cookbook",
                },
            )
        ],
        id="entity metadata — title and description",
    ),
    pytest.param(
        "recipes",
        """
        type: object
        additionalProperties:
          type: object
          properties:
            title:
              type: string
              title: Recipe title
              description: Short name of the dish
              default: Untitled
              examples: [Curry, Pasta]
              deprecated: false
              format: kebab-case
            servings:
              type: integer
              minimum: 1
              maximum: 100
              exclusiveMinimum: 0
            difficulty:
              type: string
              enum: [easy, medium, hard]
          additionalProperties: false
          required: [title]
        """,
        ArrayNode(
            child=ObjectNode(
                fields=[
                    SchemaField("id", True, ValueNode(type="string")),
                    SchemaField(
                        "title",
                        True,
                        ValueNode(
                            type="string",
                            metadata={
                                "title": "Recipe title",
                                "description": "Short name of the dish",
                                "default": "Untitled",
                                "examples": ["Curry", "Pasta"],
                                "deprecated": False,
                                "format": "kebab-case",
                            },
                        ),
                    ),
                    SchemaField(
                        "servings",
                        False,
                        ValueNode(
                            type="integer",
                            validation={
                                "minimum": 1,
                                "maximum": 100,
                                "exclusiveMinimum": 0,
                            },
                        ),
                    ),
                    SchemaField(
                        "difficulty",
                        False,
                        ValueNode(
                            type="string",
                            validation={"enum": ["easy", "medium", "hard"]},
                        ),
                    ),
                ]
            )
        ),
        [
            CatalogEntity(
                "recipes",
                fields=[
                    CatalogField("id", "string", True),
                    CatalogField(
                        "title",
                        "string",
                        True,
                        metadata={
                            "title": "Recipe title",
                            "description": "Short name of the dish",
                            "default": "Untitled",
                            "examples": ["Curry", "Pasta"],
                            "deprecated": False,
                            "format": "kebab-case",
                        },
                    ),
                    CatalogField(
                        "servings",
                        "integer",
                        False,
                        validation={
                            "minimum": 1,
                            "maximum": 100,
                            "exclusiveMinimum": 0,
                        },
                    ),
                    CatalogField(
                        "difficulty",
                        "string",
                        False,
                        validation={
                            "enum": ["easy", "medium", "hard"],
                        },
                    ),
                ],
            )
        ],
        id="field metadata and validation keywords",
    ),
]


class TestBuildSchemaTree:
    """A → B: schema YAML → SchemaTree."""

    @pytest.mark.parametrize(("name", "src", "expected_tree", "_catalog"), _CASES)
    def test_build(
        self,
        name: str,
        src: str,
        expected_tree: ObjectNode | ArrayNode | ValueNode,
        _catalog: object,
    ) -> None:
        schema = yaml.safe_load(src)
        assert build_schema_tree(schema) == expected_tree


class TestExtractEntities:
    """B → C: SchemaTree → DataCatalog."""

    @pytest.mark.parametrize(("name", "_src", "_tree", "expected_catalog"), _CASES)
    def test_extract(
        self,
        name: str,
        _src: str,
        _tree: object,
        expected_catalog: list[CatalogEntity],
    ) -> None:
        schema = yaml.safe_load(_src)
        tree = build_schema_tree(schema)
        entities: list[CatalogEntity] = []
        collect_entities(name, tree, entities)
        assert entities == expected_catalog


class TestSchemaToDataCatalog:
    """A → C: schema YAML → DataCatalog (integration)."""

    @pytest.mark.parametrize(("name", "src", "_tree", "expected_catalog"), _CASES)
    def test_end_to_end(
        self,
        name: str,
        src: str,
        _tree: object,
        expected_catalog: list[CatalogEntity],
    ) -> None:
        schemas = yaml.safe_load(src)
        result = extract_entities({name: schemas})
        assert result == expected_catalog
