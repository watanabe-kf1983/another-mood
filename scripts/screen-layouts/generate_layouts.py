"""Draw the screen-layout wireframes of the system-dev-docs-ja showcase.

A screen layout is the one design-document artifact this showcase cannot
derive from its records: it is a drawing, not a projection of data. So the
drawing is authored, as an HTML mockup that lives in the showcase's own
``contents/`` beside the SVG it produces — a reader who wants to redraw a
screen edits the HTML, and the project ships them the source, not just the
picture.

Authoring the SVG directly would mean placing every coordinate by hand, and a
caption one character longer would break the drawing. Instead the mockup is
plain HTML laid out by its stylesheet; headless Chrome performs the layout,
``measure.js`` reports the geometry it arrived at, and this script turns that
geometry into a line drawing.

``measure.js`` is injected into a throwaway copy rather than referenced from
the mockup, so that what ships with the showcase is a page about the screen
and nothing about how it gets measured.

Usage (from the repository root, with google-chrome on PATH)::

    uv run scripts/screen-layouts/generate_layouts.py          # every mockup
    uv run scripts/screen-layouts/generate_layouts.py SC04     # just one

Standard library only: the measuring step is a browser this repository does
not otherwise depend on, so it is invoked as a subprocess rather than driven
through a client library.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast
from xml.sax.saxutils import escape

MEASURE_JS = Path(__file__).parent / "measure.js"
# The mockups are showcase content, not part of this scaffold: they are
# authored beside the drawings they produce and ship with the project.
LAYOUT_DIR = (
    Path(__file__).parent.parent.parent
    / "showcase"
    / "system-dev-docs-ja"
    / "contents"
    / "画面レイアウト"
)

# Margin around the screen frame, so the frame's own stroke is not clipped by
# the viewBox and the drawing does not sit flush against surrounding text.
MARGIN = 8

# Measured edges land on whole pixels, where a one-pixel stroke straddles the
# boundary and renders as two grey half-pixels. Shifting every rectangle by
# half a pixel centres the stroke inside one pixel instead. The shift is
# uniform rather than an inset, so edges two boxes share stay coincident.
CRISP = 0.5

# The caret drawn inside a select box, measured in from its trailing edge.
MARKER_INSET = 8
MARKER_WIDTH = 8
MARKER_HEIGHT = 5

INK = "#333"
SHADE = "#eee"
TEXT = "#111"
# Generic families only: the SVG is rendered by whichever viewer opens it, and
# naming the font the mockup was measured with would promise metrics no other
# machine has.
FONT_STACK = "sans-serif"

# --dump-dom hands back the whole document; the measurements are the one
# element measure.js appended to it.
_MEASURED = re.compile(
    r'<script type="application/json" id="wf-measured">(?P<json>.*?)</script>',
    re.DOTALL,
)


def main(argv: Sequence[str]) -> int:
    mockups = _select_mockups(argv)
    if not mockups:
        print(f"no mockup matched {list(argv)}", file=sys.stderr)
        return 1
    for mockup in mockups:
        measured = _measure(mockup)
        destination = LAYOUT_DIR / f"{mockup.stem}.svg"
        destination.write_text(build_svg(measured), encoding="utf-8")
        print(f"{mockup.name} -> {destination.relative_to(Path.cwd())}")
    return 0


def build_svg(measured: Mapping[str, object]) -> str:
    """Render one screen's measurements as an SVG line drawing."""
    width = _as_float(measured["width"]) + MARGIN * 2
    height = _as_float(measured["height"]) + MARGIN * 2
    parts = _as_parts(measured["parts"])
    title = str(measured["title"])

    # Rectangles first, then text: a shaded box drawn after a caption would
    # paint over it, and document order gives no guarantee about the two.
    body = [
        *(_rect(p) for p in parts if p["kind"] == "rect"),
        *(_text(p) for p in parts if p["kind"] == "text"),
    ]
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_n(width)} {_n(height)}"',
            f'     width="{_n(width)}" height="{_n(height)}"',
            f'     role="img" aria-label="{escape(title)} の画面レイアウト">',
            # An explicit background keeps the drawing legible where the page
            # around it is dark; the strokes are near-black.
            f'<rect width="{_n(width)}" height="{_n(height)}" fill="#fff"/>',
            f'<g font-family="{FONT_STACK}">',
            *body,
            "</g>",
            "</svg>",
            "",
        ]
    )


def _select_mockups(argv: Sequence[str]) -> Sequence[Path]:
    everything = sorted(LAYOUT_DIR.glob("SC*.html"))
    if not argv:
        return everything
    wanted = {name.removesuffix(".html") for name in argv}
    return [p for p in everything if p.stem in wanted]


def _measure(mockup: Path) -> Mapping[str, object]:
    with tempfile.TemporaryDirectory() as workspace:
        staged = _stage(mockup, Path(workspace))
        dom = subprocess.run(
            [
                "google-chrome",
                "--headless",
                "--no-sandbox",
                "--disable-gpu",
                # The mockups are static, but the measuring script runs on
                # `load`; the budget lets Chrome finish that turn before
                # dumping.
                "--virtual-time-budget=2000",
                "--window-size=1200,1600",
                "--dump-dom",
                staged.as_uri(),
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    found = _MEASURED.search(dom)
    if found is None:
        message = f"{mockup.name}: the page produced no measurements"
        raise RuntimeError(message)
    measured: object = json.loads(found.group("json"))
    if not isinstance(measured, Mapping):
        message = f"{mockup.name}: measurements are not an object"
        raise TypeError(message)
    return cast("Mapping[str, object]", measured)


def _stage(mockup: Path, workspace: Path) -> Path:
    """Copy the mockup somewhere it can be measured without being altered.

    The stylesheet comes along because the mockup links to it as a sibling,
    and the measuring script is appended here rather than kept in the mockup's
    own source.
    """
    for stylesheet in mockup.parent.glob("*.css"):
        shutil.copy2(stylesheet, workspace / stylesheet.name)
    staged = workspace / mockup.name
    measuring = MEASURE_JS.read_text(encoding="utf-8")
    page = mockup.read_text(encoding="utf-8")
    staged.write_text(f"{page}\n<script>{measuring}</script>\n", encoding="utf-8")
    return staged


def _rect(part: Mapping[str, object]) -> str:
    x = _as_float(part["x"]) + MARGIN + CRISP
    y = _as_float(part["y"]) + MARGIN + CRISP
    w = _as_float(part["w"])
    h = _as_float(part["h"])
    fill = SHADE if part["shaded"] else "none"
    radius = _as_float(part["radius"])
    rounded = f' rx="{_n(radius)}"' if radius else ""
    box = (
        f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}"'
        f' fill="{fill}" stroke="{INK}" stroke-width="1"{rounded}/>'
    )
    return box + _marker(x + w, y + h / 2) if part["marker"] else box


def _marker(right: float, middle: float) -> str:
    """The caret that tells a box the user picks a value in from one they type in.

    Drawn rather than written, so it does not depend on the renderer having a
    glyph for it.
    """
    left = right - MARKER_INSET - MARKER_WIDTH
    top = middle - MARKER_HEIGHT / 2
    return (
        f'<path d="M{_n(left)} {_n(top)}'
        f" h{_n(MARKER_WIDTH)}"
        f' l-{_n(MARKER_WIDTH / 2)} {_n(MARKER_HEIGHT)} Z" fill="{INK}"/>'
    )


def _text(part: Mapping[str, object]) -> str:
    # Measured boxes are line boxes, so the glyphs sit on the vertical centre;
    # `central` puts them there without needing the font's baseline metrics.
    y = _as_float(part["y"]) + _as_float(part["h"]) / 2 + MARGIN
    weight = ' font-weight="700"' if part["bold"] else ""
    return (
        f'<text x="{_n(_as_float(part["x"]) + MARGIN)}" y="{_n(y)}"'
        f' font-size="{_n(_as_float(part["fontSize"]))}" fill="{TEXT}"'
        f' dominant-baseline="central"{weight}>{escape(str(part["text"]))}</text>'
    )


def _as_parts(parts: object) -> Sequence[Mapping[str, object]]:
    if not isinstance(parts, list):
        message = "measurements carry no part list"
        raise TypeError(message)
    listed = cast("list[object]", parts)
    return [cast("Mapping[str, object]", p) for p in listed if isinstance(p, Mapping)]


def _as_float(value: object) -> float:
    if not isinstance(value, (int, float)):
        message = f"expected a number, got {value!r}"
        raise TypeError(message)
    return float(value)


def _n(value: float) -> str:
    """Trim a measurement to the shortest form that still reads exactly."""
    return f"{value:.1f}".removesuffix(".0")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
