"""Tests for ProjectConfig path defaults and publish-destination resolution."""

from pathlib import Path

import pytest

from another_mood.config import ConfigValidationError, ProjectConfig


ROOT = Path("/ws")


class TestAnotherMoodRoot:
    def test_project_dir_directly_under_the_root(self) -> None:
        config = ProjectConfig(
            namespace_root=ROOT, project_dir=ROOT / "docs"
        ).resolved_for_build()
        assert config.out_dir == ROOT / ".another-mood/docs/output"
        assert config.site_dir == ROOT / ".another-mood/docs/site"

    def test_multi_component_tail(self) -> None:
        config = ProjectConfig(
            namespace_root=ROOT, project_dir=ROOT / "showcase/starter"
        ).resolved_for_build()
        assert config.out_dir == ROOT / ".another-mood/showcase/starter/output"

    def test_project_dir_as_the_root_itself(self) -> None:
        # The MCP binding: the tail collapses and output lands in the project.
        project = ROOT / "docs"
        config = ProjectConfig(
            namespace_root=project, project_dir=project
        ).resolved_for_build()
        assert config.out_dir == project / ".another-mood/output"


class TestResolvedForTap:
    def test_fills_unset_tap_dir_with_the_default(self) -> None:
        config = ProjectConfig(
            namespace_root=ROOT, project_dir=ROOT / "docs"
        ).resolved_for_tap()
        assert config.tap_dir == ROOT / ".another-mood/docs/tap"

    def test_keeps_an_explicit_tap_dir(self) -> None:
        config = ProjectConfig(
            namespace_root=ROOT, project_dir=ROOT / "docs", tap_dir=Path("/custom")
        ).resolved_for_tap()
        assert config.tap_dir == Path("/custom")


class TestVerifyProjectDirUnderNamespaceRoot:
    """project_dir must lie under namespace_root; external paths are rejected (G8).

    The containment check runs before the existence check, so an external path
    is rejected regardless of whether it exists — pinning the check ordering
    via the error message.
    """

    def test_accepts_subdir_under_the_root(self, tmp_path: Path) -> None:
        (tmp_path / "docs").mkdir()
        ProjectConfig(
            namespace_root=tmp_path, project_dir=tmp_path / "docs"
        ).verify()  # no raise

    def test_accepts_the_root_itself(self, tmp_path: Path) -> None:
        ProjectConfig(
            namespace_root=tmp_path, project_dir=tmp_path
        ).verify()  # no raise

    def test_rejects_a_path_outside_the_root(self, tmp_path: Path) -> None:
        config = ProjectConfig(
            namespace_root=tmp_path, project_dir=tmp_path.parent / "elsewhere"
        )
        with pytest.raises(ConfigValidationError, match="under the namespace root"):
            config.verify()

    def test_rejects_a_missing_directory(self, tmp_path: Path) -> None:
        config = ProjectConfig(namespace_root=tmp_path, project_dir=tmp_path / "absent")
        with pytest.raises(ConfigValidationError, match="not found"):
            config.verify()


class TestVerifyPathsAreAbsolute:
    """Every path field must be absolute — the config layer never resolves.

    The boundary layers absolutize what they pass, but MOOD_* environment
    variables reach the fields untouched, so the invariant is enforced here
    rather than trusted.
    """

    def test_rejects_a_relative_project_dir(self, tmp_path: Path) -> None:
        config = ProjectConfig(namespace_root=tmp_path, project_dir=Path("docs"))
        with pytest.raises(ConfigValidationError, match="project_dir=docs"):
            config.verify()

    @pytest.mark.parametrize("field", ["out_dir", "site_dir", "tap_dir", "tmp_dir"])
    def test_rejects_a_relative_output_dir(self, field: str, tmp_path: Path) -> None:
        config = ProjectConfig(
            namespace_root=tmp_path, project_dir=tmp_path
        ).model_copy(update={field: Path("out")})
        with pytest.raises(ConfigValidationError, match=f"{field}=out"):
            config.verify()

    def test_names_every_relative_path_at_once(self, tmp_path: Path) -> None:
        # One report per run beats a fix-one-rerun loop through the fields.
        config = ProjectConfig(
            namespace_root=tmp_path,
            project_dir=tmp_path,
            out_dir=Path("out"),
            site_dir=Path("site"),
        )
        with pytest.raises(ConfigValidationError, match="out_dir=out, site_dir=site"):
            config.verify()

    def test_runs_before_the_containment_check(self, tmp_path: Path) -> None:
        # A relative project_dir is not "under" an absolute root either, so
        # the ordering decides which error the user sees. The absolute rule
        # is the more actionable one.
        config = ProjectConfig(namespace_root=tmp_path, project_dir=Path("docs"))
        with pytest.raises(ConfigValidationError, match="must be absolute"):
            config.verify()


class TestPublishDestinations:
    def test_unset_by_default(self) -> None:
        config = ProjectConfig(namespace_root=ROOT, project_dir=ROOT / "docs")
        assert config.out_dir is None
        assert config.site_dir is None

    def test_build_keeps_explicit_dirs(self) -> None:
        config = ProjectConfig(
            namespace_root=ROOT,
            project_dir=ROOT / "docs",
            out_dir=Path("/pin/out"),
            site_dir=Path("/pin/site"),
        ).resolved_for_build()
        assert config.out_dir == Path("/pin/out")
        assert config.site_dir == Path("/pin/site")

    def test_watch_publishes_nothing_by_default(self) -> None:
        config = ProjectConfig(
            namespace_root=ROOT, project_dir=ROOT / "docs"
        ).resolved_for_watch()
        assert config.out_dir is None
        assert config.site_dir is None

    def test_watch_opts_into_md_via_out_dir(self) -> None:
        config = ProjectConfig(
            namespace_root=ROOT, project_dir=ROOT / "docs", out_dir=Path("/pin/out")
        ).resolved_for_watch()
        assert config.out_dir == Path("/pin/out")

    def test_watch_never_publishes_site(self) -> None:
        # Even a pinned site_dir (e.g. MOOD_SITE_DIR) is dropped: the live
        # server is watch's only HTML consumer.
        config = ProjectConfig(
            namespace_root=ROOT, project_dir=ROOT / "docs", site_dir=Path("/pin/site")
        ).resolved_for_watch()
        assert config.site_dir is None


class TestVarsFromTheEnvironment:
    def _vars(self) -> dict[str, str]:
        return ProjectConfig(namespace_root=ROOT, project_dir=ROOT / "docs").vars

    def test_strips_the_envelope_and_lowercases_the_rest(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The envelope is one literal prefix, not a path to split on, so the
        # underscores of a longer name survive it.
        monkeypatch.setenv("MOOD_VARS_CI_BUILD_NUMBER", "42")
        assert self._vars() == {"ci_build_number": "42"}

    def test_ignores_the_other_mood_variables(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MOOD_HOST", "0.0.0.0")
        monkeypatch.setenv("MOOD_VARS_GIT_SHA", "abc123")
        assert self._vars() == {"git_sha": "abc123"}

    def test_ignores_the_bare_envelope(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # An empty name would take the whole namespace as one key.
        monkeypatch.setenv("MOOD_VARS_", "orphan")
        assert self._vars() == {}


def test_injected_vars_merge_onto_the_existing_ones() -> None:
    config = ProjectConfig(
        namespace_root=ROOT,
        project_dir=ROOT / "docs",
        vars={"git_sha": "existing", "ci_run_url": "https://ci.test/7"},
    ).with_injected_vars({"git_sha": "injected"})
    assert config.vars == {"git_sha": "injected", "ci_run_url": "https://ci.test/7"}
