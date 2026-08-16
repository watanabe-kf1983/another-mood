"""Tests for the build_info template global."""

from another_mood.components.generator.build_info_globals import (
    make_build_info_globals,
)

# One store for every case below: a set key, plus a "None" key that must stay
# unreachable by stringifying an argument that was never passed.
_build_info = make_build_info_globals({"vars.git_sha": "abc123", "None": "trap"})[
    "build_info"
]


class TestBuildInfo:
    def test_returns_the_value_of_a_set_key(self) -> None:
        assert _build_info("vars.git_sha") == "abc123"

    def test_prefers_a_set_value_over_the_default(self) -> None:
        assert _build_info("vars.git_sha", "(dev)") == "abc123"

    def test_returns_nothing_for_a_key_the_store_does_not_carry(self) -> None:
        assert _build_info("vars.build_number") is None

    def test_falls_back_to_the_default_for_a_key_the_store_does_not_carry(self) -> None:
        assert _build_info("vars.build_number", "(dev)") == "(dev)"

    def test_returns_nothing_when_no_key_is_given(self) -> None:
        assert _build_info(None) is None

    def test_falls_back_to_the_default_when_no_key_is_given(self) -> None:
        assert _build_info(None, "(dev)") == "(dev)"
