"""Composer package — combine normalized data into views."""

from reqs_builder.composer.core import compose, parse_query
from reqs_builder.composer.json_data_model import deep_merge, load_yamls
from reqs_builder.composer.query import From, Grouped, Query, Select, SelectItem

__all__ = [
    "compose",
    "parse_query",
    "deep_merge",
    "load_yamls",
    "From",
    "Grouped",
    "Query",
    "Select",
    "SelectItem",
]
