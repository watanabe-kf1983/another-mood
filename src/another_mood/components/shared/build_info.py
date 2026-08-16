"""Build info — one invocation's facts, flattened for templates to query by key."""

from collections.abc import Mapping
from types import MappingProxyType

type BuildInfo = Mapping[str, str]

NO_BUILD_INFO: BuildInfo = MappingProxyType({})
"""What a caller with no store to supply passes."""
