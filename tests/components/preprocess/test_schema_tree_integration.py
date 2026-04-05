"""Integration tests for SchemaTree — schema YAML → catalog YAML (A→C)."""

import pytest
import yaml

from reqs_builder.components.preprocess.schema_inspector import extract_data_catalog

# fmt: off

_CASES = [
    pytest.param(
        """
        schemas:
          recipes:
            type: object
            additionalProperties:
              type: object
              properties:
                title: { type: string }
                servings: { type: integer }
              additionalProperties: false
              required: [title]
        """,
        """
        entities:
          - id: recipes
            fields:
              - { id: id, type: string, required: true }
              - { id: title, type: string, required: true }
              - { id: servings, type: integer, required: false }
        """,
        id="additionalProperties — entity with implicit id",
    ),
    pytest.param(
        """
        schemas:
          kitchen:
            type: object
            properties:
              name: { type: string }
              capacity: { type: integer }
            additionalProperties: false
            required: [name]
        """,
        """
        entities:
          - id: kitchen
            fields:
              - { id: name, type: string, required: true }
              - { id: capacity, type: integer, required: false }
        """,
        id="properties — flat fields",
    ),
    pytest.param(
        """
        schemas:
          steps:
            type: array
            items:
              type: object
              properties:
                order: { type: integer }
                instruction: { type: string }
              additionalProperties: false
              required: [order, instruction]
        """,
        """
        entities:
          - id: steps
            fields:
              - { id: order, type: integer, required: true }
              - { id: instruction, type: string, required: true }
        """,
        id="array of objects — entity without id",
    ),
    pytest.param(
        """
        schemas:
          recipe:
            type: object
            properties:
              tags:
                type: array
                items: { type: string }
            additionalProperties: false
        """,
        """
        entities:
          - id: recipe
            fields:
              - { id: tags, type: "string[]", required: false }
        """,
        id="array of scalars — type[]",
    ),
    pytest.param(
        """
        schemas:
          recipes:
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
        """
        entities:
          - id: recipes
            fields:
              - { id: id, type: string, required: true }
              - { id: title, type: string, required: true }
              - { id: ingredients, type: "object[]", required: true }
          - id: recipes.ingredients
            fields:
              - { id: id, type: string, required: true }
              - { id: name, type: string, required: true }
              - { id: amount, type: string, required: true }
        """,
        id="nested additionalProperties — parent.child entity",
    ),
    pytest.param(
        """
        schemas:
          recipe:
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
        """
        entities:
          - id: recipe
            fields:
              - { id: nutrition, type: object, required: true }
              - { id: nutrition.calories, type: number, required: true }
              - { id: nutrition.protein, type: number, required: false }
        """,
        id="nested properties — prefix-separated fields",
    ),
    pytest.param(
        """
        schemas:
          recipe:
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
        """
        entities:
          - id: recipe
            fields:
              - { id: steps, type: "object[]", required: false }
          - id: recipe.steps
            fields:
              - { id: instruction, type: string, required: true }
              - { id: duration_min, type: integer, required: false }
        """,
        id="array of objects inside properties — new entity without id",
    ),
    pytest.param(
        """
        schemas:
          recipes:
            type: object
            title: Recipe collection
            description: All recipes in the cookbook
            additionalProperties:
              type: object
              properties:
                title: { type: string }
              additionalProperties: false
        """,
        """
        entities:
          - id: recipes
            metadata:
              title: Recipe collection
              description: All recipes in the cookbook
            fields:
              - { id: id, type: string, required: true }
              - { id: title, type: string, required: false }
        """,
        id="entity metadata — title and description",
    ),
    pytest.param(
        """
        schemas:
          recipes:
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
        """
        entities:
          - id: recipes
            fields:
              - { id: id, type: string, required: true }
              - id: title
                type: string
                required: true
                metadata:
                  title: Recipe title
                  description: Short name of the dish
                  default: Untitled
                  examples: [Curry, Pasta]
                  deprecated: false
                  format: kebab-case
              - id: servings
                type: integer
                required: false
                validation:
                  minimum: 1
                  maximum: 100
                  exclusiveMinimum: 0
              - id: difficulty
                type: string
                required: false
                validation:
                  enum: [easy, medium, hard]
        """,
        id="field metadata and validation keywords",
    ),
    pytest.param(
        """
        schemas:
          recipes:
            type: object
            additionalProperties:
              type: object
              properties:
                title: { type: string }
              additionalProperties: false
        references:
          - from: recipes.ingredients.name
            to: ingredients
          - from: recipes.category
            to: categories
        """,
        """
        entities:
          - id: recipes
            fields:
              - { id: id, type: string, required: true }
              - { id: title, type: string, required: false }
        references:
          - from: recipes.ingredients.name
            to: ingredients
          - from: recipes.category
            to: categories
        """,
        id="references passthrough",
    ),
]

# fmt: on


class TestSchemaToDataCatalog:
    """A → C: schema YAML → catalog YAML (end-to-end via extract_data_catalog)."""

    @pytest.mark.parametrize(("src", "expected_src"), _CASES)
    def test_end_to_end(self, src: str, expected_src: str) -> None:
        schema = yaml.safe_load(src)
        expected = yaml.safe_load(expected_src)
        assert extract_data_catalog(schema) == expected
