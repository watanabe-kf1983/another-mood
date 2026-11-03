# JSON Data Model

## Definition

What the YAML DSL and the template engine operate on is the "JSON data model": a tree structure made of object / array / string / number / boolean. It has no null; the absence of a value is expressed by omitting the key (the same tree as the data model section of [Concept](../../../10-concept/10-product.md#data-model-a-json-tree-with-discipline)).

It is unrelated to JSON as a serialization format, and works the same on data loaded from YAML.

From inspect_schema to generate, every stage operates consistently on this data model.

Note that there is no formal specification corresponding to the term "JSON data model" (XML has the W3C recommendation XML Information Set, but JSON has no equivalent). CBOR's RFC 8949 uses the phrase "the JSON data model", and this project follows it.

YAML's data model is a superset of the JSON data model (date types, the distinction between integers and floats, anchors, and so on), but the data this application handles stays within the JSON data model.

## Serialization formats

The files this project reads and writes fall into three groups, and each group has its serialization format:

| Group | Examples | Format |
|---|---|---|
| (1) The user's input | `contents/*.yaml`, `contents/*.json`, `definition/schema.yaml`, `reports.yaml`, `sbdb.yaml` | YAML 1.2 / JSON |
| (2) Built-in schema resources | `resources/schemas/*.yaml` | YAML 1.2 |
| (3) Intermediate representation between stages | Each stage's output under the workspace ([transport](index.md#transport)), `__build_report` | JSON |

- YAML is 1.2 (applies to (1) and (2)). It avoids the unintended booleanization of `yes`/`no`, and accepts JSON input without an additional parser
- The intermediate representation is JSON (applies to (3)). Build time was dominated by ruamel.yaml's read/write. The workspace is not an external contract, so the change stays internal. The schema language side is what blocks the routes by which non-JSON values (dates and the like) could arrive

## Uniform fields in objects within arrays

The objects within arrays that the Normalizer and the components emit all, as a rule, have the common fields. However, a nullable item (one not `required` in the schema) omits the field itself when the value is absent (no null is filled in).

Reason: templates draw nothing for a missing field ([Template](../../10-external/50-template.md#a-missing-value-draws-nothing-and-is-no-error)), so the field's absence is itself "not drawn".

Filling in null would not prevent errors on nested access such as `None.child`, and a fallback through `dict.get("key", {})` stops working once null is in. The absent field is easier to handle on the template side.

## Reserved prefixes

The following prefixes are reserved on object keys in the JSON data model:

| Prefix | Use | Examples |
|---|---|---|
| `_` (single) | Metadata the Generator injects into nodes (`generator/data_tree.py`) | `_parent`, `_meta` |
| `__` (double) | System-internal fields (the user does not handle them directly) | `__build_report`, `__definition` |

`__` is rejected in top-level entity names, view names, and edition names (they share a namespace with the built-in sources and with the tool's own output such as `__db/`). `_` is a reservation by convention, placed so that the Generator's metadata does not shadow keys in the user's data.

The built-in prose / blob schemas' key names `prose` / `blob` are kept without a prefix.
