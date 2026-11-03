# Data Catalog

## Definition

The **data catalog** (below, the catalog) is the inventory of entities and attributes built from the schema. `inspect_schema` validates `definition/schema.yaml` against the meta-schema, builds the catalog, and persists it as JSON (`inspect_schema/` in the [stage table](../20-pipeline.md#stages)).

One inventory carries entities of three origins:

- The entities of the user's schema
- The entities of the built-in schemas (prose / blob)
- The `__definition` entities that describe the shape of the catalog itself. The self-description that lets a query read the catalog with `from: __definition.entities`

Downstream stages, when they want to know the structure of the schema, read the catalog instead of rereading the schema:

- `normalize_contents` — the data check of x-refs (`data_fk_validator.py`). However, validating contents and normalizing map → array use JSON Schema itself, so this stage alone also reads the schema file. It does not watch the schema, so a schema change arrives as an update of `inspect_schema/`
- `derive_queries` — resolving `from:`, and generating the entities derived from views. Outputs the catalog with the derived entities added
- `compose` — passes the catalog through downstream as it is
- `generate` — drawing the database pages (`__db/`), and telling a record's origin (built-in prose / blob or not)
- `tap_schema` (`mood tap --schema`) — writes the JSON Schema of the tap document from the catalog

## compose's output matches the shape the catalog declares

Each clause of a query holds a record transformation (`apply`) and a catalog transformation (`derive`) as a pair from the same DSL fragment (`components/shared/query.py`). `derive_queries` uses `derive` to put the shape of a view's output on the catalog as a derived entity, and `compose` uses `apply` of the same `Query` to make the records.

Both pass the same clauses in the same order, and each clause's pair is consistent, so compose's output matches the shape derive_queries declared. Downstream (`generate`'s database pages, `tap_schema`) may trust the catalog without looking at the data. When adding a clause, add both of the pair.

## Shape

The shape is defined in `components/shared/data_catalog.py`. There are two representations: the tree of `Node` / `Edge` (an entity, and the child's attribute as seen from the parent; distinct from a node of the data tree) is the primary representation, and the sequence of Entity is its flat serialization. Between stages this sequence is passed as JSON.

The tree is what `derive_queries` needs: cutting out the subtree that a view's `from:` points at and grafting it back under the root as a derived entity is done on the tree.

An entity's id is the route to it on the data tree (`categories`, `categories.tasks`), and `from:` names an entity by it.

The type of one record (ObjectType) has a separate id (`_item_type_id` in `data_catalog.py`), so that a view's derived entity can carry records of the same type while having an id different from the original entity's.

A derived entity inherits the original record type as `origin_item_type`, and `generate` uses it to tell whether a record derives from the built-in prose / blob. A view that recomposes records (flatten, join) is no longer an instance of the original type, so it does not inherit.

Both ids are type-level identifiers that denote a position in the schema, distinct from the anchor path, the address of an individual record on the data tree (Anchor paths in `docs/reference/template.md`). Neither id appears in the assembly of anchor paths.
