"""Build info — the facts surrounding one invocation, as a flat string store."""

from collections.abc import Mapping
from datetime import datetime

from another_mood.components.shared.tool_version import PROCESSOR_ID, tool_version

type BuildInfo = Mapping[str, str]


def make_build_info() -> BuildInfo:
    """Mint the store for one invocation, stamping the moment it is called."""
    started_at = datetime.now().astimezone()
    return {
        "processor.name": PROCESSOR_ID,
        "processor.version": tool_version(),
        "processor.started_at": started_at.isoformat(timespec="seconds"),
    }
