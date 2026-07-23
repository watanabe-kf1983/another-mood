"""Write-once sweep: no pipeline stage may write into an existing inode.

Runs the real pipeline twice (content change in between). After each stage,
every produced file is hardlink-snapshotted and all snapshots are re-checked.
A snapshot pins the inode a stage produced, so a later in-place write — by a
downstream stage or by the re-run — changes the snapshot's bytes and fails
the check. Blind spot: rewriting identical bytes in place is invisible here;
test_preparation.py pins the known such site (prepare_render) directly.
"""

import hashlib
import os
from pathlib import Path

from another_mood import command
from another_mood.config import ProjectConfig
from another_mood.layout import resolve_layout
from another_mood.pipeline.stages import STAGE_FACTORIES
from another_mood.pipeline.workspace import Workspace

_BLOB_V1 = b"\x89PNG-fake-bytes-v1"
_BLOB_V2 = b"\x89PNG-fake-bytes-v2-different"

# Coordination metadata, rewritten in place by design and never transported
# downstream, so no inode sharing can arise: .version.json is exclusive_write's
# sync ordering marker, .lock is a filelock artifact.
_EXEMPT_SUFFIXES = (".version.json", ".lock")


def test_no_stage_writes_into_an_existing_inode(tmp_path: Path) -> None:
    project = _scaffold_project(tmp_path)
    workspace, published = _make_workspace(tmp_path, project)
    observers = _Observers(
        watch_roots=(workspace.root, published), obs_root=tmp_path / "observers"
    )

    _run_all_stages(workspace, observers, run_label="run1")

    members = project / "contents" / "members.yaml"
    members.write_text(
        members.read_text(encoding="utf-8").replace("Alice", "Alicia"),
        encoding="utf-8",
    )
    (project / "contents" / "cover.png").write_bytes(_BLOB_V2)

    _run_all_stages(workspace, observers, run_label="run2")

    # Guard against a vacuous sweep: the change must reach the published
    # output, otherwise run2 diverged nowhere and detected nothing.
    published_blob = published / "output" / "default" / "blob" / "cover.png"
    assert published_blob.read_bytes() == _BLOB_V2
    published_member = published / "output" / "default" / "members" / "alice.md"
    assert "Alicia" in published_member.read_text(encoding="utf-8")


def test_observers_flag_in_place_writes_only(tmp_path: Path) -> None:
    watched = tmp_path / "watched"
    watched.mkdir()
    replaced = watched / "replaced.md"
    corrupted = watched / "corrupted.md"
    replaced.write_text("v1", encoding="utf-8")
    corrupted.write_text("v1", encoding="utf-8")
    observers = _Observers(watch_roots=(watched,), obs_root=tmp_path / "observers")
    observers.snapshot()

    replaced.unlink()
    replaced.write_text("v2", encoding="utf-8")
    with corrupted.open("r+", encoding="utf-8") as f:
        f.write("v2")

    assert observers.mutated() == [corrupted]


def _scaffold_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    command.init(project)
    (project / "contents" / "cover.png").write_bytes(_BLOB_V1)
    # Untouched between the two runs: run2 takes normalize's hardlink-reuse
    # path for it, so the sweep covers that path too.
    (project / "contents" / "logo.png").write_bytes(b"logo-bytes-unchanged")
    return project


def _make_workspace(tmp_path: Path, project: Path) -> tuple[Workspace, Path]:
    published = tmp_path / "published"
    config = ProjectConfig(
        project_dir=project,
        out_dir=published / "output",
        render_dir=published / "render",
    )
    return Workspace(config, tmp_path / "workspace", resolve_layout(project)), published


def _run_all_stages(
    workspace: Workspace, observers: "_Observers", *, run_label: str
) -> None:
    for factory in STAGE_FACTORIES:
        factory(workspace).run()
        mutated = observers.mutated()
        assert not mutated, (
            f"in-place write into an existing inode detected after"
            f" {run_label}/{factory.__name__}: {[str(p) for p in mutated]}"
        )
        observers.snapshot()


class _Observers:
    def __init__(self, watch_roots: tuple[Path, ...], obs_root: Path) -> None:
        self.watch_roots = watch_roots
        self.obs_root = obs_root
        self._records: list[tuple[Path, Path, str]] = []
        self._round = 0

    def snapshot(self) -> None:
        self._round += 1
        round_dir = self.obs_root / f"{self._round:03d}"
        for i, path in enumerate(self._watched_files()):
            observer = round_dir / str(i)
            observer.parent.mkdir(parents=True, exist_ok=True)
            os.link(path, observer)
            self._records.append((path, observer, _sha256(observer)))

    def mutated(self) -> list[Path]:
        return [
            origin
            for origin, observer, digest in self._records
            if _sha256(observer) != digest
        ]

    def _watched_files(self) -> list[Path]:
        return [
            path
            for root in self.watch_roots
            for path in sorted(root.rglob("*"))
            if path.is_file() and not path.name.endswith(_EXEMPT_SUFFIXES)
        ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
