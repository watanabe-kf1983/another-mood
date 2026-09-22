"""Tests for SchemaCatalog — JSON Schema → catalog tree → flat entities."""

from collections.abc import Sequence

import yaml

from another_mood.components.shared import data_catalog as dc
from another_mood.components.preprocess.schema_catalog import build_catalog_node

# fmt: off


def _node(src: str) -> dc.Node:
    return build_catalog_node(yaml.safe_load(src))


def _entities(src: str, root_name: str) -> Sequence[dc.Entity]:
    return dc.flatten_tree(build_catalog_node(yaml.safe_load(src)), root_name)


# ── Schema → catalog node tree ──────────────────────────────────────


class TestBuildCatalogNode:
    """build_catalog_node: JSON Schema → dc.Node / dc.Edge tree."""

    def test_record_properties(self) -> None:
        """object + properties → one edge per property."""
        assert _node("""
            type: object
            properties:
              name: { type: string }
              age:  { type: integer }
            additionalProperties: false
            required: [name]
        """) == dc.Node(children=[
            (dc.Edge("name", "string",  True),  dc.Node()),
            (dc.Edge("age",  "integer", False), dc.Node()),
        ])

    def test_map_of_records(self) -> None:
        """object + additionalProperties: {type: object} → records with an implicit id."""
        assert _node("""
            type: object
            additionalProperties:
              type: object
              properties:
                title: { type: string }
              additionalProperties: false
              required: [title]
        """) == dc.Node(children=[
            (dc.Edge("id",    "string", True), dc.Node()),
            (dc.Edge("title", "string", True), dc.Node()),
        ])

    def test_map_of_scalars(self) -> None:
        """object + additionalProperties: {type: T} (non-object) → id/value pairs."""
        assert _node("""
            type: object
            additionalProperties: { type: number }
        """) == dc.Node(children=[
            (dc.Edge("id",    "string", True), dc.Node()),
            (dc.Edge("value", "number", True), dc.Node()),
        ])

    def test_array_of_records(self) -> None:
        """array + items → the node of the record underneath."""
        assert _node("""
            type: array
            items:
              type: object
              properties:
                x: { type: integer }
              additionalProperties: false
        """) == dc.Node(children=[
            (dc.Edge("x", "integer", False), dc.Node()),
        ])

    def test_array_of_scalars(self) -> None:
        """array + items: scalar → a leaf node; the array layer shows on the edge."""
        assert _node("""
            type: array
            items: { type: boolean }
        """) == dc.Node()

    def test_scalar(self) -> None:
        """scalar type → a leaf node."""
        assert _node("type: number") == dc.Node()

    def test_metadata_on_record(self) -> None:
        """metadata keywords are extracted to node.metadata."""
        node = _node("""
            type: object
            title: My Object
            description: A test object
            properties:
              x: { type: string }
            additionalProperties: false
        """)
        assert node.metadata == {"title": "My Object", "description": "A test object"}

    def test_metadata_preserves_schema_key_order(self) -> None:
        """metadata keys keep the schema's authoring order, not the keyword
        set's hash order — otherwise the emitted order varies per process
        (PYTHONHASHSEED) and builds are non-deterministic."""
        node = _node("""
            type: object
            description: D
            title: T
            properties:
              x: { type: string }
        """)
        assert node.metadata is not None
        assert list(node.metadata.keys()) == ["description", "title"]

    def test_validation_preserves_schema_key_order(self) -> None:
        """validation keys keep the schema's authoring order (see
        ``test_metadata_preserves_schema_key_order``)."""
        edge, _ = _node("""
            type: object
            properties:
              code:
                type: string
                maxLength: 9
                minLength: 1
            additionalProperties: false
        """).children[0]
        assert edge.validation is not None
        assert list(edge.validation.keys()) == ["maxLength", "minLength"]

    def test_metadata_and_validation_on_edge(self) -> None:
        """A scalar property carries its metadata and validation on the edge."""
        assert _node("""
            type: object
            properties:
              label:
                type: string
                title: A label
                minLength: 1
                pattern: "^[A-Z]"
            additionalProperties: false
        """) == dc.Node(children=[
            (
                dc.Edge(
                    "label", "string", False,
                    metadata={"title": "A label"},
                    validation={"minLength": 1, "pattern": "^[A-Z]"},
                ),
                dc.Node(),
            ),
        ])

    def test_required_propagation(self) -> None:
        """Edge.required reflects the record's required list."""
        node = _node("""
            type: object
            properties:
              a: { type: string }
              b: { type: string }
              c: { type: string }
            additionalProperties: false
            required: [a, c]
        """)
        assert [(e.name, e.required) for e, _ in node.children] == [
            ("a", True), ("b", False), ("c", True),
        ]

    def test_record_containing_record(self) -> None:
        """Record-Record: a property holding a nested object."""
        assert _node("""
            type: object
            properties:
              address:
                type: object
                properties:
                  city: { type: string }
                additionalProperties: false
            additionalProperties: false
        """) == dc.Node(children=[
            (dc.Edge("address", "object", False), dc.Node(children=[
                (dc.Edge("city", "string", False), dc.Node()),
            ])),
        ])

    def test_record_containing_array(self) -> None:
        """Record-Array: an array property becomes a ``[]``-suffixed edge type."""
        assert _node("""
            type: object
            properties:
              scores:
                type: array
                items: { type: integer }
            additionalProperties: false
        """) == dc.Node(children=[
            (dc.Edge("scores", "integer[]", False), dc.Node()),
        ])

    def test_record_mixed_children(self) -> None:
        """Record-[Record, Array, Value]: properties with all three child shapes."""
        assert _node("""
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
        """) == dc.Node(children=[
            (dc.Edge("name", "string",   False), dc.Node()),
            (dc.Edge("tags", "string[]", False), dc.Node()),
            (dc.Edge("address", "object", False), dc.Node(children=[
                (dc.Edge("city", "string", False), dc.Node()),
            ])),
        ])

    def test_array_of_arrays(self) -> None:
        """One ``[]`` per array layer, innermost type first."""
        assert _node("""
            type: object
            properties:
              matrix:
                type: array
                items:
                  type: array
                  items: { type: string }
            additionalProperties: false
        """) == dc.Node(children=[
            (dc.Edge("matrix", "string[][]", False), dc.Node()),
        ])

    def test_x_ref_entity_only(self) -> None:
        """An x-ref without ``attribute`` resolves to the target's implicit id."""
        assert _node("""
            type: object
            properties:
              artist_id:
                type: string
                x-ref:
                  entity: artists
            additionalProperties: false
        """) == dc.Node(children=[
            (
                dc.Edge("artist_id", "string", False,
                        x_ref=dc.XRef(entity="artists", attribute="id")),
                dc.Node(),
            ),
        ])

    def test_x_ref_with_attribute(self) -> None:
        """A spelled-out ``attribute`` is carried through as written."""
        assert _node("""
            type: object
            properties:
              curator:
                type: string
                x-ref:
                  entity: users
                  attribute: name
            additionalProperties: false
        """) == dc.Node(children=[
            (
                dc.Edge("curator", "string", False,
                        x_ref=dc.XRef(entity="users", attribute="name")),
                dc.Node(),
            ),
        ])

    def test_no_x_ref(self) -> None:
        """Properties without x-ref produce Edge.x_ref=None."""
        edge, _ = _node("""
            type: object
            properties:
              plain: { type: string }
            additionalProperties: false
        """).children[0]
        assert edge.x_ref is None


# ── Catalog node tree → flat entities ───────────────────────────────
#
# Each schema here is a top-level collection, matching the convention
# that every top-level entity is one (the user schema must be
# ``additionalProperties`` or ``array``-rooted; a bare top-level
# ``properties`` is not supported).


class TestCatalogNodeToEntities:
    """build_catalog_node + dc.flatten_tree: schema → flat Entity list."""

    def test_top_level_array_of_objects(self) -> None:
        """A top-level collection → entity with item_type.id == name + .item."""
        assert _entities("""
            type: array
            items:
              type: object
              properties:
                x: { type: number }
              additionalProperties: false
              required: [x]
        """, "points") == [
            dc.Entity("points", item_type=dc.ObjectType("points.item", origin_item_type="points.item", attributes=[
                dc.Attribute("x", "number", True),
            ])),
        ]

    def test_map_collection_gets_implicit_id(self) -> None:
        """A map collection → entity whose records carry the map key as ``id``."""
        assert _entities("""
            type: object
            additionalProperties:
              type: object
              properties:
                title:    { type: string }
                servings: { type: integer }
              additionalProperties: false
              required: [title]
        """, "recipes") == [
            dc.Entity("recipes", item_type=dc.ObjectType("recipes.item", origin_item_type="recipes.item", attributes=[
                dc.Attribute("id",       "string",  True),
                dc.Attribute("title",    "string",  True),
                dc.Attribute("servings", "integer", False),
            ])),
        ]

    def test_nested_map_creates_child_entity(self) -> None:
        """A map inside a map's record → object[] attribute + parent.child entity."""
        assert _entities("""
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
                      name:   { type: string }
                      amount: { type: string }
                    additionalProperties: false
                    required: [name, amount]
              additionalProperties: false
              required: [title, ingredients]
        """, "recipes") == [
            dc.Entity("recipes", item_type=dc.ObjectType("recipes.item", origin_item_type="recipes.item", attributes=[
                dc.Attribute("id",    "string", True),
                dc.Attribute("title", "string", True),
                dc.Attribute("ingredients", "object[]", True,
                             child_entity="recipes.ingredients",
                             child_item_type="recipes.item.ingredients.item"),
            ])),
            dc.Entity(
                "recipes.ingredients",
                item_type=dc.ObjectType("recipes.item.ingredients.item", origin_item_type="recipes.item.ingredients.item", attributes=[
                    dc.Attribute("id",     "string", True),
                    dc.Attribute("name",   "string", True),
                    dc.Attribute("amount", "string", True),
                ]),
                parent_entity="recipes",
            ),
        ]

    def test_nested_object_prefix_flattened(self) -> None:
        """A singleton object inside a record → prefix.name flat attributes."""
        assert _entities("""
            type: array
            items:
              type: object
              properties:
                address:
                  type: object
                  properties:
                    city:    { type: string }
                    zipcode: { type: string }
                  additionalProperties: false
                  required: [city]
              additionalProperties: false
              required: [address]
        """, "persons") == [
            dc.Entity("persons", item_type=dc.ObjectType("persons.item", origin_item_type="persons.item", attributes=[
                dc.Attribute("address",         "object", True),
                dc.Attribute("address.city",    "string", True),
                dc.Attribute("address.zipcode", "string", False),
            ])),
        ]

    def test_array_object_creates_child_entity(self) -> None:
        """An array-of-objects property → object[] attribute + linked child entity (with .item)."""
        assert _entities("""
            type: array
            items:
              type: object
              properties:
                items:
                  type: array
                  items:
                    type: object
                    properties:
                      name: { type: string }
                    additionalProperties: false
                    required: [name]
              additionalProperties: false
        """, "orders") == [
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
        """An array-of-scalars property → type[] attribute."""
        assert _entities("""
            type: array
            items:
              type: object
              properties:
                tags:
                  type: array
                  items: { type: string }
              additionalProperties: false
        """, "articles") == [
            dc.Entity("articles", item_type=dc.ObjectType("articles.item", origin_item_type="articles.item", attributes=[
                dc.Attribute("tags", "string[]", False),
            ])),
        ]

    def test_nested_array_type_brackets(self) -> None:
        """An array of arrays of scalars → type[][] attribute."""
        assert _entities("""
            type: array
            items:
              type: object
              properties:
                matrix:
                  type: array
                  items:
                    type: array
                    items: { type: number }
              additionalProperties: false
        """, "sheets") == [
            dc.Entity("sheets", item_type=dc.ObjectType("sheets.item", origin_item_type="sheets.item", attributes=[
                dc.Attribute("matrix", "number[][]", False),
            ])),
        ]

    def test_nested_array_of_objects_creates_child_entity(self) -> None:
        """An array of arrays of objects → object[][] attribute + child entity (with .item)."""
        assert _entities("""
            type: array
            items:
              type: object
              properties:
                grid:
                  type: array
                  items:
                    type: array
                    items:
                      type: object
                      properties:
                        v: { type: number }
                      additionalProperties: false
                      required: [v]
              additionalProperties: false
        """, "boards") == [
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

    def test_entity_metadata_from_collection_layer(self) -> None:
        """The collection layer's metadata lands on ObjectType.metadata."""
        assert _entities("""
            type: array
            title: My Collection
            items:
              type: object
              properties:
                x: { type: string }
              additionalProperties: false
              required: [x]
        """, "things")[0].item_type.metadata == {"title": "My Collection"}

    def test_entity_metadata_collection_layer_wins_whole_mapping(self) -> None:
        """The collection layer wins as a mapping: a non-colliding key on the
        record layer is dropped with the rest, not merged in."""
        assert _entities("""
            type: object
            title: Recipe collection
            additionalProperties:
              type: object
              description: One recipe
              properties:
                title: { type: string }
              additionalProperties: false
        """, "recipes")[0].item_type.metadata == {"title": "Recipe collection"}

    def test_entity_metadata_falls_back_to_record_layer(self) -> None:
        """With no metadata on the collection layer, the record layer's is used."""
        assert _entities("""
            type: object
            additionalProperties:
              type: object
              title: Recipe
              description: One recipe
              properties:
                title: { type: string }
              additionalProperties: false
        """, "recipes")[0].item_type.metadata == {
            "title": "Recipe", "description": "One recipe",
        }

    def test_entity_metadata_skips_intermediate_array_layer(self) -> None:
        """Only the outermost and innermost layers are consulted: metadata on
        an array layer in between is dropped even when nothing outranks it."""
        assert _entities("""
            type: array
            items:
              type: array
              title: Row
              items:
                type: object
                title: Cell
                properties:
                  v: { type: number }
                additionalProperties: false
        """, "grid")[0].item_type.metadata == {"title": "Cell"}

    def test_attribute_metadata_scalar_array_keeps_array_layer(self) -> None:
        """On a scalar array the array layer's metadata reaches the Attribute;
        the item layer's has no slot."""
        assert _entities("""
            type: array
            items:
              type: object
              properties:
                tags:
                  type: array
                  title: Tag list
                  items:
                    type: string
                    title: Tag
              additionalProperties: false
        """, "recipes")[0].item_type.attributes[0] == dc.Attribute(
            "tags", "string[]", False, metadata={"title": "Tag list"},
        )

    def test_attribute_metadata_and_validation(self) -> None:
        """Metadata and validation keywords are transferred to the Attribute as written."""
        assert _entities("""
            type: array
            items:
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
        """, "recipes")[0].item_type.attributes == [
            dc.Attribute("title", "string", True, metadata={
                "title": "Recipe title",
                "description": "Short name of the dish",
                "default": "Untitled",
                "examples": ["Curry", "Pasta"],
                "deprecated": False,
                "format": "kebab-case",
            }),
            dc.Attribute("servings", "integer", False, validation={
                "minimum": 1, "maximum": 100, "exclusiveMinimum": 0,
            }),
            dc.Attribute("difficulty", "string", False, validation={
                "enum": ["easy", "medium", "hard"],
            }),
        ]

    def test_required_transferred(self) -> None:
        """Edge.required → Attribute.required."""
        assert [(a.id, a.required) for a in _entities("""
            type: array
            items:
              type: object
              properties:
                a: { type: string }
                b: { type: string }
              additionalProperties: false
              required: [a]
        """, "ts")[0].item_type.attributes] == [
            ("a", True), ("b", False),
        ]

    def test_singleton_with_collection_subproperty_creates_child_entity(self) -> None:
        """A singleton holding an object[] sub-property keeps the child entity link.

        Singleton-flatten emits the singleton itself as a type='object'
        scalar attribute and its sub-properties as dotted-name edges; for
        array-of-object sub-properties the child entity must be
        registered so that ``from: <singleton>.<collection>`` walks.
        """
        assert _entities("""
            type: array
            items:
              type: object
              properties:
                name: { type: string }
                hobby:
                  type: object
                  properties:
                    pets:
                      type: array
                      items:
                        type: object
                        properties:
                          name: { type: string }
                          kind: { type: string }
                        additionalProperties: false
                        required: [name]
                  additionalProperties: false
              additionalProperties: false
              required: [name, hobby]
        """, "members") == [
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
        assert _entities("""
            type: array
            items:
              type: object
              properties:
                address:
                  type: object
                  properties:
                    city: { type: string }
                    aliases:
                      type: array
                      items: { type: string }
                  additionalProperties: false
                  required: [city]
              additionalProperties: false
              required: [address]
        """, "persons") == [
            dc.Entity("persons", item_type=dc.ObjectType("persons.item", origin_item_type="persons.item", attributes=[
                dc.Attribute("address",         "object",   True),
                dc.Attribute("address.city",    "string",   True),
                dc.Attribute("address.aliases", "string[]", False),
            ])),
        ]

    def test_nested_singleton_flattens_at_any_depth(self) -> None:
        """Singleton under a singleton inlines too — one dotted attribute per level.

        The flattening budget is not spent after one level: every
        singleton on the way down contributes its own ``object``
        attribute plus dotted attributes for its sub-properties.
        """
        assert _entities("""
            type: array
            items:
              type: object
              properties:
                meta:
                  type: object
                  properties:
                    owner:
                      type: object
                      properties:
                        name: { type: string }
                        team:
                          type: object
                          properties:
                            code: { type: string }
                          additionalProperties: false
                          required: [code]
                      additionalProperties: false
                      required: [name]
                  additionalProperties: false
                  required: [owner]
              additionalProperties: false
              required: [meta]
        """, "screens") == [
            dc.Entity("screens", item_type=dc.ObjectType("screens.item", origin_item_type="screens.item", attributes=[
                dc.Attribute("meta",                 "object", True),
                dc.Attribute("meta.owner",           "object", True),
                dc.Attribute("meta.owner.name",      "string", True),
                dc.Attribute("meta.owner.team",      "object", False),
                dc.Attribute("meta.owner.team.code", "string", True),
            ])),
        ]

    def test_collection_under_nested_singleton_creates_child_entity(self) -> None:
        """An object[] two singletons down is walkable, like one singleton down.

        Guards the one entity the recursion actually adds: the child
        entity hangs off the fully-dotted edge name.
        """
        assert _entities("""
            type: array
            items:
              type: object
              properties:
                meta:
                  type: object
                  properties:
                    owner:
                      type: object
                      properties:
                        history:
                          type: array
                          items:
                            type: object
                            properties:
                              date: { type: string }
                            additionalProperties: false
                            required: [date]
                      additionalProperties: false
                  additionalProperties: false
                  required: [owner]
              additionalProperties: false
              required: [meta]
        """, "screens") == [
            dc.Entity("screens", item_type=dc.ObjectType("screens.item", origin_item_type="screens.item", attributes=[
                dc.Attribute("meta",       "object", True),
                dc.Attribute("meta.owner", "object", True),
                dc.Attribute("meta.owner.history", "object[]", False,
                             child_entity="screens.meta.owner.history",
                             child_item_type="screens.item.meta.owner.history.item"),
            ])),
            dc.Entity(
                "screens.meta.owner.history",
                item_type=dc.ObjectType("screens.item.meta.owner.history.item", origin_item_type="screens.item.meta.owner.history.item", attributes=[
                    dc.Attribute("date", "string", True),
                ]),
                parent_entity="screens",
            ),
        ]

    def test_x_ref_propagates_to_attribute(self) -> None:
        """x-ref reaches the Attribute; an omitted 'attribute' is filled
        with the implicit-id default."""
        assert _entities("""
            type: array
            items:
              type: object
              properties:
                artist_id:
                  type: string
                  x-ref: { entity: artists }
                curator:
                  type: string
                  x-ref: { entity: users, attribute: name }
              additionalProperties: false
              required: [artist_id]
        """, "albums") == [
            dc.Entity("albums", item_type=dc.ObjectType("albums.item", origin_item_type="albums.item", attributes=[
                dc.Attribute("artist_id", "string", True,
                             x_ref=dc.XRef(entity="artists", attribute="id")),
                dc.Attribute("curator", "string", False,
                             x_ref=dc.XRef(entity="users", attribute="name")),
            ])),
        ]

    def test_x_ref_on_dotted_singleton_subproperty(self) -> None:
        """x-ref on a sub-property of a singleton is carried by the dotted edge."""
        assert _entities("""
            type: array
            items:
              type: object
              properties:
                address:
                  type: object
                  properties:
                    city_id:
                      type: string
                      x-ref: { entity: cities }
                  additionalProperties: false
                  required: [city_id]
              additionalProperties: false
              required: [address]
        """, "users") == [
            dc.Entity("users", item_type=dc.ObjectType("users.item", origin_item_type="users.item", attributes=[
                dc.Attribute("address",         "object", True),
                dc.Attribute("address.city_id", "string", True,
                             x_ref=dc.XRef(entity="cities", attribute="id")),
            ])),
        ]

# fmt: on
