"""Tests for the advisory comment the pr-lint workflow posts."""

from pathlib import Path

from scripts.compose_pr_notice import compose_notice, read_changed_paths

GENERATION_FILE = "src/another_mood/components/manifest/supported_sbdb_versions.py"


def notice(*changed_paths: str, kinds: frozenset[str] = frozenset()) -> str:
    return compose_notice(kinds, changed_paths)


class TestGenerationRule:
    def test_speaks_up_when_the_declaration_moved_without_breaking(self) -> None:
        body = notice(GENERATION_FILE)
        assert GENERATION_FILE in body
        assert "Release-Highlight: breaking" in body

    def test_stays_quiet_when_breaking_is_declared(self) -> None:
        assert notice(GENERATION_FILE, kinds=frozenset({"breaking"})) == ""

    def test_a_weaker_kind_does_not_satisfy_it(self) -> None:
        assert notice(GENERATION_FILE, kinds=frozenset({"feature"})) != ""

    def test_stays_quiet_when_the_declaration_is_untouched(self) -> None:
        assert notice("src/another_mood/cli.py") == ""


class TestReferenceDocsRule:
    def test_speaks_up_when_the_reference_changed_without_any_kind(self) -> None:
        assert "Release-Highlight: feature" in notice("docs/reference/cli.md")

    def test_stays_quiet_for_any_declared_kind(self) -> None:
        assert notice("docs/reference/cli.md", kinds=frozenset({"fix"})) == ""

    def test_stays_quiet_for_docs_outside_the_reference(self) -> None:
        assert notice("docs/guides.md") == ""


class TestComment:
    def test_is_empty_when_there_is_nothing_to_say(self) -> None:
        assert notice("README.md") == ""

    def test_carries_the_marker_the_workflow_looks_for(self) -> None:
        assert notice(GENERATION_FILE).startswith("<!-- pr-lint -->")

    def test_joins_both_rules_into_one_comment(self) -> None:
        body = notice(GENERATION_FILE, "docs/reference/manifest.md")
        assert "Release-Highlight: breaking" in body
        assert "Release-Highlight: feature" in body

    def test_a_fix_kind_leaves_only_the_generation_rule(self) -> None:
        body = notice(
            GENERATION_FILE, "docs/reference/manifest.md", kinds=frozenset({"fix"})
        )
        assert "Release-Highlight: breaking" in body
        assert "Release-Highlight: feature" not in body

    def test_points_at_the_convention(self) -> None:
        assert "DEVELOPMENT.md" in notice(GENERATION_FILE)


class TestReadChangedPaths:
    def test_reads_one_path_per_line_and_drops_blanks(self, tmp_path: Path) -> None:
        listing = tmp_path / "changed-paths.txt"
        listing.write_text(
            "docs/reference/cli.md\n\nsrc/another_mood/cli.py\n", "utf-8"
        )

        assert read_changed_paths(listing) == (
            "docs/reference/cli.md",
            "src/another_mood/cli.py",
        )

    def test_reads_an_empty_listing(self, tmp_path: Path) -> None:
        listing = tmp_path / "changed-paths.txt"
        listing.write_text("", encoding="utf-8")

        assert read_changed_paths(listing) == ()
