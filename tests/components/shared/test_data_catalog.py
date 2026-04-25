"""Tests for data_catalog — Entity / ObjectType / Attribute round-trip."""

from dataclasses import asdict

from another_mood.components.shared.data_catalog import (
    Attribute,
    Entity,
    ObjectType,
)


class TestRoundTrip:
    def test_minimal_entity(self) -> None:
        entity = Entity(
            id="users",
            item_type=ObjectType(
                id="users.item",
                attributes=[Attribute(id="name", type="string", required=True)],
            ),
        )
        assert Entity.from_dict(asdict(entity)) == entity

    def test_full_tree(self) -> None:
        entity = Entity(
            id="orders",
            item_type=ObjectType(
                id="orders.item",
                attributes=[
                    Attribute(
                        id="total",
                        type="number",
                        required=True,
                        validation={"minimum": 0},
                    ),
                    Attribute(
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
        assert Entity.from_dict(asdict(entity)) == entity
