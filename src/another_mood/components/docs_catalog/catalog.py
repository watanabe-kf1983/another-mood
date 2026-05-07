"""Bundled documentation catalog.

A *doc entry* is a single file from the bundled ``docs/`` tree exposed as an
MCP resource.  The catalog is declared in ``docs/mcp-resources.yaml`` (the
manifest) as a list of ``{path, description}`` items.

Public API (in increasing order of convenience):

- :func:`load_catalog` — low-level parser.  Takes a docs root path and returns
  a ``uri -> DocEntry`` mapping
- :func:`list_docs` — list all bundled doc entries
- :func:`read_doc` — read one bundled doc by its ``docs://`` URI
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import cast

import yaml

CATALOG_FILE = "mcp-resources.yaml"

MIME_TYPES: Mapping[str, str] = {
    ".md": "text/markdown",
    ".yaml": "application/yaml",
}


@dataclass(frozen=True)
class DocEntry:
    """One entry in the bundled docs catalog."""

    uri: str
    name: str
    description: str
    mime_type: str
    path: Path


def list_docs() -> Sequence[DocEntry]:
    """Return all bundled doc entries from the shipped catalog."""
    return list(load_catalog(_docs_root()).values())


def read_doc(uri: str) -> str:
    """Read a bundled doc by its ``docs://`` URI.

    Raises ``ValueError`` if ``uri`` is not in the catalog (catalog-external
    paths are rejected).
    """
    catalog = load_catalog(_docs_root())
    entry = catalog.get(uri)
    if entry is None:
        raise ValueError(
            f"Unknown doc URI: {uri!r}. Call list_docs() to see available URIs."
        )
    return entry.path.read_text(encoding="utf-8")


def load_catalog(docs_root: Path) -> Mapping[str, DocEntry]:
    """Read ``<docs_root>/mcp-resources.yaml`` and return ``uri -> DocEntry``.

    Trusts the manifest's shape since it is shipped with the package; relies
    on ``read_text`` / ``yaml.safe_load`` to raise on a missing or
    syntactically broken file.
    """
    raw = cast(
        Mapping[str, list[Mapping[str, str]]],
        yaml.safe_load((docs_root / CATALOG_FILE).read_text(encoding="utf-8")),
    )
    entries: dict[str, DocEntry] = {}
    for e in raw["resources"]:
        rel = e["path"]
        uri = f"docs://{rel}"
        entries[uri] = DocEntry(
            uri=uri,
            name=rel,
            description=e["description"].strip(),
            mime_type=MIME_TYPES[Path(rel).suffix],
            path=(docs_root / rel).resolve(),
        )
    return entries


def _docs_root() -> Path:
    """Return the directory containing the bundled docs/ tree.

    Resolves to ``another_mood/_docs`` in a packaged install (mapped via
    ``[tool.hatch.build.targets.wheel.force-include]``) and to the
    repository's ``docs/`` directory in an editable install.
    """
    pkg_root = Path(str(resources.files("another_mood")))
    packaged = pkg_root / "_docs"
    if packaged.is_dir():
        return packaged
    return pkg_root.parent.parent / "docs"
