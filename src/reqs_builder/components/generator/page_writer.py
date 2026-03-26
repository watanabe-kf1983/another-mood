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
        rendered = self.render(template_name, data)
        out_file = self.out_dir / template_name / f"{data['id']}.md"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(rendered)
        return ""
