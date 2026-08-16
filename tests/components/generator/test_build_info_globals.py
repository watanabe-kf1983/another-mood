"""Tests for the build_info template global."""

from another_mood.components.generator.build_info_globals import (
    make_build_info_globals,
)


class TestMakeBuildInfoGlobals:
    def test_returns_the_value_of_a_set_key(self) -> None:
        query = make_build_info_globals({"vars.git_sha": "abc123"})["build_info"]
        assert query("vars.git_sha") == "abc123"

    def test_returns_nothing_for_a_key_the_store_does_not_carry(self) -> None:
        query = make_build_info_globals({"processor.name": "x"})["build_info"]
        assert query("vars.git_sha") is None

    def test_returns_nothing_when_no_key_is_given(self) -> None:
        # An absent argument asks nothing; the store is not searched for "None".
        query = make_build_info_globals({"None": "trap"})["build_info"]
        assert query(None) is None
