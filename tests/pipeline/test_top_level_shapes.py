"""How a build treats the shapes placed directly under the root today.

Current limitation, not a contract.  A top-level singleton and the
collection inside it reach ``tap`` and the templates but never the
catalog, so views cannot name them and ``__db/`` has no page for them.
The intended behavior is what the same shapes get inside a record: the
singleton folds into the holding record and the collection opens an
entity of its own.

TODO: rewrite every expectation here once the root is catalogued as a
record; none of them is to be preserved.
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


def test_top_level_singleton_reaches_templates_but_has_no_db_pages(
    tmp_path: Path,
) -> None:
    result = _build(tmp_path)

    assert not result.has_errors()
    out_dir = Path(result.out_dir)
    # Intended: ``site_config.items`` gets Entity / Data pages like ``users``.
    # The data itself is intact: the template read the singleton.
    page = (out_dir / "default" / "index.md").read_text(encoding="utf-8")
    assert "# My Site" in page
    # The catalog lists the collection only.
    db_dir = out_dir / "__db"
    assert (db_dir / "__entity_defs" / "users.md").is_file()
    assert not (db_dir / "__entity_defs" / "site_config.md").exists()
    assert not (db_dir / "__entity_defs" / "site_config.items.md").exists()
    assert "site_config" not in (db_dir / "index.md").read_text(encoding="utf-8")


def test_from_cannot_name_a_top_level_singleton_or_its_collection(
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
    # Today both read as a key that does not exist at all.  Intended:
    # ``site_config.items`` resolves, and ``site_config`` is diagnosed as
    # "not a collection" instead.
    assert messages == [
        "unknown source 'site_config'",
        "unknown source 'site_config.items'",
    ]
