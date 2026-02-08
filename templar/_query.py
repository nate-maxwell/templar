from pathlib import Path
from typing import Iterator

from templar._templartypes import ContextT
from templar._template import PathResolver


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
        for path in self._walk_paths():
            ctx = self.resolver.parse_path(path)
            if ctx is not None and self._matches_filters(ctx, filters):
                yield ctx

    @staticmethod
    def _matches_filters(ctx: ContextT, filters: dict) -> bool:
        for key, value in filters.items():
            if getattr(ctx, key, None) != value:
                return False
        return True

    def _walk_paths(self) -> Iterator[Path]:
        for path in self.root.rglob("*"):
            yield path
