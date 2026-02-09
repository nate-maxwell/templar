"""
Templar Queries

Contains a query class that returns dataclasses for templates that match given
filters for a resolver.

Additionally, contains various cached query strategies including:
* CachedQuery - Fully cached disk scan
* TwoTierCachedQuery - Cached queries with path and parsed object cache separation
* LazyQuery - Query with lazy evaluation and selective caching based on filters
"""

import time
from pathlib import Path
from typing import Generic
from typing import Iterator
from typing import Optional

from templar._templartypes import ContextT
from templar._template import PathResolver

# -----Base Query--------------------------------------------------------------


class Query(object):
    """
    Query interface for finding paths that match a template.

    Args:
        resolver (PathResolver): The resolver to create dataclasses from.
        root (Path): The base path to check in. The query will recursively scan
            all paths below the root path.
    """

    def __init__(self, resolver: PathResolver, root: Path) -> None:
        self.resolver = resolver
        self.root = root

    def query(self, **filters) -> Iterator[ContextT]:
        """Find paths matching criteria."""
        for path in self.walk_paths():
            ctx = self.resolver.parse_path(path)
            if ctx is not None and self.matches_filters(ctx, filters):
                yield ctx

    @staticmethod
    def matches_filters(ctx: ContextT, filters: dict) -> bool:
        """
        Returns True or False if the given dataclass matches the filters.

        Args:
            ctx (ContextT): The dataclass to check against.
            filters (dict): The fields to required values that the dataclass
                must contain to be considered a match.
        Returns:
            bool: True if passes filters, else False.
        """
        for key, value in filters.items():
            if getattr(ctx, key, None) != value:
                return False
        return True

    def walk_paths(self) -> Iterator[Path]:
        """Recursively walks the root path, yielding each path."""
        for path in self.root.rglob("*"):
            yield path


# -----Cached Queries----------------------------------------------------------


class CachedQuery(Query, Generic[ContextT]):
    """
    Query interface with result caching.

    Caches the full scan results to avoid re-walking the directory tree.
    Cache can be manually invalidated or auto-invalidated after a timeout.

    Args:
        resolver (PathResolver): The resolver to create dataclasses from.
        root (Path): The base path to check in.
        cache_timeout (float): Seconds before cache auto-invalidates. None = never.
    """

    def __init__(
        self,
        resolver: PathResolver,
        root: Path,
        cache_timeout: Optional[float] = None,
    ) -> None:
        super().__init__(resolver, root)
        self.cache_timeout = cache_timeout

        self._cache: Optional[list[ContextT]] = None
        self._cache_timestamp: Optional[float] = None

    def query(self, **filters) -> Iterator[ContextT]:
        """Find paths matching criteria using cached results."""
        contexts = self._get_cached_contexts()

        for ctx in contexts:
            if self.matches_filters(ctx, filters):
                yield ctx

    def invalidate_cache(self) -> None:
        """Manually invalidate the cache."""
        self._cache = None
        self._cache_timestamp = None

    def _get_cached_contexts(self) -> list[ContextT]:
        """Get all contexts, using cache if valid."""
        if self._is_cache_valid():
            return self._cache

        # Cache miss - scan and parse
        contexts = []
        for path in self.walk_paths():
            rel_path = path.relative_to(self.root)
            ctx = self.resolver.parse_path(rel_path)
            if ctx is not None:
                contexts.append(ctx)

        self._cache = contexts
        self._cache_timestamp = time.time()
        return contexts

    def _is_cache_valid(self) -> bool:
        """Check if cache exists and hasn't expired."""
        if self._cache is None:
            return False

        if self.cache_timeout is None:
            return True

        elapsed = time.time() - self._cache_timestamp
        return elapsed < self.cache_timeout


class TwoTierCachedQuery(Query, Generic[ContextT]):
    """
    Query with separate caches for path scanning and parsing.

    This is more memory efficient - it caches the path list separately
    from parsed contexts, so you can invalidate parsing cache without
    re-scanning the filesystem.

    Args:
        resolver (PathResolver): The resolver to create dataclasses from.
        root (Path): The base path to check in.
        path_cache_timeout (float): Seconds before path cache expires.
        parse_cache_timeout (float): Seconds before parse cache expires.
    """

    def __init__(
        self,
        resolver: PathResolver,
        root: Path,
        path_cache_timeout: Optional[float] = None,
        parse_cache_timeout: Optional[float] = None,
    ) -> None:
        super().__init__(resolver, root)
        self.path_cache_timeout = path_cache_timeout
        self.parse_cache_timeout = parse_cache_timeout

        # Path Cache
        self._path_cache: Optional[list[Path]] = None
        self._path_cache_timestamp: Optional[float] = None

        # Context Cache
        self._parse_cache: dict[Path, Optional[ContextT]] = {}
        self._parse_cache_timestamp: Optional[float] = None

    def query(self, **filters) -> Iterator[ContextT]:
        """Find paths matching criteria using two-tier cache."""
        paths = self._get_cached_paths()

        for path in paths:
            ctx = self._get_cached_parse(path)
            if ctx is not None and self.matches_filters(ctx, filters):
                yield ctx

    def invalidate_path_cache(self) -> None:
        """Invalidate only the path scanning cache."""
        self._path_cache = None
        self._path_cache_timestamp = None

    def invalidate_parse_cache(self) -> None:
        """Invalidate only the parse cache."""
        self._parse_cache.clear()
        self._parse_cache_timestamp = None

    def invalidate_all(self) -> None:
        """Invalidate both caches."""
        self.invalidate_path_cache()
        self.invalidate_parse_cache()

    def _get_cached_paths(self) -> list[Path]:
        """Get all paths, using cache if valid."""
        if self._is_path_cache_valid():
            return self._path_cache

        # Cache miss - scan filesystem
        paths = list(self.walk_paths())
        self._path_cache = paths
        self._path_cache_timestamp = time.time()
        return paths

    def _get_cached_parse(self, path: Path) -> Optional[ContextT]:
        """Parse a path, using cache if valid."""
        if not self._is_parse_cache_valid():
            self._parse_cache.clear()
            self._parse_cache_timestamp = time.time()

        if path not in self._parse_cache:
            rel_path = path.relative_to(self.root)
            self._parse_cache[path] = self.resolver.parse_path(rel_path)

        return self._parse_cache[path]

    def _is_path_cache_valid(self) -> bool:
        """Check if path cache exists and hasn't expired."""
        if self._path_cache is None:
            return False

        if self.path_cache_timeout is None:
            return True

        elapsed = time.time() - self._path_cache_timestamp
        return elapsed < self.path_cache_timeout

    def _is_parse_cache_valid(self) -> bool:
        """Check if parse cache hasn't expired."""
        if self._parse_cache_timestamp is None:
            return False

        if self.parse_cache_timeout is None:
            return True

        elapsed = time.time() - self._parse_cache_timestamp
        return elapsed < self.parse_cache_timeout


class LazyQuery(Query, Generic[ContextT]):
    """
    Query with lazy evaluation and selective caching.

    Only caches results that have been queried, not the entire tree.
    Good for when you're making targeted queries rather than full scans.

    Args:
        resolver (PathResolver): The resolver to create dataclasses from.
        root (Path): The base path to check in.
    """

    def __init__(self, resolver: PathResolver, root: Path) -> None:
        super().__init__(resolver, root)

        # Cache only stores results that have been queried
        # Key is frozenset of filter items
        self._cache: dict[frozenset, list[ContextT]] = {}

    def query(self, **filters) -> Iterator[ContextT]:
        """Find paths matching criteria with lazy caching."""
        cache_key = frozenset(filters.items())

        if cache_key in self._cache:
            # Cache hit - return stored results
            for ctx in self._cache[cache_key]:
                yield ctx
        else:
            # Cache miss - scan and cache results
            results = []
            for path in self.walk_paths():
                rel_path = path.relative_to(self.root)
                ctx = self.resolver.parse_path(rel_path)
                if ctx is not None and self.matches_filters(ctx, filters):
                    results.append(ctx)
                    yield ctx

            self._cache[cache_key] = results

    def invalidate_cache(self, **filters) -> None:
        """Invalidate cache for specific filter combination."""
        cache_key = frozenset(filters.items())
        self._cache.pop(cache_key, None)

    def invalidate_all(self) -> None:
        """Invalidate entire cache."""
        self._cache.clear()
