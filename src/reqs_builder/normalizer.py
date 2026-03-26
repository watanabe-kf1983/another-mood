"""Normalizer — validate and normalize input data.

Copies YAML files as-is. Converts Markdown files into a prose.yaml
with the built-in prose schema.
"""

import shutil
from pathlib import Path

import yaml

from reqs_builder.prose import parse_markdown


def normalize(src_dir: Path, out_dir: Path) -> None:
    """Normalize src_dir contents into out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)

    md_files = sorted(src_dir.rglob("*.md"))
    non_md_files = sorted(
        p for p in src_dir.rglob("*") if p.is_file() and p.suffix != ".md"
    )

    # Copy non-Markdown files preserving directory structure
    for src_file in non_md_files:
        rel = src_file.relative_to(src_dir)
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst)

    # Convert each Markdown file into a corresponding .yaml file
    for src_file in md_files:
        rel = src_file.relative_to(src_dir)
        record = parse_markdown(
            src_file.read_text(encoding="utf-8"),
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
