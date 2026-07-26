"""Tests for the inert value model — the marshal boundary."""

import pytest

from another_mood.components.generator.inert import ensure_inert


class TestEnsureInert:
    """The single ``Any`` boundary: only exact inert scalars pass; a foreign
    leaf raises rather than reach a template unaudited."""

    def test_foreign_leaf_type_raises(self) -> None:
        with pytest.raises(TypeError):
            ensure_inert({"x": object()})

    def test_foreign_leaf_in_anchorless_subtree_raises(self) -> None:
        with pytest.raises(TypeError):
            ensure_inert({"items": [{"text": object()}]})
