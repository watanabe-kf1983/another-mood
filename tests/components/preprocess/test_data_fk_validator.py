"""Tests for data-level FK integrity check (D6)."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from textwrap import dedent
from typing import cast

import yaml

from another_mood.components.preprocess.data_fk_validator import check_fk_data
from another_mood.components.preprocess.source_loader import parse_yaml
from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.diagnostic import Diagnostic


def _catalog(yaml_text: str) -> Sequence[dc.Entity]:
    """Build a typed catalog list from a YAML entity-list string."""
    raw = cast(list[Mapping[str, object]], yaml.safe_load(dedent(yaml_text)))
    return [dc.Entity.from_dict(e) for e in raw]


def _data(
    yaml_text: str, tmp_path: Path, name: str = "contents.yaml"
) -> Mapping[str, Sequence[Mapping[str, object]]]:
    """Parse YAML text (already in normalized array form) with UserStr tagging."""
    src = tmp_path / name
    src.write_text(dedent(yaml_text).lstrip("\n"))
    return cast(Mapping[str, Sequence[Mapping[str, object]]], parse_yaml(src))


def _summary(d: Diagnostic) -> tuple[int | None, str]:
    """Compact (line, message) tuple for comparing diagnostic lists."""
    return (d.line, d.message)


# A catalog reused by several happy-path / dangling-FK scenarios.
_ARTISTS_ALBUMS_CATALOG = """
    - id: artists
      item_type:
        id: artists.item
        attributes:
          - { id: id, type: string, required: true }
          - { id: name, type: string, required: true }
    - id: albums
      item_type:
        id: albums.item
        attributes:
          - { id: id, type: string, required: true }
          - id: artist_id
            type: string
            required: true
            x_ref: { entity: artists, attribute: id }
"""


class TestHappyPath:
    def test_all_fk_values_resolve(self, tmp_path: Path) -> None:
        catalog = _catalog(_ARTISTS_ALBUMS_CATALOG)
        data = _data(
            """
            artists:
              - id: miyavi
                name: Miyavi
              - id: luna
                name: Luna
            albums:
              - id: a1
                artist_id: miyavi
              - id: a2
                artist_id: luna
            """,
            tmp_path,
        )
        assert list(check_fk_data(catalog, data)) == []


class TestDanglingFK:
    def test_single_violation_reports_line_and_target(self, tmp_path: Path) -> None:
        catalog = _catalog(_ARTISTS_ALBUMS_CATALOG)
        data = _data(
            """
            artists:
              - id: miyavi
                name: Miyavi
            albums:
              - id: a1
                artist_id: ghost
            """,
            tmp_path,
        )
        diagnostics = check_fk_data(catalog, data)
        assert [_summary(d) for d in diagnostics] == [
            (6, "x-ref albums.artist_id = 'ghost' has no match in artists.id"),
        ]
        assert diagnostics[0].source == "x-ref-data"

    def test_multiple_violations_collected(self, tmp_path: Path) -> None:
        catalog = _catalog(_ARTISTS_ALBUMS_CATALOG)
        data = _data(
            """
            artists:
              - id: miyavi
                name: Miyavi
            albums:
              - id: a1
                artist_id: ghost
              - id: a2
                artist_id: spectre
            """,
            tmp_path,
        )
        assert sorted(
            d.line for d in check_fk_data(catalog, data) if d.line is not None
        ) == [6, 8]


class TestSelfReference:
    CATALOG = """
        - id: genres
          item_type:
            id: genres.item
            attributes:
              - { id: id, type: string, required: true }
              - { id: name, type: string, required: true }
              - id: parent_id
                type: string
                required: false
                x_ref: { entity: genres, attribute: id }
    """

    def test_self_reference_resolves(self, tmp_path: Path) -> None:
        catalog = _catalog(self.CATALOG)
        data = _data(
            """
            genres:
              - id: electronic
                name: Electronic
              - id: techno
                name: Techno
                parent_id: electronic
            """,
            tmp_path,
        )
        assert list(check_fk_data(catalog, data)) == []

    def test_self_reference_dangling(self, tmp_path: Path) -> None:
        catalog = _catalog(self.CATALOG)
        data = _data(
            """
            genres:
              - id: techno
                name: Techno
                parent_id: missing
            """,
            tmp_path,
        )
        diagnostics = check_fk_data(catalog, data)
        assert [_summary(d) for d in diagnostics] == [
            (4, "x-ref genres.parent_id = 'missing' has no match in genres.id"),
        ]


class TestOptionalFK:
    CATALOG = """
        - id: labels
          item_type:
            id: labels.item
            attributes:
              - { id: id, type: string, required: true }
              - { id: name, type: string, required: true }
        - id: albums
          item_type:
            id: albums.item
            attributes:
              - { id: id, type: string, required: true }
              - id: label_id
                type: string
                required: false
                x_ref: { entity: labels, attribute: id }
    """

    def test_absent_value_skipped(self, tmp_path: Path) -> None:
        catalog = _catalog(self.CATALOG)
        data = _data(
            """
            labels:
              - id: moonlit
                name: Moonlit
            albums:
              - id: a1
                label_id: moonlit
              - id: a2
            """,
            tmp_path,
        )
        assert list(check_fk_data(catalog, data)) == []


class TestNestedFromEntity:
    """FK declared on a nested (child) entity attribute."""

    CATALOG = """
        - id: instruments
          item_type:
            id: instruments.item
            attributes:
              - { id: id, type: string, required: true }
              - { id: name, type: string, required: true }
        - id: artists
          item_type:
            id: artists.item
            attributes:
              - { id: id, type: string, required: true }
              - { id: name, type: string, required: true }
              - id: members
                type: object[]
                required: false
                child_entity: artists.members
                child_item_type: artists.members.item
        - id: artists.members
          parent_entity: artists
          item_type:
            id: artists.members.item
            attributes:
              - { id: id, type: string, required: true }
              - id: instrument_id
                type: string
                required: false
                x_ref: { entity: instruments, attribute: id }
    """

    def test_nested_fk_resolves(self, tmp_path: Path) -> None:
        catalog = _catalog(self.CATALOG)
        data = _data(
            """
            instruments:
              - id: guitar
                name: Guitar
              - id: drums
                name: Drums
            artists:
              - id: miyavi
                name: Miyavi
                members:
                  - id: ao
                    instrument_id: guitar
                  - id: ko
                    instrument_id: drums
            """,
            tmp_path,
        )
        assert list(check_fk_data(catalog, data)) == []

    def test_nested_fk_dangling(self, tmp_path: Path) -> None:
        catalog = _catalog(self.CATALOG)
        data = _data(
            """
            instruments:
              - id: guitar
                name: Guitar
            artists:
              - id: miyavi
                name: Miyavi
                members:
                  - id: ao
                    instrument_id: piano
            """,
            tmp_path,
        )
        diagnostics = check_fk_data(catalog, data)
        assert [_summary(d) for d in diagnostics] == [
            (
                9,
                "x-ref artists.members.instrument_id = 'piano' has no match in instruments.id",
            ),
        ]


class TestExplicitTargetAttribute:
    """FK targets a non-id attribute (e.g. ``attribute: code``)."""

    CATALOG = """
        - id: countries
          item_type:
            id: countries.item
            attributes:
              - { id: id, type: string, required: true }
              - { id: code, type: string, required: true }
        - id: labels
          item_type:
            id: labels.item
            attributes:
              - { id: id, type: string, required: true }
              - id: country_code
                type: string
                required: false
                x_ref: { entity: countries, attribute: code }
    """

    def test_resolves_against_explicit_attribute(self, tmp_path: Path) -> None:
        catalog = _catalog(self.CATALOG)
        data = _data(
            """
            countries:
              - id: jp
                code: JPN
              - id: pt
                code: PRT
            labels:
              - id: moonlit
                country_code: JPN
            """,
            tmp_path,
        )
        assert list(check_fk_data(catalog, data)) == []

    def test_dangling_against_explicit_attribute(self, tmp_path: Path) -> None:
        catalog = _catalog(self.CATALOG)
        data = _data(
            """
            countries:
              - id: jp
                code: JPN
            labels:
              - id: moonlit
                country_code: USA
            """,
            tmp_path,
        )
        diagnostics = check_fk_data(catalog, data)
        assert [_summary(d) for d in diagnostics] == [
            (6, "x-ref labels.country_code = 'USA' has no match in countries.code"),
        ]


class TestUntaggedValue:
    """A FROM-side value without UserStr tagging still produces a diagnostic."""

    def test_diagnostic_without_position(self) -> None:
        catalog = _catalog(_ARTISTS_ALBUMS_CATALOG)
        # Plain str values (e.g. data re-loaded via typ='safe').  The walker
        # cannot recover a source location, but still names the offender so
        # the user can grep for it.
        data: Mapping[str, Sequence[Mapping[str, object]]] = {
            "artists": [{"id": "miyavi", "name": "Miyavi"}],
            "albums": [{"id": "a1", "artist_id": "ghost"}],
        }
        diagnostics = check_fk_data(catalog, data)
        assert len(diagnostics) == 1
        diag = diagnostics[0]
        assert diag.file is None
        assert diag.line is None
        assert diag.column is None
        assert (
            diag.message
            == "x-ref albums.artist_id = 'ghost' has no match in artists.id"
        )
