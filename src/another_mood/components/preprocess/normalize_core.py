"""Normalize core — shared file pipeline used by content/query modules.

Walks a source directory, parses Markdown / YAML inputs, validates them
against a schema, applies dict-to-array normalization, and writes the
result to an output directory. Used by both ``content_normalizer`` and
``query_normalizer``.
"""

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from another_mood.components.preprocess.dict_to_array import normalize_data
from another_mood.components.preprocess.prose import parse_markdown
from another_mood.components.preprocess.validator import Validator, parse_yaml
from another_mood.components.shared.diagnostic import Diagnostic, FileValidationError
from another_mood.components.shared.file_type import FileType
from another_mood.components.shared.json_data_model import save_model


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
