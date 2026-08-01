"""Tests for Tap — merge a stage's output into one namespace document."""

import json
from pathlib import Path

from another_mood.components.tap.tap import TAP_DOCUMENT_NAME, tap


class TestTap:
    def test_merges_the_data_dir_into_one_document(self, tmp_path: Path) -> None:
        data = tmp_path / "upstream" / "data"
        data.mkdir(parents=True)
        (data / "a.json").write_text('{"items": [1]}', encoding="utf-8")
        (data / "b.json").write_text('{"items": [2], "names": []}', encoding="utf-8")

        out = tmp_path / "tap"
        tap(data_dir=tmp_path / "upstream", out_dir=out)

        document = json.loads(
            (out / "data" / TAP_DOCUMENT_NAME).read_text(encoding="utf-8")
        )
        assert document == {"items": [1, 2], "names": []}
