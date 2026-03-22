"""PageWriter — SectionProcessor implementation that writes pages to disk.

Receives a template name and data, delegates rendering to an injected
render function, and writes the result to ``{out_dir}/{template_name}/{id}.md``.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RenderFn = Callable[[str, dict[str, Any]], str]


@dataclass(frozen=True)
class PageWriter:
    out_dir: Path
    render: RenderFn

    def __call__(self, template_name: str, data: dict[str, Any]) -> str:
        if "id" not in data:
            raise KeyError(
                f'{{% section "{template_name}" %}} requires "id" in data, '
                f"got keys: {sorted(data.keys())}"
            )
        rendered = self.render(template_name, data)
        page_dir = self.out_dir / template_name
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / f"{data['id']}.md").write_text(rendered)
        return ""
