"""Components package — public API for pipeline."""

from reqs_builder.components.composer.core import compose
from reqs_builder.components.generator.core import generate
from reqs_builder.components.normalizer.core import normalize

__all__ = ["compose", "generate", "normalize"]
