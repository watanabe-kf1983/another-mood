"""Components package — public API for pipeline."""

from reqs_builder.components.composer.composer import compose
from reqs_builder.components.generator.generator import generate
from reqs_builder.components.normalizer.normalizer import normalize

__all__ = ["compose", "generate", "normalize"]
