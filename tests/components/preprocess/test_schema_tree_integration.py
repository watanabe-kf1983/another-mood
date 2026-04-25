"""Integration tests for SchemaTree — schema YAML → catalog YAML."""

from io import StringIO

import pytest
import yaml

from another_mood.components.preprocess.schema_inspector import extract_data_catalog
from another_mood.components.shared import yaml_dumper

_CASES = [
    pytest.param(
        """
        type: object
        properties:
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
            builtin: false
            item_type:
              id: recipes.item
              attributes:
                - { id: id, type: string, required: true }
                - { id: title, type: string, required: true }
                - { id: servings, type: integer, required: false }
        """,
        id="additionalProperties — entity with implicit id",
    ),
    pytest.param(
        """
        type: object
        properties:
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
            builtin: false
            item_type:
              id: kitchen
              attributes:
                - { id: name, type: string, required: true }
                - { id: capacity, type: integer, required: false }
        """,
        id="properties — flat fields (singleton, no .item)",
    ),
    pytest.param(
        """
        type: object
        properties:
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
            builtin: false
            item_type:
              id: steps.item
              attributes:
                - { id: order, type: integer, required: true }
                - { id: instruction, type: string, required: true }
        """,
        id="array of objects — entity without id",
    ),
    pytest.param(
        """
        type: object
        properties:
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
            builtin: false
            item_type:
              id: recipe
              attributes:
                - { id: tags, type: "string[]", required: false }
        """,
        id="array of scalars — type[]",
    ),
    pytest.param(
        """
        type: object
        properties:
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
            builtin: false
            item_type:
              id: recipes.item
              attributes:
                - { id: id, type: string, required: true }
                - { id: title, type: string, required: true }
                - id: ingredients
                  type: "object[]"
                  required: true
                  entity: recipes.ingredients
                  item_type: recipes.item.ingredients.item
          - id: recipes.ingredients
            builtin: false
            parent_entity: recipes
            item_type:
              id: recipes.item.ingredients.item
              attributes:
                - { id: id, type: string, required: true }
                - { id: name, type: string, required: true }
                - { id: amount, type: string, required: true }
        """,
        id="nested additionalProperties — parent.child entity",
    ),
    pytest.param(
        """
        type: object
        properties:
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
            builtin: false
            item_type:
              id: recipe
              attributes:
                - { id: nutrition, type: object, required: true }
                - { id: nutrition.calories, type: number, required: true }
                - { id: nutrition.protein, type: number, required: false }
        """,
        id="nested properties — prefix-separated fields",
    ),
    pytest.param(
        """
        type: object
        properties:
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
            builtin: false
            item_type:
              id: recipe
              attributes:
                - id: steps
                  type: "object[]"
                  required: false
                  entity: recipe.steps
                  item_type: recipe.steps.item
          - id: recipe.steps
            builtin: false
            parent_entity: recipe
            item_type:
              id: recipe.steps.item
              attributes:
                - { id: instruction, type: string, required: true }
                - { id: duration_min, type: integer, required: false }
        """,
        id="array of objects inside properties — new entity without id",
    ),
    pytest.param(
        """
        type: object
        properties:
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
            builtin: false
            item_type:
              id: recipes.item
              metadata:
                title: Recipe collection
                description: All recipes in the cookbook
              attributes:
                - { id: id, type: string, required: true }
                - { id: title, type: string, required: false }
        """,
        id="entity metadata — title and description",
    ),
    pytest.param(
        """
        type: object
        properties:
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
            builtin: false
            item_type:
              id: recipes.item
              attributes:
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
]


class TestSchemaToDataCatalog:
    """schema YAML → catalog YAML (end-to-end via extract_data_catalog)."""

    @pytest.mark.parametrize(("src", "expected_src"), _CASES)
    def test_end_to_end(self, src: str, expected_src: str) -> None:
        schema = yaml.safe_load(src)
        expected = yaml.safe_load(expected_src)
        buf = StringIO()
        yaml_dumper.dump(extract_data_catalog(schema), buf)
        assert yaml.safe_load(buf.getvalue()) == expected
