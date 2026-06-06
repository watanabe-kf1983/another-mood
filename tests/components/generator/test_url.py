from another_mood.components.generator.url import url_escape


class TestUrlEscape:
    def test_leaves_ascii_unreserved_raw(self) -> None:
        assert url_escape("AZaz09-._~") == "AZaz09-._~"

    def test_percent_encodes_space(self) -> None:
        assert url_escape("a b") == "a%20b"

    def test_percent_encodes_reserved_ascii(self) -> None:
        assert url_escape("a/b#c?d") == "a%2Fb%23c%3Fd"

    def test_safe_keeps_named_ascii_raw(self) -> None:
        assert url_escape("a/b", safe="/") == "a/b"

    def test_keeps_ucschar_raw(self) -> None:
        assert url_escape("書籍") == "書籍"

    def test_keeps_non_ascii_punctuation_raw(self) -> None:
        # `。` (U+3002) and `、` (U+3001) are ucschar — real ids carry them.
        assert url_escape("モーニング娘。") == "モーニング娘。"
        assert url_escape("藤岡弘、") == "藤岡弘、"

    def test_keeps_astral_cjk_raw(self) -> None:
        # CJK Extension chars live in the astral planes, which RFC 3987
        # ucschar includes (10000–2FFFD): they pass through raw, not escaped.
        assert url_escape("𠮷野家") == "𠮷野家"  # 𠮷 = U+20BB7
        assert url_escape("𩸽") == "𩸽"  # U+29E3D

    def test_keeps_emoji_raw(self) -> None:
        # Emoji are ucschar too (U+1F600 ∈ 10000–1FFFD) — kept raw.
        assert url_escape("😀") == "😀"

    def test_percent_encodes_non_ucschar_non_ascii(self) -> None:
        # U+FFFF is a noncharacter — outside ucschar, so it is encoded.
        assert url_escape("￿") == "%EF%BF%BF"

    def test_encodes_percent_itself(self) -> None:
        assert url_escape("100%") == "100%25"

    def test_empty_string(self) -> None:
        assert url_escape("") == ""
