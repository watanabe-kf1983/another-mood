"""Normalizer — validate and normalize input data.

Copies non-Markdown files as-is. Converts Markdown files into YAML
with the built-in prose schema.
"""

import shutil
from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.representer import RoundTripRepresenter

from reqs_builder.prose import parse_markdown


class _LiteralStrRepresenter(RoundTripRepresenter):
    """Represent multiline strings as literal block scalars (|)."""

    def represent_str(self, data: str) -> object:
        if "\n" in data:
            return self.represent_scalar("tag:yaml.org,2002:str", data, style="|")  # type: ignore[reportUnknownMemberType]
        return super().represent_str(data)  # type: ignore[reportUnknownMemberType]


_LiteralStrRepresenter.add_representer(str, _LiteralStrRepresenter.represent_str)  # type: ignore[reportUnknownMemberType]

_yaml = YAML()
_yaml.version = (1, 1)  # YAML 1.1 per json-data-model.md serialization spec
_yaml.Representer = _LiteralStrRepresenter


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

    buf = StringIO()
    _yaml.dump({"prose": [record.to_data()]}, buf)  # type: ignore[reportUnknownMemberType]
    dst.write_text(buf.getvalue(), encoding="utf-8")


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
