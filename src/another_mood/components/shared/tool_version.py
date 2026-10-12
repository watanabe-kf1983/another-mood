"""The running another-mood's own identity: the id it answers to, and its
version and home page read from installed metadata."""

from importlib import metadata

# Must match `project.name` in pyproject.toml. Nothing in Python enforces that
# agreement -- the packaging metadata is the other side of a boundary the type
# checker cannot see -- so this constant only narrows where it can drift, and
# the test module pins it to the distribution that actually provides this
# package.
DISTRIBUTION_NAME = "another-mood"

# This processor's id in sbdb vocabulary: the `tools.` key a manifest addresses
# it by.  Matches DISTRIBUTION_NAME by coincidence, not by rule.
PROCESSOR_ID = "another-mood"


def tool_version() -> str:
    """Return the running another-mood's version as a PEP 440 string.

    Every surface that names a version -- ``mood --version``, the MCP server's
    serverInfo, the manifest's ``minimum_version`` gate -- reports this one
    value, so a version the gate rejects is the version ``--version`` shows.
    """
    return metadata.version(DISTRIBUTION_NAME)


def tool_homepage() -> str:
    """Return the project's home page URL, read from installed metadata.

    pyproject.toml's ``Homepage`` stays the one place the URL is written;
    every surface that points a reader at the project links this value.
    """
    entries = metadata.metadata(DISTRIBUTION_NAME).get_all("Project-URL") or []
    labelled = (entry.split(", ", 1) for entry in entries)
    return next(url for label, url in labelled if label == "Homepage")
