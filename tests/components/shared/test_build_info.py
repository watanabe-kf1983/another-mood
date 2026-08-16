"""Tests for build_info — projecting a run's facts onto dotted keys."""

from pathlib import Path

from another_mood.components.shared.build_info import flatten_build_info


def test_flatten_build_info_prefixes_every_name() -> None:
    assert dict(flatten_build_info("processor.config", {"host": "127.0.0.1"})) == {
        "processor.config.host": "127.0.0.1"
    }


def test_flatten_build_info_stringifies_non_string_values() -> None:
    values = {"port": 5077, "project_dir": Path("/srv/catalog")}

    assert dict(flatten_build_info("processor.config", values)) == {
        "processor.config.port": "5077",
        "processor.config.project_dir": "/srv/catalog",
    }


def test_flatten_build_info_renders_booleans_in_yaml_spelling() -> None:
    values = {"temporary": True, "pinned": False}

    assert dict(flatten_build_info("processor.workspace", values)) == {
        "processor.workspace.temporary": "true",
        "processor.workspace.pinned": "false",
    }


def test_flatten_build_info_drops_unset_values() -> None:
    # An absent key lets `build_info(key, default)` answer with its default,
    # which a "None" string would shadow.
    assert dict(flatten_build_info("processor.config", {"site_dir": None})) == {}
