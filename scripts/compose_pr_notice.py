"""The advisory half of the pr-lint workflow: the sticky comment it posts.

Run by the pr-lint workflow rather than by ``make ci``: the inputs exist only
on a pull request. Standard library only, so the workflow needs no install
step. Reads the kinds ``check_release_trailer`` published and the paths the
pull request touches, and writes the comment body to ``NOTICE_FILE`` — empty
when there is nothing to say, which the workflow reads as "delete whatever an
earlier run left behind".

Each rule pairs a signal in the diff with a declaration that fails to match it;
none of them judges whether a change is *actually* breaking. Nothing here reads
the PR body, so a malformed trailer stops the job upstream instead of being
advised on as a missing one.
"""

import os
from collections.abc import Sequence
from pathlib import Path

GENERATION_DECLARATION = (
    "src/another_mood/components/manifest/supported_sbdb_versions.py"
)
REFERENCE_DOCS_PREFIX = "docs/reference/"

COMMENT_MARKER = "<!-- pr-lint -->"
CONVENTION_URL = (
    "https://github.com/watanabe-kf1983/another-mood/blob/main/DEVELOPMENT.md"
)


def main() -> None:
    kinds = frozenset(os.environ.get("DECLARED_KINDS", "").split())
    changed_paths = read_changed_paths(Path(os.environ["CHANGED_PATHS_FILE"]))

    notice = compose_notice(kinds, changed_paths)
    Path(os.environ["NOTICE_FILE"]).write_text(notice, encoding="utf-8")


def compose_notice(kinds: frozenset[str], changed_paths: Sequence[str]) -> str:
    """The comment body, or the empty string when no rule has anything to say."""
    notices = (
        *_generation_notices(changed_paths, kinds),
        *_reference_docs_notices(changed_paths, kinds),
    )
    if not notices:
        return ""
    else:
        return "\n\n".join(
            (
                COMMENT_MARKER,
                "### Release-Highlight notes",
                "\n\n---\n\n".join(notices),
                f"<sub>Non-blocking, and no action is needed if the reading above "
                f"is wrong. The convention lives in [DEVELOPMENT.md]({CONVENTION_URL})."
                f"</sub>\n",
            )
        )


def read_changed_paths(path: Path) -> Sequence[str]:
    return tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _generation_notices(
    changed_paths: Sequence[str], kinds: frozenset[str]
) -> Sequence[str]:
    if GENERATION_DECLARATION not in changed_paths or "breaking" in kinds:
        return ()
    else:
        return (
            f"**The supported sbdb generation set moved, and no `breaking` is "
            f"declared.**\n\n`{GENERATION_DECLARATION}` has a diff. A generation "
            f"dropping out of the supported set is a format break, and `breaking` "
            f"is mandatory for one — together with the incompatibility note and "
            f"the migration steps under `docs/`. Adding a generation is not a "
            f"break; ignore this if that is what happened.\n\n"
            f"```\nRelease-Highlight: breaking\n```",
        )


def _reference_docs_notices(
    changed_paths: Sequence[str], kinds: frozenset[str]
) -> Sequence[str]:
    touches_reference = any(
        path.startswith(REFERENCE_DOCS_PREFIX) for path in changed_paths
    )
    if not touches_reference or kinds:
        return ()
    else:
        return (
            f"**`{REFERENCE_DOCS_PREFIX}` changed, and no Release-Highlight is "
            f"declared.**\n\nIf the set of promises grew or shrank, say so with "
            f"`feature` — documenting existing behaviour counts, since it pulls "
            f"that behaviour into the contract. Restating, clarifying or "
            f"reorganising the same promises is `fix` or nothing at all.\n\n"
            f"```\nRelease-Highlight: feature\n```",
        )


if __name__ == "__main__":
    main()
