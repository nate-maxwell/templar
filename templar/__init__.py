"""
Templar - Type-safe path templating for production pipelines.

This module provides a lightweight templating system for building and parsing
file paths using strongly-typed dataclass contexts. Define path templates with
token placeholders, then generate paths from context values or parse existing
paths back into structured data.
"""

from templar._query import Query
from templar._query import CachedQuery
from templar._query import TwoTierCachedQuery
from templar._query import LazyQuery
from templar._templartypes import ContextT
from templar._resolvers import CompositeResolver
from templar._resolvers import PathResolver
from templar._path_template import PathTemplate
