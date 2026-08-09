"""The sbdb generations this tool accepts.

A module of its own so that a diff here *is* the signal that the supported
set moved — readable at the file boundary, with no need to parse the value.
Keep nothing else in this file: anything that changes for other reasons
would make the signal fire spuriously.
"""

SUPPORTED_SBDB_VERSIONS = frozenset({1})
