"""Tests for source_loader — parse_yaml, UserStr/Location."""

import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import pytest

from another_mood.components.shared.user_source.source_loader import (
    Location,
    UserStr,
    load_blob,
    load_prose,
    load_source,
    parse_yaml,
)
from another_mood.components.shared.user_source.position_resolver import (
    Position,
    resolve_position,
)
from another_mood.components.shared.user_source.diagnostic import FileValidationError


# ── parse_yaml ─────────────────────────────────────────────────────


class TestParseYaml:
    """parse_yaml: YAML parsing with source position preservation."""

    def test_valid_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "ok.yaml"
        f.write_text("key: value\n")
        result = parse_yaml(f)
        assert result["key"] == "value"

    def test_empty_file_returns_empty_mapping(self, tmp_path: Path) -> None:
        # ruamel returns None for empty input; parse_yaml normalises that
        # to {} so callers can keep using the documented Mapping shape.
        f = tmp_path / "empty.yaml"
        f.write_text("")
        assert parse_yaml(f) == {}

    def test_whitespace_only_file_returns_empty_mapping(self, tmp_path: Path) -> None:
        f = tmp_path / "ws.yaml"
        f.write_text("\n  \n")
        assert parse_yaml(f) == {}

    @pytest.mark.parametrize(
        ("source", "expected_type"),
        [
            ("- a\n- b\n", "CommentedSeq"),
            ("42\n", "int"),
            ('"just a string"\n', "str"),
            ("true\n", "bool"),
        ],
    )
    def test_non_mapping_root_rejected(
        self, source: str, expected_type: str, tmp_path: Path
    ) -> None:
        f = tmp_path / "non_mapping.yaml"
        f.write_text(source)
        with pytest.raises(FileValidationError) as exc_info:
            parse_yaml(f)
        diag = exc_info.value.diagnostics[0]
        assert diag.file == f
        assert "Expected a YAML mapping" in diag.message
        assert expected_type in diag.message

    def test_broken_yaml_raises_diagnostic(self, tmp_path: Path) -> None:
        f = tmp_path / "broken.yaml"
        f.write_text("a: [unterminated\n")
        with pytest.raises(FileValidationError) as exc_info:
            parse_yaml(f)
        diag = exc_info.value.diagnostics[0]
        assert diag.file == f
        assert diag.source == "ruamel.yaml"

    def test_scalar_strings_become_user_str_with_location(self, tmp_path: Path) -> None:
        f = tmp_path / "tagged.yaml"
        f.write_text(
            "top:\n"  # line 1
            "  name: alice\n"  # line 2, value column 9
            "  tags:\n"  # line 3
            "    - red\n"  # line 4, value column 7
        )
        result = parse_yaml(f)
        name = result["top"]["name"]  # type: ignore[index]
        tag = result["top"]["tags"][0]  # type: ignore[index]
        assert isinstance(name, UserStr)
        assert name.location == Location(file=f, line=2, column=9)
        assert isinstance(tag, UserStr)
        assert tag.location == Location(file=f, line=4, column=7)

    def test_mapping_keys_become_user_str_with_location(self, tmp_path: Path) -> None:
        f = tmp_path / "keys.yaml"
        f.write_text(
            "top:\n"  # line 1, key column 1
            "  name: alice\n"  # line 2, key column 3
        )
        result = parse_yaml(f)
        (top,) = result.keys()
        (name,) = result["top"].keys()  # type: ignore[union-attr]
        assert isinstance(top, UserStr)
        assert top.location == Location(file=f, line=1, column=1)
        assert isinstance(name, UserStr)
        assert name.location == Location(file=f, line=2, column=3)

    def test_non_string_scalars_left_untouched(self, tmp_path: Path) -> None:
        f = tmp_path / "untouched.yaml"
        f.write_text("count: 3\nflag: true\n")
        result = parse_yaml(f)
        assert result["count"] == 3
        assert result["flag"] is True

    def test_key_tagging_preserves_lc_for_position_resolution(
        self, tmp_path: Path
    ) -> None:
        """Tagging keys must leave ruamel's ``.lc`` intact so schema-validation
        position resolution keeps working — including the root node's own
        position (which anchors errors about the document root) and non-string
        scalars, whose positions cannot ride on a ``UserStr``."""
        f = tmp_path / "positions.yaml"
        f.write_text("count: 3\nnested:\n  flag: true\n")
        result = parse_yaml(f)
        assert resolve_position([], result) == Position(line=1, column=1)
        assert resolve_position(["count"], result) == Position(line=1, column=8)
        assert resolve_position(["nested", "flag"], result) == Position(
            line=3, column=9
        )


# ── NFC normalization at the input boundary (D10) ──────────────────


class TestNfcNormalization:
    """All text is folded to NFC at the two decode/traversal boundaries,
    so an id differing only in normalization form can't silently collapse
    onto the same output file on a form-insensitive filesystem (macOS)."""

    def test_yaml_value_normalized_to_nfc(self, tmp_path: Path) -> None:
        nfd = unicodedata.normalize("NFD", "café")
        assert nfd != "café"  # sanity: the written value really is decomposed
        f = tmp_path / "value.yaml"
        f.write_text(f"id: {nfd}\n", encoding="utf-8")
        value = parse_yaml(f)["id"]
        assert value == "café"
        assert unicodedata.is_normalized("NFC", cast(str, value))

    def test_yaml_key_normalized_to_nfc(self, tmp_path: Path) -> None:
        nfd = unicodedata.normalize("NFD", "café")
        f = tmp_path / "key.yaml"
        f.write_text(f"{nfd}: value\n", encoding="utf-8")
        (key,) = parse_yaml(f).keys()
        assert key == "café"
        assert unicodedata.is_normalized("NFC", key)

    def test_prose_id_from_filename_normalized_to_nfc(self, tmp_path: Path) -> None:
        # The filename is the id source and never passes through the
        # decoder, so it needs its own normalization step.
        nfd_stem = unicodedata.normalize("NFD", "café")
        f = tmp_path / f"{nfd_stem}.md"
        f.write_text("# Title\n", encoding="utf-8")
        record = cast(
            Sequence[Mapping[str, object]],
            load_prose(f, tmp_path, mime_type="text/markdown")["prose"],
        )[0]
        assert record["id"] == "café"
        assert unicodedata.is_normalized("NFC", cast(str, record["id"]))

    def test_prose_content_normalized_to_nfc(self, tmp_path: Path) -> None:
        nfd_body = unicodedata.normalize("NFD", "# Café\n")
        f = tmp_path / "doc.md"
        f.write_text(nfd_body, encoding="utf-8")
        record = cast(
            Sequence[Mapping[str, object]],
            load_prose(f, tmp_path, mime_type="text/markdown")["prose"],
        )[0]
        content = cast(Mapping[str, object], record["body"])["content"]
        assert content == "# Café\n"
        assert unicodedata.is_normalized("NFC", cast(str, content))

    def test_blob_id_from_filename_normalized_to_nfc(self, tmp_path: Path) -> None:
        # Like a prose id, a blob id is a traversed filename that never
        # passes through the decoder, so it is folded separately.
        nfd_stem = unicodedata.normalize("NFD", "café")
        f = tmp_path / f"{nfd_stem}.png"
        f.write_bytes(b"\x89PNG")
        record = _blob_record(load_blob(f, tmp_path))
        assert record["id"] == "café.png"
        assert unicodedata.is_normalized("NFC", cast(str, record["id"]))


# ── Blob ───────────────────────────────────────────────────────────


def _blob_record(data: Mapping[str, object]) -> Mapping[str, object]:
    return cast(Sequence[Mapping[str, object]], data["blob"])[0]


class TestLoadBlob:
    """load_blob: wrap an opaque contents file into a blob record."""

    def test_record_shape_keeps_extension_and_no_bytes(self, tmp_path: Path) -> None:
        f = tmp_path / "figs" / "diagram.png"
        f.parent.mkdir()
        f.write_bytes(b"\x89PNG\r\n")
        assert _blob_record(load_blob(f, tmp_path)) == {
            "id": "figs/diagram.png",
            "mime_type": "image/png",
        }

    def test_unknown_extension_falls_back_to_octet_stream(self, tmp_path: Path) -> None:
        f = tmp_path / "sample.unknownext"
        f.write_bytes(b"\x00\x01")
        assert (
            _blob_record(load_blob(f, tmp_path))["mime_type"]
            == "application/octet-stream"
        )

    def test_mime_type_ignores_os_mime_registry(self, tmp_path: Path) -> None:
        # ``.xlsx`` is absent from Python's frozen table but present in most
        # OS mime sources (/etc/mime.types, the Windows registry). Resolving
        # it to the opaque default pins that derivation consults only the
        # builtin table, so a blob's mime_type stays identical across
        # machines (the module-level mimetypes.guess_type would not).
        f = tmp_path / "report.xlsx"
        f.write_bytes(b"PK\x03\x04")
        assert (
            _blob_record(load_blob(f, tmp_path))["mime_type"]
            == "application/octet-stream"
        )


class TestLoadSourceBlobDispatch:
    """load_source: non-YAML/Markdown files become blobs; hidden ones are skipped."""

    def test_non_yaml_markdown_becomes_blob(self, tmp_path: Path) -> None:
        f = tmp_path / "data.csv"
        f.write_text("a,b\n1,2\n")
        data = load_source(f, tmp_path)
        assert data is not None
        assert _blob_record(data) == {
            "id": "data.csv",
            "mime_type": "text/csv",
        }

    @pytest.mark.parametrize("rel", [".DS_Store", ".hidden/photo.png", ".gitkeep"])
    def test_dotfile_and_dotdir_excluded(self, tmp_path: Path, rel: str) -> None:
        # The one skip that survives: a dotfile is cruft in any source tree,
        # so it must not reach validation (a .gitkeep lives in queries_dir).
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")
        assert load_source(f, tmp_path) is None

    def test_yaml_and_markdown_still_parsed(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "d.yaml"
        yaml_file.write_text("k: v\n")
        md_file = tmp_path / "d.md"
        md_file.write_text("# Title\n")
        assert load_source(yaml_file, tmp_path) == {"k": "v"}
        assert "prose" in cast(Mapping[str, object], load_source(md_file, tmp_path))


# ── UserStr / Location ─────────────────────────────────────────────


def test_user_str_carries_location_and_behaves_as_str() -> None:
    loc = Location(file=Path("foo.yaml"), line=3, column=7)
    s = UserStr("hello", loc)
    assert s == "hello"
    assert s.location is loc
