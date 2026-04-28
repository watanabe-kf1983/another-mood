"""Normalize core — shared file pipeline used by content/query modules.

Walks a source directory, parses Markdown / YAML inputs, validates them
against a schema, applies dict-to-array normalization, and writes the
result to an output directory. Used by both ``content_normalizer`` and
``query_deriver``.

Includes the Markdown → ProseRecord parser and the schema-guided
dict-to-array transformer that the pipeline composes.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

from another_mood.components.preprocess.validator import Validator, parse_yaml
from another_mood.components.shared.diagnostic import Diagnostic, FileValidationError
from another_mood.components.shared.file_type import FileType
from another_mood.components.shared.json_data_model import save_model

# JSON-like str-keyed mappings.
type Schema = Mapping[str, object]
type DataMap = Mapping[str, object]


# ── pipeline ───────────────────────────────────────────────────────


def normalize(
    src_dir: Path,
    out_dir: Path,
    schema: Mapping[str, object],
    *,
    wrapper: Callable[[object], object] = lambda x: x,
) -> None:
    """Validate all files, then parse, normalize, and write each to out_dir."""
    check(src_dir, schema)
    for src_file in _iter_files(src_dir):
        data = _parse(src_file, src_dir)
        if data is None:
            continue
        normalized = normalize_data(data, schema)
        _write(wrapper(normalized), src_file.relative_to(src_dir), out_dir)


def check(src_dir: Path, schema: Mapping[str, object]) -> None:
    """Validate all files in src_dir against the given schema.

    Raises FileValidationError if any file has diagnostics.
    """
    validator = Validator(schema)
    diagnostics: list[Diagnostic] = []
    for src_file in _iter_files(src_dir):
        try:
            data = _parse(src_file, src_dir)
        except FileValidationError as exc:
            diagnostics.extend(exc.diagnostics)
            continue
        if data is None:
            continue
        diagnostics.extend(validator.validate(data, src_file))
    if diagnostics:
        raise FileValidationError(diagnostics=diagnostics)


def _iter_files(src_dir: Path) -> Sequence[Path]:
    """Recursively list regular files under src_dir (sorted)."""
    return [f for f in sorted(src_dir.rglob("*")) if f.is_file()]


def _parse(src: Path, src_dir: Path) -> Mapping[str, object] | None:
    """Parse a source file into data, or None if the file is not a recognized source."""
    if FileType.MARKDOWN.match(src):
        source = src.read_text(encoding="utf-8")
        rel = src.relative_to(src_dir)
        record = parse_markdown(source, str(rel.with_suffix("")))
        return {"prose": [record.to_data()]}
    if FileType.YAML.match(src):
        return parse_yaml(src)
    return None


def _write(data: object, rel: Path, out_dir: Path) -> None:
    # Append (not replace) so distinct source files (foo.yaml / foo.yml / foo.md)
    # never collide on the same destination.
    dst = out_dir / rel.with_name(rel.name + ".yaml")
    dst.parent.mkdir(parents=True, exist_ok=True)
    save_model(dst, data)


# ── markdown → prose ──────────────────────────────────────────────


_MD = MarkdownIt()


@dataclass(frozen=True)
class ProseRecord:
    id: str
    title: str | None
    body: str
    mime_type: str

    def to_data(self) -> Mapping[str, object]:
        data: dict[str, object] = {
            "id": self.id,
            "body": {
                "mime_type": self.mime_type,
                "content": self.body,
            },
        }
        if self.title is not None:
            data["title"] = self.title
        return data


def parse_markdown(content: str, id: str) -> ProseRecord:
    """Parse a Markdown string into a ProseRecord.

    Extracts title from the first H1 heading (None if absent).
    Body is the full file content.
    """
    title = _extract_h1_title(content)
    return ProseRecord(
        id=id,
        title=title,
        body=content,
        mime_type="text/markdown",
    )


def _extract_h1_title(content: str) -> str | None:
    """Extract text from the first H1 heading using Markdown AST."""
    tokens = _MD.parse(content)
    tree = SyntaxTreeNode(tokens)
    for node in tree.walk():
        if node.type == "heading" and node.tag == "h1":
            return node.children[0].content if node.children else None
    return None


# ── dict → array (additionalProperties pattern) ───────────────────


def normalize_data(data: object, schema: Schema) -> object:
    """Normalize data according to schema's additionalProperties patterns."""
    schema_type = schema.get("type")

    if schema_type == "object":
        data_map = cast(DataMap, data)
        if schema_properties := schema.get("properties"):
            return _recurse_properties(data_map, cast(Schema, schema_properties))
        if schema_additional := schema.get("additionalProperties"):
            return _flatten_dict(data_map, cast(Schema, schema_additional))

    if schema_type == "array":
        items = cast(Sequence[object], data)
        if schema_items := schema.get("items"):
            return _recurse_items(items, cast(Schema, schema_items))

    return data


def _flatten_dict(data: DataMap, additional_schema: Schema) -> list[dict[str, object]]:
    """Convert a dict-pattern object to an array with ``id`` fields.

    When additionalProperties is an object schema with properties, the
    value's properties are expanded directly.  For non-object types
    (string, number, etc.) the value is wrapped as ``{"id": key, "value": val}``.
    """
    if additional_schema.get("type") == "object" and "properties" in additional_schema:
        props = cast(Schema, additional_schema.get("properties"))
        return [
            {"id": key, **_recurse_properties(cast(DataMap, value), props)}
            for key, value in data.items()
        ]
    return [
        {"id": key, "value": normalize_data(value, additional_schema)}
        for key, value in data.items()
    ]


def _recurse_properties(data: DataMap, properties: Schema) -> dict[str, object]:
    """Recurse into each property value using its sub-schema."""
    return {
        key: normalize_data(value, cast(Schema, properties[key]))
        if key in properties
        else value
        for key, value in data.items()
    }


def _recurse_items(data: Sequence[object], items_schema: Schema) -> list[object]:
    """Recurse into each element of an array."""
    return [normalize_data(item, items_schema) for item in data]
