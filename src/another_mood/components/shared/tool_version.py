"""The running another-mood's own version, read from installed metadata."""

from importlib import metadata

# Must match `project.name` in pyproject.toml. Nothing in Python enforces that
# agreement -- the packaging metadata is the other side of a boundary the type
# checker cannot see -- so this constant only narrows where it can drift, and
# the test module pins it to the distribution that actually provides this
# package.
DISTRIBUTION_NAME = "another-mood"


def tool_version() -> str:
    """Return the running another-mood's version as a PEP 440 string.

    Every surface that names a version -- ``mood --version``, the MCP server's
    serverInfo, the manifest's ``minimum_version`` gate -- reports this one
    value, so a version the gate rejects is the version ``--version`` shows.
    """
    return metadata.version(DISTRIBUTION_NAME)
