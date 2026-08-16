"""Build info — one invocation's facts, flattened for templates to query by key."""

from collections.abc import Mapping

type BuildInfo = Mapping[str, str]
