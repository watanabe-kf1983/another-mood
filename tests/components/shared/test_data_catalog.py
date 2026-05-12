"""Tests for catalog — persisted-record round-trip and tree build/flatten."""

import pytest
from ruamel.yaml import YAML

from another_mood.components.shared import data_catalog as dc


def _catalog(yaml_text: str) -> list[dc.Entity]:
    """Parse a YAML list of entity dicts into a flat Entity catalog."""
    loaded: list[dict[str, object]] = YAML(typ="safe").load(yaml_text)  # type: ignore[no-untyped-call]
    return [dc.Entity.from_dict(e) for e in loaded]


class TestDictRoundTrip:
    def test_minimal_entity(self) -> None:
        entity = dc.Entity(
            id="users",
            item_type=dc.ObjectType(
                id="users.item",
                attributes=[dc.Attribute(id="name", type="string", required=True)],
            ),
        )
        assert dc.Entity.from_dict(entity.to_dict()) == entity

    def test_full_tree(self) -> None:
        entity = dc.Entity(
            id="orders",
            item_type=dc.ObjectType(
                id="orders.item",
                attributes=[
                    dc.Attribute(
                        id="total",
                        type="number",
                        required=True,
                        validation={"minimum": 0},
                    ),
                    dc.Attribute(
                        id="items",
                        type="object[]",
                        required=False,
                        entity="orders.items",
                        item_type="orders.items.item",
                    ),
                ],
                metadata={"title": "Order"},
            ),
            parent_entity=None,
            builtin=True,
        )
        assert dc.Entity.from_dict(entity.to_dict()) == entity

    def test_view_flag(self) -> None:
        entity = dc.Entity(
            id="tasks_by_phase",
            item_type=dc.ObjectType(
                id="tasks_by_phase.item",
                attributes=[dc.Attribute(id="phase", type="integer", required=True)],
            ),
            view=True,
        )
        assert dc.Entity.from_dict(entity.to_dict()) == entity


class TestBuildAndFlatten:
    @pytest.mark.parametrize(
        "root_name,yaml_text",
        [
            pytest.param(
                "categories",
                """
                - id: categories
                  item_type:
                    id: categories.item
                    attributes:
                      - { id: id, type: string, required: true }
                      - { id: title, type: string, required: true }
                      - id: tasks
                        type: object[]
                        required: true
                        entity: categories.tasks
                        item_type: categories.item.tasks.item
                - id: categories.tasks
                  item_type:
                    id: categories.item.tasks.item
                    attributes:
                      - { id: id, type: string, required: true }
                      - { id: title, type: string, required: true }
                      - { id: phase, type: integer, required: true }
                  parent_entity: categories
                """,
                id="parent_with_child_entity",
            ),
            pytest.param(
                "entities",
                """
                - id: entities
                  item_type:
                    id: entities.item
                    attributes:
                      - id: id
                        type: string
                        required: true
                        metadata: { description: Entity identifier }
                      - id: fields
                        type: object[]
                        required: true
                        metadata: { title: Fields list }
                        entity: entities.fields
                        item_type: entities.item.fields.item
                    metadata: { title: Entity }
                - id: entities.fields
                  item_type:
                    id: entities.item.fields.item
                    attributes:
                      - { id: name, type: string, required: true }
                    metadata: { title: Field }
                  parent_entity: entities
                """,
                id="metadata_preserved",
            ),
            pytest.param(
                "users",
                """
                - id: users
                  item_type:
                    id: users.item
                    attributes:
                      - { id: id, type: string, required: true }
                      - { id: address.street, type: string, required: false }
                      - { id: address.city, type: string, required: false }
                """,
                id="singleton_dotted_attribute",
            ),
            pytest.param(
                "members",
                """
                - id: members
                  item_type:
                    id: members.item
                    attributes:
                      - id: hobby.pets
                        type: object[]
                        required: false
                        entity: members.hobby.pets
                        item_type: members.item.hobby.pets.item
                - id: members.hobby.pets
                  item_type:
                    id: members.item.hobby.pets.item
                    attributes:
                      - { id: id, type: string, required: true }
                  parent_entity: members
                """,
                id="dotted_attribute_pointing_to_entity",
            ),
        ],
    )
    def test_build_then_flatten_is_identity(
        self, root_name: str, yaml_text: str
    ) -> None:
        flat = _catalog(yaml_text)
        root = dc.Node.from_flat(flat)
        assert root.child(root_name).to_flat(root_name) == flat


_MEMBERS_DOTTED_EDGE_YAML = """
- id: members
  item_type:
    id: members.item
    attributes:
      - { id: id, type: string, required: true }
      - { id: hobby, type: object, required: false }
      - id: hobby.pets
        type: object[]
        required: false
        entity: members.hobby.pets
        item_type: members.item.hobby.pets.item
- id: members.hobby.pets
  item_type:
    id: members.item.hobby.pets.item
    attributes:
      - { id: id, type: string, required: true }
  parent_entity: members
"""


class TestWalkPath:
    def test_single_segment(self) -> None:
        root = dc.Node.from_flat(_catalog(_MEMBERS_DOTTED_EDGE_YAML))
        assert root.walk_path("members") is root.child("members")

    def test_longest_match_picks_dotted_edge(self) -> None:
        # ``hobby.pets`` is a single edge, even though there is also a
        # shorter ``hobby`` edge under ``members``.  walk_path consumes
        # the longest match.
        root = dc.Node.from_flat(_catalog(_MEMBERS_DOTTED_EDGE_YAML))
        target = root.child("members").child("hobby.pets")
        assert root.walk_path("members.hobby.pets") is target

    def test_raises_when_no_match(self) -> None:
        root = dc.Node.from_flat(_catalog(_MEMBERS_DOTTED_EDGE_YAML))
        with pytest.raises(KeyError):
            root.walk_path("missing")

    def test_raises_when_partial_match_only(self) -> None:
        # ``members.unknown`` shares the ``members`` prefix but no
        # second-step edge matches ``unknown`` — should still raise.
        root = dc.Node.from_flat(_catalog(_MEMBERS_DOTTED_EDGE_YAML))
        with pytest.raises(KeyError):
            root.walk_path("members.unknown")


class TestRenameOnFlatten:
    def test_to_flat_renames_root_and_propagates(self) -> None:
        flat = _catalog(
            """
            - id: categories
              item_type:
                id: categories.item
                attributes:
                  - { id: id, type: string, required: true }
                  - id: tasks
                    type: object[]
                    required: true
                    entity: categories.tasks
                    item_type: categories.item.tasks.item
            - id: categories.tasks
              item_type:
                id: categories.item.tasks.item
                attributes:
                  - { id: id, type: string, required: true }
                  - { id: phase, type: integer, required: true }
              parent_entity: categories
            """
        )
        expected = _catalog(
            """
            - id: tasks_by_phase
              item_type:
                id: tasks_by_phase.item
                attributes:
                  - { id: id, type: string, required: true }
                  - id: tasks
                    type: object[]
                    required: true
                    entity: tasks_by_phase.tasks
                    item_type: tasks_by_phase.item.tasks.item
            - id: tasks_by_phase.tasks
              item_type:
                id: tasks_by_phase.item.tasks.item
                attributes:
                  - { id: id, type: string, required: true }
                  - { id: phase, type: integer, required: true }
              parent_entity: tasks_by_phase
            """
        )
        root = dc.Node.from_flat(flat)
        assert root.child("categories").to_flat("tasks_by_phase") == expected
