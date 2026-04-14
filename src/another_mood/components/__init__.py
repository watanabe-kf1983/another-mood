"""Components package — public API for pipeline."""

from another_mood.components.composer.composer import compose
from another_mood.components.generator.generator import generate, reconcile
from another_mood.components.preprocess.normalizer import (
    normalize_contents,
    normalize_queries,
)
from another_mood.components.preprocess.schema_inspector import inspect_schema

__all__ = [
    "compose",
    "generate",
    "inspect_schema",
    "normalize_contents",
    "normalize_queries",
    "reconcile",
]
