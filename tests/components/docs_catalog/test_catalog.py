"""Tests for the docs_catalog component."""

from pathlib import Path

import pytest

from another_mood.components.docs_catalog.catalog import (
    list_docs,
    load_catalog,
    read_doc,
)


@pytest.fixture()
def synthetic_docs(tmp_path: Path) -> Path:
    """Create a small synthetic docs tree with a manifest."""
    (tmp_path / "catalog.yaml").write_text(
        "resources:\n"
        "  - path: foo.md\n"
        "    description: |\n"
        "      Foo description.\n"
        "  - path: bar/baz.yaml\n"
        "    description: Baz description.\n",
        encoding="utf-8",
    )
    (tmp_path / "foo.md").write_text("# Foo", encoding="utf-8")
    (tmp_path / "bar").mkdir()
    (tmp_path / "bar" / "baz.yaml").write_text("baz: true", encoding="utf-8")
    return tmp_path


def test_load_catalog_parses_manifest(synthetic_docs: Path) -> None:
    catalog = load_catalog(synthetic_docs)

    assert set(catalog) == {"docs://foo.md", "docs://bar/baz.yaml"}

    foo = catalog["docs://foo.md"]
    assert foo.name == "foo.md"
    assert foo.description == "Foo description."
    assert foo.mime_type == "text/markdown"
    assert foo.path == (synthetic_docs / "foo.md").resolve()

    baz = catalog["docs://bar/baz.yaml"]
    assert baz.name == "bar/baz.yaml"
    assert baz.mime_type == "application/yaml"


def test_list_docs_returns_bundled_catalog() -> None:
    """Smoke test against the real bundled docs."""
    uris = {entry.uri for entry in list_docs()}

    assert "docs://reference/cli.md" in uris


def test_read_doc_returns_content() -> None:
    """Smoke test against the real bundled docs."""
    text = read_doc("docs://reference/cli.md")

    assert "# CLI Reference" in text


def test_read_doc_unknown_uri_raises() -> None:
    with pytest.raises(ValueError, match="Unknown doc URI"):
        read_doc("docs://nonexistent")
