"""
Templar - Type-safe path templating for production pipelines.

This module provides a lightweight templating system for building and parsing
file paths using strongly-typed dataclass contexts. Define path templates with
token placeholders, then generate paths from context values or parse existing
paths back into structured data.

Core Components:
    PathTemplate: Represents a single path pattern with token placeholders
    PathResolver: Manages multiple templates and resolves them from context

Example:
    >>> from dataclasses import dataclass
    >>> from typing import Optional
    >>> from pathlib import Path
    >>>
    >>> @dataclass
    >>> class VFXContext:
    ...     show: Optional[str] = None
    ...     seq: Optional[str] = None
    ...     shot: Optional[str] = None
    ...     dcc: Optional[str] = None
    ...
    >>> resolver = PathResolver(VFXContext)
    >>> resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>/__pub__/<dcc>")
    >>>
    >>> ctx = VFXContext(show="demo", seq="DEF", shot="0010", dcc="maya")
    >>> path = resolver.resolve("shot", ctx)
    >>> print(path)
    V:/shows/demo/seq/DEF/0010/__pub__/maya
    >>>
    >>> parsed = resolver.parse_path(path)
    >>> print(parsed.show, parsed.seq)
    demo DEF

Typical Usage:
    1. Define a dataclass with Optional[str] fields for your path components
    2. Create a PathResolver with your dataclass
    3. Register path templates using <token> syntax
    4. Build paths with resolve() or parse paths with parse_path()

The system automatically handles:
    - Optional tokens (templates match based on available context fields)
    - File name/extension extraction (file_name and file_type fields)
    - Cross-platform path separators
    - Round-trip conversion (path -> context -> path)
"""

from templar._query import Query
from templar._query import CachedQuery
from templar._query import TwoTierCachedQuery
from templar._query import LazyQuery
from templar._templartypes import ContextT
from templar._resolvers import CompositeResolver
from templar._resolvers import PathResolver
from templar._path_template import PathTemplate
