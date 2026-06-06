"""URL / link-target escaping shared by anchor_path construction and `as_url`.

See design/generator/anchor-spec.md#escape-規則 for the policy of record.
"""

from urllib.parse import quote

# RFC 3987 ``ucschar``: the non-ASCII code points an IRI may carry raw.
# The gaps exclude surrogates, noncharacters, and private-use areas.
_UCSCHAR_RANGES: tuple[tuple[int, int], ...] = (
    (0xA0, 0xD7FF),
    (0xF900, 0xFDCF),
    (0xFDF0, 0xFFEF),
    (0x10000, 0x1FFFD),
    (0x20000, 0x2FFFD),
    (0x30000, 0x3FFFD),
    (0x40000, 0x4FFFD),
    (0x50000, 0x5FFFD),
    (0x60000, 0x6FFFD),
    (0x70000, 0x7FFFD),
    (0x80000, 0x8FFFD),
    (0x90000, 0x9FFFD),
    (0xA0000, 0xAFFFD),
    (0xB0000, 0xBFFFD),
    (0xC0000, 0xCFFFD),
    (0xD0000, 0xDFFFD),
    (0xE1000, 0xEFFFD),
)


def url_escape(value: str, safe: str = "") -> str:
    """Percent-encode ``value`` to IRI form: URL-unsafe ASCII is encoded
    (via ``urllib.parse.quote``), RFC 3987 ``ucschar`` is kept raw.

    ``safe`` lists extra ASCII to leave unencoded (forwarded to ``quote``).
    Applied once to a raw value, so a literal ``%`` becomes ``%25``.
    """
    return "".join(c if _is_ucschar(c) else quote(c, safe=safe) for c in value)


def _is_ucschar(c: str) -> bool:
    cp = ord(c)
    return any(lo <= cp <= hi for lo, hi in _UCSCHAR_RANGES)
