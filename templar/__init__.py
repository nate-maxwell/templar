"""
Templar - Type-safe path templating for production pipelines.

This module provides a lightweight templating system for building and parsing
file paths using strongly-typed dataclass contexts. Define path templates with
token placeholders, then generate paths from context values or parse existing
paths back into structured data.
"""

from templar.query import Query
from templar.query import CachedQuery
from templar.query import TwoTierCachedQuery
from templar.query import LazyQuery
from templar.templartypes import ContextT
from templar.resolvers import CompositeResolver
from templar.resolvers import PathResolver
from templar.path_template import PathTemplate
