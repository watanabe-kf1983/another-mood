"""How a build treats the shapes placed directly under the root today.

Partly a current limitation, not a contract.  The root is catalogued as
a record: a top-level singleton folds into it, and the collection inside
the singleton opens an entity of its own, which views can name and
``__db/`` gives pages to.  The singleton itself still has no page, and
``from:`` naming it reads as a key that does not exist at all.

TODO: rewrite the expectations marked "Intended" as the root's own page
and the "not a collection" diagnostic land.
"""

from pathlib import Path
from textwrap import dedent

from another_mood import command
from another_mood.config import ProjectConfig

_SCHEMA = """\
type: object
additionalProperties: false
properties:
  site_config:
    type: object
    additionalProperties: false
    properties:
      title: { type: string }
      items:
        type: array
        items:
          type: object
          additionalProperties: false
          properties:
            name: { type: string }
  users:
    type: array
    items:
      type: object
      additionalProperties: false
      properties:
        name: { type: string }
"""

_CONTENTS = """\
site_config:
  title: My Site
  items:
    - name: first
users:
  - name: alice
"""


def _write_project(project: Path, *, views: str = "") -> None:
    files = {
        "sbdb.yaml": "sbdb_version: 1\ntitle: Top-level shapes\n",
        "definition/schema.yaml": _SCHEMA,
        "definition/reports.yaml": "file_per: []\n",
        "definition/templates/index.md": "# {{ site_config.title }}\n",
        "contents/data.yaml": _CONTENTS,
    }
    if views:
        files["definition/views/views.yaml"] = views
    for rel, text in files.items():
        path = project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (project / "definition" / "views").mkdir(exist_ok=True)


def _build(tmp_path: Path, *, views: str = "") -> command.BuildResult:
    project = tmp_path / "project"
    _write_project(project, views=views)
    return command.build(ProjectConfig(namespace_root=tmp_path, project_dir=project))


def test_collection_in_top_level_singleton_gets_db_pages(
    tmp_path: Path,
) -> None:
    result = _build(tmp_path)

    assert not result.has_errors()
    out_dir = Path(result.out_dir)
    page = (out_dir / "default" / "index.md").read_text(encoding="utf-8")
    assert "# My Site" in page
    # ``site_config.items`` gets Entity / Data pages like ``users``.
    db_dir = out_dir / "__db"
    assert (db_dir / "__entity_defs" / "users.md").is_file()
    assert (db_dir / "__entity_defs" / "site_config.items.md").is_file()
    data_page = (db_dir / "__data" / "site_config.items.md").read_text(encoding="utf-8")
    assert "| first |" in data_page
    # Intended: the singleton shows on the root's own page.
    assert not (db_dir / "__entity_defs" / "site_config.md").exists()


def test_from_names_the_collection_but_not_the_singleton(
    tmp_path: Path,
) -> None:
    views = dedent("""\
        config:
          from: site_config
        config_items:
          from: site_config.items
    """)

    result = _build(tmp_path, views=views)

    assert result.has_errors()
    messages = sorted(d.message for d in result.diagnostics)
    # ``site_config.items`` resolves.  Intended: ``site_config`` is
    # diagnosed as "not a collection" instead.
    assert messages == ["unknown source 'site_config'"]
