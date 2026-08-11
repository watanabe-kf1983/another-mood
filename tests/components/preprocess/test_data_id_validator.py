"""Tests for the record identity check (id uniqueness among siblings)."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from textwrap import dedent
from typing import cast

from another_mood.components.preprocess.data_id_validator import check_duplicate_ids
from another_mood.components.shared.user_source.diagnostic import (
    Diagnostic,
    DiagnosticSeverity,
)
from another_mood.components.shared.user_source.source_loader import parse_mapping


def _data(
    yaml_text: str, tmp_path: Path, name: str = "contents.yaml"
) -> Mapping[str, Sequence[Mapping[str, object]]]:
    """Parse YAML text (already in normalized array form) with UserStr tagging."""
    src = tmp_path / name
    src.write_text(dedent(yaml_text).lstrip("\n"))
    return cast(Mapping[str, Sequence[Mapping[str, object]]], parse_mapping(src))


def _summary(d: Diagnostic) -> tuple[int | None, str]:
    """Compact (line, message) tuple for comparing diagnostic lists."""
    return (d.line, d.message)


class TestHappyPath:
    def test_distinct_ids_pass(self, tmp_path: Path) -> None:
        data = _data(
            """
            members:
              - id: alice
              - id: bob
            """,
            tmp_path,
        )
        assert list(check_duplicate_ids(data)) == []

    def test_same_id_in_different_entities_passes(self, tmp_path: Path) -> None:
        data = _data(
            """
            members:
              - id: alice
            albums:
              - id: alice
            """,
            tmp_path,
        )
        assert list(check_duplicate_ids(data)) == []

    def test_records_without_ids_pass(self, tmp_path: Path) -> None:
        data = _data(
            """
            steps:
              - label: Boil water
              - label: Boil water
            """,
            tmp_path,
        )
        assert list(check_duplicate_ids(data)) == []

    def test_empty_input_passes(self) -> None:
        assert list(check_duplicate_ids({})) == []


class TestTopLevelDuplicates:
    def test_reports_every_colliding_record(self, tmp_path: Path) -> None:
        data = _data(
            """
            members:
              - id: alice
              - id: bob
              - id: alice
            """,
            tmp_path,
        )
        assert [_summary(d) for d in check_duplicate_ids(data)] == [
            (2, "duplicate id 'alice' in members"),
            (4, "duplicate id 'alice' in members"),
        ]

    def test_severity_is_error(self, tmp_path: Path) -> None:
        data = _data(
            """
            members:
              - id: alice
              - id: alice
            """,
            tmp_path,
        )
        diagnostics = check_duplicate_ids(data)
        assert [d.severity for d in diagnostics] == [DiagnosticSeverity.error] * 2
        assert {d.source for d in diagnostics} == {"duplicate-id"}

    def test_ids_collide_across_scalar_types(self, tmp_path: Path) -> None:
        data = _data(
            """
            members:
              - id: 10
              - id: "10"
            """,
            tmp_path,
        )
        assert len(check_duplicate_ids(data)) == 2

    def test_untagged_id_reports_without_a_location(self) -> None:
        data: Mapping[str, Sequence[Mapping[str, object]]] = {
            "prose": [{"id": "about"}, {"id": "about"}]
        }
        diagnostics = check_duplicate_ids(data)
        assert [(d.file, d.line) for d in diagnostics] == [(None, None)] * 2
        assert diagnostics[0].message == "duplicate id 'about' in prose"


class TestCrossFileDuplicates:
    def test_ids_merged_from_two_files_collide(self, tmp_path: Path) -> None:
        first = _data("members:\n  - id: alice\n", tmp_path, "members.yaml")
        second = _data("members:\n  - id: alice\n", tmp_path, "members copy.yaml")
        merged = {
            "members": [*first["members"], *second["members"]],
        }

        diagnostics = check_duplicate_ids(merged)

        assert [cast(Path, d.file).name for d in diagnostics] == [
            "members.yaml",
            "members copy.yaml",
        ]


class TestNestedCollections:
    def test_duplicates_under_one_parent_are_reported(self, tmp_path: Path) -> None:
        data = _data(
            """
            members:
              - id: alice
                links:
                  - id: home
                  - id: home
            """,
            tmp_path,
        )
        assert [_summary(d) for d in check_duplicate_ids(data)] == [
            (4, "duplicate id 'home' in members/alice/links"),
            (5, "duplicate id 'home' in members/alice/links"),
        ]

    def test_same_id_under_different_parents_passes(self, tmp_path: Path) -> None:
        data = _data(
            """
            members:
              - id: alice
                links:
                  - id: home
              - id: bob
                links:
                  - id: home
            """,
            tmp_path,
        )
        assert list(check_duplicate_ids(data)) == []

    def test_collections_under_an_id_less_record_are_skipped(
        self, tmp_path: Path
    ) -> None:
        """An id-less array element has no address, so nothing below it
        can collide on one."""
        data = _data(
            """
            groups:
              - label: core
                links:
                  - id: home
                  - id: home
            """,
            tmp_path,
        )
        assert list(check_duplicate_ids(data)) == []

    def test_duplicates_under_an_object_attribute_are_reported(
        self, tmp_path: Path
    ) -> None:
        data = _data(
            """
            members:
              - id: alice
                profile:
                  links:
                    - id: home
                    - id: home
            """,
            tmp_path,
        )
        assert [d.message for d in check_duplicate_ids(data)] == [
            "duplicate id 'home' in members/alice/profile/links",
            "duplicate id 'home' in members/alice/profile/links",
        ]
