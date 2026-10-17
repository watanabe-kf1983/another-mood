"""How a build treats the shapes placed directly under the root.

The root is catalogued as a record: a top-level singleton folds into it,
and the collection inside the singleton opens an entity of its own,
which views can name and ``__db/`` gives pages to.  The singleton and
its scalars show on the root's own pages, and ``from:`` naming the
singleton is diagnosed as not an entity.
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


def test_top_level_shapes_get_db_pages(
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
    # The singleton and its scalar get no page of their own; they show on
    # the root's pages.
    assert not (db_dir / "__entity_defs" / "site_config.md").exists()
    root_def = (db_dir / "__root_def.md").read_text(encoding="utf-8")
    assert "| `site_config` |" in root_def
    assert "| `site_config.title` |" in root_def
    root_data = (db_dir / "__root_data.md").read_text(encoding="utf-8")
    assert "| My Site |" in root_data


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
    # ``site_config.items`` resolves; ``site_config`` is told apart from
    # a key that does not exist.
    assert messages == ["source 'site_config' is not an entity (type 'object')"]
