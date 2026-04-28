"""Content normalizer — parse, validate, and normalize source contents.

Every source file is parsed into data, validated against the merged
schema (built-in prose schema + user schema), and normalized
(dict-to-array conversion for additionalProperties patterns).
"""

from collections.abc import Mapping
from importlib import resources
from pathlib import Path

from another_mood.components.preprocess.normalize_core import normalize
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.json_data_model import load_model

_BUILTIN_CONTENTS_SCHEMA_FILE = Path(
    str(resources.files("another_mood.resources") / "schemas" / "content-schema.yaml")
)


@Component(out_dir="out_dir", upstream_dirs=["data_catalog_dir"])
def normalize_contents(
    src_dir: Path,
    *,
    schema_file: Path,
    data_catalog_dir: Path | None = None,
    out_dir: Path,
) -> None:
    """Normalize src_dir contents into out_dir."""
    normalize(src_dir, out_dir, build_contents_schema(schema_file))


def build_contents_schema(
    schema_file: Path,
) -> Mapping[str, object]:
    """Build a validation/normalization schema for content files.

    Merges the built-in prose schema with the user's schema.yaml.  Both
    files are root JSON Schemas (subset); the merge happens at the
    `properties` level so that each top-level key in a content file is
    validated against the matching entry.
    """
    return load_model(_BUILTIN_CONTENTS_SCHEMA_FILE, schema_file)
