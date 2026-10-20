"""The tap pipeline's documented contract: rendering stages never run,
so the data layer stays extractable while templates are broken; and the
document always validates against the schema handed back with it."""

import json
from pathlib import Path

import jsonschema
import pytest

from another_mood import command
from another_mood.components.manifest import Manifest
from another_mood.config import ProjectConfig
from another_mood.layout import resolve_layout
from another_mood.pipeline.stages import tap_pipeline
from another_mood.pipeline.workspace import Workspace, make_processor_info

REPO = Path(__file__).resolve().parents[2]
PROJECTS = sorted(p.parent for p in REPO.glob("showcase/*/sbdb.yaml")) + [
    REPO / "dev-docs"
]


def test_broken_templates_do_not_fail_the_tap_pipeline(tmp_path: Path) -> None:
    project = tmp_path / "project"
    command.init(project)
    for template in (project / "definition" / "templates").rglob("*"):
        if template.is_file():
            template.write_text("{% broken", encoding="utf-8")
    config = ProjectConfig(namespace_root=tmp_path, project_dir=project)
    workspace = Workspace(
        config,
        tmp_path / "work",
        resolve_layout(project),
        Manifest(sbdb_version=1),
        make_processor_info("tap"),
    )

    report = tap_pipeline(workspace).run()

    assert not report.has_errors()


@pytest.mark.parametrize(
    "project", PROJECTS, ids=lambda p: p.relative_to(REPO).as_posix()
)
def test_document_validates_against_its_schema(project: Path) -> None:
    config = ProjectConfig(namespace_root=REPO, project_dir=project)
    document = command.tap(config).document
    schema = command.tap(config, schema=True).document

    assert document is not None and schema is not None
    validator = jsonschema.Draft202012Validator(json.loads(schema))
    # jsonschema's stubs leave iter_errors partially typed, as in validator.py.
    errors = [
        e.message
        for e in validator.iter_errors(json.loads(document))  # type: ignore[reportUnknownMemberType]
    ]
    assert errors == []
