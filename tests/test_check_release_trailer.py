"""Tests for the blocking trailer checks the pr-lint workflow runs."""

from scripts.check_release_trailer import declared_kinds, trailer_defects


BREAKING = "## Breaking change\n\nThe manifest format moved to generation 2.\n"
HIGHLIGHT = "## Release highlight\n\nViews can now read nested fields.\n"


def defects(body: str) -> tuple[str, ...]:
    return tuple(trailer_defects(body))


class TestTrailerFormat:
    def test_accepts_every_kind(self) -> None:
        for kind in ("feature", "fix"):
            assert defects(f"Summary.\n\nRelease-Highlight: {kind}") == ()
        assert defects(f"{BREAKING}\nRelease-Highlight: breaking") == ()

    def test_accepts_a_trailing_newline_and_trailing_spaces(self) -> None:
        assert defects("Release-Highlight: fix  \n") == ()

    def test_accepts_a_body_written_with_crlf(self) -> None:
        assert defects("Summary.\r\n\r\nRelease-Highlight: fix\r\n") == ()

    def test_accepts_a_body_with_no_trailer_at_all(self) -> None:
        assert defects("Just a summary.\n") == ()

    def test_rejects_an_unknown_kind(self) -> None:
        assert len(defects("Release-Highlight: chore")) == 1

    def test_rejects_a_missing_space(self) -> None:
        assert len(defects("Release-Highlight:fix")) == 1

    def test_rejects_two_kinds_on_one_line(self) -> None:
        assert len(defects("Release-Highlight: feature, fix")) == 1

    def test_rejects_a_kind_followed_by_prose(self) -> None:
        assert len(defects("Release-Highlight: fix mood tap on empty input")) == 1

    def test_rejects_near_miss_keys(self) -> None:
        for key in (
            "Release-Highlights",
            "Release-Note",
            "Release-Notes",
            "Release_Highlight",
            "Release Highlight",
            "release-highlight",
        ):
            assert len(defects(f"{key}: fix")) == 1, key

    def test_reports_every_malformed_line(self) -> None:
        assert len(defects("Release-Note: fix\nRelease-Highlight: chore")) == 2

    def test_quotes_the_offending_line(self) -> None:
        assert "'Release-Note: fix'" in defects("Release-Note: fix")[0]

    def test_ignores_an_indented_example(self) -> None:
        """The documented escape hatch, and the release-time grep skips it too."""
        assert defects("Write this at the end:\n\n    Release-Highlight: fix\n") == ()

    def test_ignores_a_mention_inside_a_line(self) -> None:
        assert defects("The `Release-Note:` key was renamed.\n") == ()


class TestBreakingSection:
    def test_rejects_a_section_with_no_trailer(self) -> None:
        assert len(defects(BREAKING)) == 1

    def test_rejects_a_section_backed_only_by_another_kind(self) -> None:
        assert len(defects(f"{BREAKING}\nRelease-Highlight: feature")) == 1

    def test_rejects_a_break_declared_without_the_section(self) -> None:
        assert len(defects("Summary.\n\nRelease-Highlight: breaking")) == 1

    def test_accepts_a_break_beside_another_kind(self) -> None:
        body = f"{BREAKING}\nRelease-Highlight: breaking\nRelease-Highlight: feature"
        assert defects(body) == ()

    def test_matches_the_heading_case_insensitively(self) -> None:
        assert len(defects("## Breaking Change\n")) == 1

    def test_ignores_a_heading_at_another_level(self) -> None:
        assert defects("### Breaking change\n") == ()


class TestHighlightSection:
    def test_rejects_a_section_with_no_trailer(self) -> None:
        assert len(defects(HIGHLIGHT)) == 1

    def test_accepts_a_section_backed_by_feature_or_fix(self) -> None:
        for kind in ("feature", "fix"):
            assert defects(f"{HIGHLIGHT}\nRelease-Highlight: {kind}") == ()

    def test_rejects_a_section_backed_only_by_a_break(self) -> None:
        """The heading a break used to be described under now points elsewhere."""
        body = f"{BREAKING}\n{HIGHLIGHT}\nRelease-Highlight: breaking"
        assert "## Breaking change" in defects(body)[0]

    def test_accepts_both_sections_on_one_change(self) -> None:
        body = (
            f"{BREAKING}\n{HIGHLIGHT}\n"
            "Release-Highlight: breaking\nRelease-Highlight: feature"
        )
        assert defects(body) == ()

    def test_matches_the_heading_case_insensitively(self) -> None:
        assert len(defects("## Release Highlight\n")) == 1

    def test_ignores_a_heading_at_another_level(self) -> None:
        assert defects("### Release highlight\n") == ()

    def test_ignores_the_words_in_prose(self) -> None:
        assert defects("This PR needs no release highlight.\n") == ()


class TestDeclaredKinds:
    def test_reads_nothing_out_of_a_bare_body(self) -> None:
        assert declared_kinds("Just a summary.\n") == frozenset()

    def test_reads_the_declared_kind(self) -> None:
        assert declared_kinds("Summary.\n\nRelease-Highlight: fix\n") == {"fix"}

    def test_reads_every_kind_a_body_declares(self) -> None:
        body = "Release-Highlight: breaking\nRelease-Highlight: fix\n"
        assert declared_kinds(body) == {"breaking", "fix"}

    def test_an_indented_example_declares_nothing(self) -> None:
        assert declared_kinds("    Release-Highlight: fix\n") == frozenset()

    def test_a_malformed_line_declares_nothing(self) -> None:
        assert declared_kinds("Release-Note: breaking\n") == frozenset()
