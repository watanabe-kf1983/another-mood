"""JSON Schema of the tap document, derived from the catalog tree."""

from collections.abc import Mapping

from another_mood.components.shared import data_catalog as dc

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


def document_schema(root: dc.Node) -> Mapping[str, object]:
    """``root`` is the catalog tree (``dc.build_tree``) whose child edges
    are the document's top-level keys."""
    return {"$schema": SCHEMA_DIALECT, **_node_schema(root, "object")}


# ── Helpers ───────────────────────────────────────────────────────────


def _edge_schema(edge: dc.Edge, node: dc.Node) -> Mapping[str, object]:
    return _annotated(edge.metadata, _typed(edge.type, node, edge.validation))


def _typed(
    type_: str, node: dc.Node, validation: Mapping[str, object] | None
) -> Mapping[str, object]:
    # ``validation`` rides down to the innermost layer: the catalog records
    # it only on scalars, and a scalar's constraints describe each item.
    if type_.endswith("[]"):
        return {"type": "array", "items": _typed(type_[:-2], node, validation)}
    elif node.children:
        return _node_schema(node, type_)
    else:
        return _annotated(node.metadata, {"type": type_, **(validation or {})})


def _node_schema(node: dc.Node, type_: str) -> Mapping[str, object]:
    required = [edge.name for edge, _ in node.children if edge.required]
    return _annotated(
        node.metadata,
        {
            "type": type_,
            "properties": {
                edge.name: _edge_schema(edge, child) for edge, child in node.children
            },
            **({"required": required} if required else {}),
        },
    )


def _annotated(
    metadata: Mapping[str, object] | None, schema: Mapping[str, object]
) -> Mapping[str, object]:
    return {**(metadata or {}), **schema}
