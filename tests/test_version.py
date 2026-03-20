from reqs_builder.version import VERSION


def test_version_is_string() -> None:
    assert isinstance(VERSION, str)
