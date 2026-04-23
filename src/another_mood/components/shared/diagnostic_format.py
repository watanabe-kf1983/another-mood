"""Render diagnostic source snippets in the ESLint-codeframe style.

Pure functions only — no I/O. The caller is responsible for reading
the source file and passing its text in.
"""

_LINES_ABOVE = 3
_LINES_BELOW = 1


def format_pointed(
    line: int | None,
    column: int | None,
    file_text: str,
    *,
    lines_above: int = _LINES_ABOVE,
    lines_below: int = _LINES_BELOW,
) -> str:
    """Render a code-frame snippet pointing at (line, column).

    Example — format_pointed(line=6, column=7, file_text=...):

        3 |     fields:
        4 |       title: string
        5 |       content: text
      > 6 |       stauts: string
          |       ^
        7 |       count: int

    Returns "" when line is missing or out of range.
    """
    lines = file_text.splitlines()
    if not line or line > len(lines):
        return ""

    start = max(1, line - lines_above)
    end = min(len(lines), line + lines_below)
    gutter_width = len(str(end))

    out: list[str] = []
    for n in range(start, end + 1):
        marker = ">" if n == line else " "
        out.append(f"{marker} {n:>{gutter_width}} | {lines[n - 1]}")
        if n == line and column is not None:
            out.append(f"  {' ' * gutter_width} | {' ' * (column - 1)}^")
    return "\n".join(out)
