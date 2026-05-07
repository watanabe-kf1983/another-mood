"""Tests for the docs_catalog component."""

from pathlib import Path

import pytest

from another_mood.components.docs_catalog.catalog import docs_root, load_catalog


@pytest.fixture()
def synthetic_docs(tmp_path: Path) -> Path:
    """Create a small synthetic docs tree with a manifest."""
    (tmp_path / "mcp-resources.yaml").write_text(
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


def test_load_catalog_against_bundled_docs() -> None:
    """Smoke test: the real shipped catalog loads without error."""
    catalog = load_catalog(docs_root())

    assert "docs://reference/cli.md" in catalog
    assert catalog["docs://reference/cli.md"].path.is_file()
