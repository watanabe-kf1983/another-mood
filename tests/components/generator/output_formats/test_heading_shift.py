"""Tests for the ``under_heading`` heading-shift transform (A6).

The filter-boundary adaptation (str coercion, Markup wrapping, template use)
is md.py's concern and is tested in test_md.py.
"""

import pytest

from another_mood.components.generator.output_formats.heading_shift import under_heading


class TestShiftAmount:
    """The shift is the marker's `#` count, added to every outline heading."""

    def test_shifts_every_heading_by_marker_length(self) -> None:
        assert under_heading("# A\n## B", "##") == "### A\n#### B"

    def test_single_hash_marker_shifts_by_one(self) -> None:
        assert under_heading("# A", "#") == "## A"


class TestHeadingSelection:
    """Only the fragment's own top-level ATX headings move; nothing else."""

    def test_shifts_an_indented_top_level_heading(self) -> None:
        # Up to 3 spaces of indentation is still a top-level heading.
        assert under_heading("   ## H", "##") == "   #### H"

    def test_leaves_setext_headings_untouched(self) -> None:
        assert under_heading("Title\n=====", "##") == "Title\n====="

    def test_leaves_hashes_in_code_fence_untouched(self) -> None:
        assert under_heading("```mermaid\n# x\n```", "##") == "```mermaid\n# x\n```"

    def test_leaves_a_heading_quoted_in_a_blockquote_untouched(self) -> None:
        # A blockquoted heading is quoted content, not part of the outline.
        assert under_heading("> # Quoted", "##") == "> # Quoted"

    def test_leaves_a_heading_inside_a_list_item_untouched(self) -> None:
        # Likewise a heading nested in a list item is subordinate content.
        assert under_heading("- # Item", "##") == "- # Item"

    def test_preserves_non_heading_body(self) -> None:
        body = "# Title\n\nA paragraph with a # sign mid-line.\n\n## Section\n"
        assert under_heading(body, "#") == (
            "## Title\n\nA paragraph with a # sign mid-line.\n\n### Section\n"
        )


class TestMarkerRewrite:
    """How the heading line's marker is rewritten."""

    def test_clamps_at_h6(self) -> None:
        assert under_heading("##### deep", "###") == "###### deep"

    def test_rewrites_only_the_opening_marker_not_a_closing_sequence(self) -> None:
        assert under_heading("## B ##", "##") == "#### B ##"


class TestInputContract:
    """Marker validation and the empty-input edge."""

    @pytest.mark.parametrize("marker", ["", "h2", "##x", "2", " ##"])
    def test_rejects_a_marker_that_is_not_a_run_of_hashes(self, marker: str) -> None:
        with pytest.raises(ValueError, match="run of '#'"):
            under_heading("# A", marker)

    def test_empty_input_yields_empty(self) -> None:
        # A split render returns "", so {% filter under_heading %} shifts
        # nothing — the no-op that keeps split and inline output identical.
        assert under_heading("", "##") == ""
