"""Normalizer — validate and normalize input data.

Copies non-Markdown files as-is. Converts Markdown files into YAML
with the built-in prose schema.
"""

import shutil
from pathlib import Path

from reqs_builder.components.normalizer.prose import parse_markdown
from reqs_builder.components.shared import yaml_dumper
from reqs_builder.components.shared.errors import with_error_propagation


@with_error_propagation
def normalize(src_dir: Path, *, out_dir: Path) -> None:
    """Normalize src_dir contents into out_dir."""
    for src_file in sorted(src_dir.rglob("*")):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src_dir)
        if src_file.suffix == ".md":
            normalize_markdown(src_file, rel, out_dir)
        else:
            _copy_file(src_file, out_dir / rel)


def normalize_markdown(src: Path, rel: Path, out_dir: Path) -> None:
    record = parse_markdown(
        src.read_text(encoding="utf-8"),
        str(rel.with_suffix("")),
    )
    dst = out_dir / rel.with_suffix(".yaml")
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as f:
        yaml_dumper.dump({"prose": [record.to_data()]}, f)


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
