"""Tests for catalog — persisted-record round-trip and tree build/flatten."""

import dataclasses

import pytest
from ruamel.yaml import YAML

from another_mood.components.shared import data_catalog as dc


def _catalog(yaml_text: str) -> list[dc.Entity]:
    """Parse a YAML list of entity dicts into a flat Entity catalog."""
    loaded: list[dict[str, object]] = YAML(typ="safe").load(yaml_text)  # type: ignore[no-untyped-call]
    return [dc.Entity.from_dict(e) for e in loaded]


def _edge(name: str, type_: str = "string") -> dc.Edge:
    return dc.Edge(name=name, type=type_, required=True)


def _edge_names(node: dc.Node) -> set[str]:
    return {edge.name for edge, _ in node.children}


class TestDictRoundTrip:
    def test_minimal_entity(self) -> None:
        entity = dc.Entity(
            id="users",
            item_type=dc.ObjectType(
                id="users.item",
                origin_item_type="users.item",
                attributes=[dc.Attribute(id="name", type="string", required=True)],
            ),
        )
        assert dc.Entity.from_dict(entity.to_dict()) == entity

    def test_full_tree(self) -> None:
        entity = dc.Entity(
            id="orders",
            item_type=dc.ObjectType(
                id="orders.item",
                origin_item_type="orders.item",
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
                        child_entity="orders.items",
                        child_item_type="orders.items.item",
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
                origin_item_type="tasks_by_phase.item",
                attributes=[dc.Attribute(id="phase", type="integer", required=True)],
            ),
            view=True,
        )
        assert dc.Entity.from_dict(entity.to_dict()) == entity

    def test_attribute_with_x_ref(self) -> None:
        """``XRef`` survives the to_dict/from_dict round-trip on Attribute."""
        entity = dc.Entity(
            id="albums",
            item_type=dc.ObjectType(
                id="albums.item",
                origin_item_type="albums.item",
                attributes=[
                    dc.Attribute(
                        id="artist_id",
                        type="string",
                        required=True,
                        x_ref=dc.XRef(entity="artists", attribute="id"),
                    ),
                    dc.Attribute(
                        id="curator",
                        type="string",
                        required=False,
                        x_ref=dc.XRef(entity="users", attribute="name"),
                    ),
                ],
            ),
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
                        child_entity: categories.tasks
                        child_item_type: categories.item.tasks.item
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
                  metadata: { title: Entity collection }
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
                        child_entity: entities.fields
                        child_item_type: entities.item.fields.item
                    metadata: { title: Entity }
                - id: entities.fields
                  metadata: { title: Fields list }
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
                      - { id: address, type: object, required: false }
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
                      - { id: hobby, type: object, required: false }
                      - id: hobby.pets
                        type: object[]
                        required: false
                        child_entity: members.hobby.pets
                        child_item_type: members.item.hobby.pets.item
                - id: members.hobby.pets
                  item_type:
                    id: members.item.hobby.pets.item
                    attributes:
                      - { id: id, type: string, required: true }
                  parent_entity: members
                """,
                id="dotted_attribute_pointing_to_entity",
            ),
            pytest.param(
                "roadmap",
                # No ``object`` attribute ahead of it, so the dotted id
                # is one edge name rather than a singleton to reclaim.
                """
                - id: roadmap
                  item_type:
                    id: roadmap.item
                    attributes:
                      - { id: task.phase, type: integer, required: true }
                      - id: tasks
                        type: object[]
                        required: true
                        child_entity: roadmap.tasks
                        child_item_type: roadmap.item.tasks.item
                - id: roadmap.tasks
                  item_type:
                    id: roadmap.item.tasks.item
                    attributes:
                      - { id: id, type: string, required: true }
                  parent_entity: roadmap
                """,
                id="dotted_alias_without_wrapper",
            ),
        ],
    )
    def test_build_then_flatten_is_identity(
        self, root_name: str, yaml_text: str
    ) -> None:
        flat = _catalog(yaml_text)
        # ``child_entry``, not ``child``: a root entity's collection-layer
        # metadata rides on the virtual root's edge, which is outside the
        # node ``flatten_tree`` walks.
        edge, node = dc.build_tree(flat).child_entry(root_name)
        assert dc.flatten_tree(node, root_name, metadata=edge.metadata) == flat


class TestCatalogDriftSuppression:
    """Assert each catalog dataclass and its ``catalog`` Node stay in sync.

    Failing here means a field was added/removed from ``XRef``,
    ``Attribute``, ``ObjectType`` or ``Entity`` without a matching update
    to that class's own ``catalog`` attribute — fix the catalog Node
    (and any consumer) before silencing the test.

    Coverage beyond field-set drift (edge types, entity-link wiring, the
    composition with ``flatten_tree``) is intentionally not tested here:
    those properties are visible directly in the implementation and are
    redundantly exercised by the broader ``build_tree`` / ``flatten_tree``
    identity tests above.
    """

    def test_attribute_edges_match_dataclass_fields(self) -> None:
        assert _edge_names(dc.Attribute.catalog) == {
            f.name for f in dataclasses.fields(dc.Attribute)
        }

    def test_xref_edges_match_dataclass_fields(self) -> None:
        assert _edge_names(dc.XRef.catalog) == {
            f.name for f in dataclasses.fields(dc.XRef)
        }

    def test_entity_edges_match_dataclass_fields(self) -> None:
        assert _edge_names(dc.Entity.catalog) == {
            f.name for f in dataclasses.fields(dc.Entity)
        }

    def test_object_type_edges_match_dataclass_fields(self) -> None:
        assert _edge_names(dc.ObjectType.catalog) == {
            f.name for f in dataclasses.fields(dc.ObjectType)
        }


class TestRenameOnFlatten:
    def test_flatten_tree_renames_root_and_propagates(self) -> None:
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
                    child_entity: categories.tasks
                    child_item_type: categories.item.tasks.item
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
            # A rename changes the id namespace but not provenance: the
            # renamed types keep the origin stamped at build time
            # (``categories.*``), not their new self ids.
            """
            - id: tasks_by_phase
              item_type:
                id: tasks_by_phase.item
                origin_item_type: categories.item
                attributes:
                  - { id: id, type: string, required: true }
                  - id: tasks
                    type: object[]
                    required: true
                    child_entity: tasks_by_phase.tasks
                    child_item_type: tasks_by_phase.item.tasks.item
            - id: tasks_by_phase.tasks
              item_type:
                id: tasks_by_phase.item.tasks.item
                origin_item_type: categories.item.tasks.item
                attributes:
                  - { id: id, type: string, required: true }
                  - { id: phase, type: integer, required: true }
              parent_entity: tasks_by_phase
            """
        )
        root = dc.build_tree(flat)
        assert dc.flatten_tree(root.child("categories"), "tasks_by_phase") == expected


class TestIsEntity:
    """``is_entity`` reads the link, not the node."""

    def test_object_collection_opens_an_entity(self) -> None:
        child = dc.Node(children=[(_edge("id"), dc.Node())])
        assert dc.is_entity(_edge("tasks", "object[]"), child)

    def test_singleton_object_does_not(self) -> None:
        """A singleton has children too, but is inlined into its holder."""
        child = dc.Node(children=[(_edge("city"), dc.Node())])
        assert not dc.is_entity(_edge("address", "object"), child)

    def test_scalar_collection_does_not(self) -> None:
        assert not dc.is_entity(_edge("tags", "string[]"), dc.Node())


class TestDescend:
    """``descend`` walks a dotted path; ``child`` reads one edge name."""

    #: ``members`` holds a singleton ``hobby``, itself holding a scalar
    #: ``level`` and a collection ``pets``.
    TREE = dc.Node(
        children=[
            (_edge("id"), dc.Node()),
            (
                _edge("hobby", "object"),
                dc.Node(
                    children=[
                        (_edge("level", "integer"), dc.Node()),
                        (
                            _edge("pets", "object[]"),
                            dc.Node(children=[(_edge("name"), dc.Node())]),
                        ),
                    ]
                ),
            ),
        ]
    )

    def test_traverses_a_singleton(self) -> None:
        edge, _ = self.TREE.descend("hobby.level")
        assert edge.name == "level"

    def test_ends_on_a_collection(self) -> None:
        edge, node = self.TREE.descend("hobby.pets")
        assert edge.type == "object[]"
        assert node.has_child("name")

    def test_does_not_cross_a_collection(self) -> None:
        """The asymmetry rule: reaching a field must mean reaching it on
        the row at hand."""
        with pytest.raises(dc.UnknownChildError):
            self.TREE.descend("hobby.pets.name")

    def test_unknown_path_carries_the_whole_path(self) -> None:
        with pytest.raises(dc.UnknownChildError) as excinfo:
            self.TREE.descend("hobby.nope")
        assert excinfo.value.name == "hobby.nope"

    def test_prefers_a_literal_dotted_edge_over_descent(self) -> None:
        """Longest-first: a view alias can still write a literal dotted key."""
        node = dc.Node(
            children=[
                (_edge("a", "object"), dc.Node(children=[(_edge("b"), dc.Node())])),
                (_edge("a.b", "integer"), dc.Node()),
            ]
        )
        edge, _ = node.descend("a.b")
        assert edge.type == "integer"

    def test_child_does_not_walk_a_path(self) -> None:
        """A dot in a name belongs to the name — top-level entity ids carry
        dots (``__definition.entities``).  Same string, different accessor:
        ``descend`` resolves ``hobby.level``, ``child`` does not."""
        assert not self.TREE.has_child("hobby.level")
        with pytest.raises(dc.UnknownChildError):
            self.TREE.child("hobby.level")
