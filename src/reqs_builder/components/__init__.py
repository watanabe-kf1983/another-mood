"""Components package — public API for pipeline."""

from reqs_builder.components.composer.composer import compose
from reqs_builder.components.generator.generator import generate, reconcile
from reqs_builder.components.preprocess.normalizer import (
    normalize_contents,
    normalize_queries,
)
from reqs_builder.components.preprocess.schema_inspector import inspect_schema

__all__ = [
    "compose",
    "generate",
    "inspect_schema",
    "normalize_contents",
    "normalize_queries",
    "reconcile",
]
