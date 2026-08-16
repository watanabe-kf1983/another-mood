"""Tests for build_info — the invocation's fact store."""

import re
from datetime import datetime

from another_mood.components.shared.build_info import make_build_info
from another_mood.components.shared.tool_version import PROCESSOR_ID, tool_version


class TestMakeBuildInfo:
    def test_reports_the_processor_identity(self) -> None:
        info = make_build_info()
        assert info["processor.name"] == PROCESSOR_ID
        assert info["processor.version"] == tool_version()

    def test_started_at_is_iso_8601_at_seconds_precision_with_an_offset(self) -> None:
        stamped = make_build_info()["processor.started_at"]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T[\d:]{8}[+-]\d{2}:\d{2}", stamped)

    def test_started_at_stamps_the_moment_it_was_called(self) -> None:
        before = datetime.now().astimezone().replace(microsecond=0)
        stamped = datetime.fromisoformat(make_build_info()["processor.started_at"])
        assert before <= stamped <= datetime.now().astimezone()

    def test_carries_only_the_processor_namespace(self) -> None:
        assert all(key.startswith("processor.") for key in make_build_info())
