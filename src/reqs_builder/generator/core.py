"""Generator — render views data through Jinja2 templates to Markdown.

See: docs-src/contents/internal/components/generator.md
"""

from functools import reduce
from pathlib import Path
from typing import Any

import yaml
from jinja2 import FileSystemLoader

from reqs_builder.generator.page_writer import PageWriter
from reqs_builder.generator.section_extension import make_section_env
from reqs_builder.json_data_model import deep_merge


def load_views(views_dir: Path) -> dict[str, Any]:
    """Read all *.yaml files from views_dir and merge them.

    Files are processed in sorted order (alphabetical).
    Merge follows the JSON data model strategy (see json_data_model.py).
    """
    files = sorted(views_dir.glob("*.yaml"))
    docs: list[dict[str, Any]] = [yaml.safe_load(f.read_text()) or {} for f in files]
    return reduce(deep_merge, docs, {})


def generate(views_dir: Path, templates_dir: Path, out_dir: Path) -> None:
    """Load views, render index.md template, and write output."""
    views = load_views(views_dir)

    def render_template(template_name: str, data: dict[str, Any]) -> str:
        template = env.get_template(f"{template_name}.md")
        return template.render(data)

    writer = PageWriter(out_dir=out_dir, render=render_template)
    env = make_section_env(writer)
    env.loader = FileSystemLoader(templates_dir)

    template = env.get_template("index.md")
    rendered = template.render(views)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.md").write_text(rendered)
