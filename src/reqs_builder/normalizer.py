"""Normalizer — validate and normalize input data.

Copies non-Markdown files as-is. Converts Markdown files into YAML
with the built-in prose schema.
"""

import shutil
from pathlib import Path

import yaml

from reqs_builder.prose import parse_markdown


def normalize(src_dir: Path, out_dir: Path) -> None:
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
    dst.write_text(
        yaml.safe_dump(
            {"prose": [record.to_data()]},
            allow_unicode=True,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
