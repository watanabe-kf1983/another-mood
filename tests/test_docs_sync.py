"""Sync check — built-in schema YAMLs vs their reference-doc appendices.

The reference docs under ``docs/reference/`` quote the built-in schema
files under ``src/another_mood/resources/schemas/`` verbatim as
canonical appendices.  This test fails when they drift, so a contributor
who edits the schema YAMLs without updating the reference (or vice
versa) is caught at CI time.
"""

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DOCS_DIR = _REPO_ROOT / "docs" / "reference"
_SCHEMAS_DIR = _REPO_ROOT / "src" / "another_mood" / "resources" / "schemas"

# (markdown file, appendix heading, source yaml filename)
_CASES = [
    ("schema.md", "## Full schema-schema", "schema-schema.yaml"),
    ("schema.md", "## Full content-schema", "content-schema.yaml"),
    ("query.md", "## query-schema 全文", "query-schema.yaml"),
]


@pytest.mark.parametrize(("md_file", "heading", "yaml_file"), _CASES)
def test_appendix_matches_source(md_file: str, heading: str, yaml_file: str) -> None:
    md_text = (_DOCS_DIR / md_file).read_text(encoding="utf-8")
    yaml_text = (_SCHEMAS_DIR / yaml_file).read_text(encoding="utf-8")

    heading_idx = md_text.find(heading)
    assert heading_idx >= 0, f"heading {heading!r} not found in {md_file}"

    match = re.search(r"```yaml\n(.*?)\n```", md_text[heading_idx:], re.DOTALL)
    assert match, f"no ```yaml fence found under {heading!r} in {md_file}"

    appendix = match.group(1).rstrip("\n")
    expected = yaml_text.rstrip("\n")
    assert appendix == expected, (
        f"appendix under {heading!r} in {md_file} drifted from "
        f"src/another_mood/resources/schemas/{yaml_file}"
    )
