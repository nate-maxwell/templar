"""
Focused unit tests for TwoTierCachedQuery - covers core functionality concisely.

NOTE: TwoTierCachedQuery._get_cached_parse() must make paths relative to root:

    def _get_cached_parse(self, path: Path) -> Optional[ContextT]:
        if not self._is_parse_cache_valid():
            self._parse_cache.clear()
            self._parse_cache_timestamp = time.time()

        if path not in self._parse_cache:
            rel_path = path.relative_to(self.root)  # FIX: Make relative
            self._parse_cache[path] = self.resolver.parse_path(rel_path)

        return self._parse_cache[path]
"""

import time
import pytest
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from templar import PathResolver
from templar._query import TwoTierCachedQuery


@dataclass
class VFXContext(object):
    show: Optional[str] = None
    seq: Optional[str] = None
    shot: Optional[str] = None


@pytest.fixture
def test_structure(tmp_path):
    """Create test directory structure and return root path."""
    # Create: shows/{demo,other}/seq/{ABC,DEF}/{0010,0020}
    for show in ["demo", "other"]:
        for seq in ["ABC", "DEF"]:
            for shot in ["0010", "0020"]:
                path = tmp_path / "shows" / show / "seq" / seq / shot
                path.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def resolver():
    """Create PathResolver with test template."""
    resolver = PathResolver(VFXContext)
    resolver.register("shot", "shows/<show>/seq/<seq>/<shot>")
    return resolver


@pytest.fixture
def query(resolver, test_structure):
    """Create TwoTierCachedQuery instance."""
    return TwoTierCachedQuery(resolver, test_structure)


def test_caches_paths_and_parses_on_first_query(query):
    """First query should populate both caches."""
    assert query._path_cache is None
    assert len(query._parse_cache) == 0

    list(query.query())

    assert query._path_cache is not None
    assert len(query._path_cache) > 0  # Contains all directories found
    assert len(query._parse_cache) == len(query._path_cache)  # Parses all paths

    # Only 8 should actually match the template
    valid_contexts = [ctx for ctx in query._parse_cache.values() if ctx is not None]
    assert len(valid_contexts) == 8  # 2 shows * 2 seqs * 2 shots


def test_second_query_uses_both_caches(query):
    """Second query should reuse both cached results."""
    list(query.query())
    path_timestamp_1 = query._path_cache_timestamp
    parse_timestamp_1 = query._parse_cache_timestamp

    time.sleep(0.01)
    list(query.query())
    path_timestamp_2 = query._path_cache_timestamp
    parse_timestamp_2 = query._parse_cache_timestamp

    assert path_timestamp_1 == path_timestamp_2, "Path cache timestamp changed"
    assert parse_timestamp_1 == parse_timestamp_2, "Parse cache timestamp changed"


def test_filters_applied_to_cached_results(query):
    """Filters should work correctly with two-tier cache."""
    results_demo = list(query.query(show="demo"))
    assert len(results_demo) == 4

    results_abc = list(query.query(seq="ABC"))
    assert len(results_abc) == 4

    results_specific = list(query.query(show="demo", seq="ABC", shot="0010"))
    assert len(results_specific) == 1


def test_path_cache_timeout_expires(resolver, test_structure):
    """Path cache should expire after timeout period."""
    query = TwoTierCachedQuery(resolver, test_structure, path_cache_timeout=0.05)

    list(query.query())
    timestamp_1 = query._path_cache_timestamp

    time.sleep(0.1)  # Wait for expiration

    list(query.query())
    timestamp_2 = query._path_cache_timestamp

    assert timestamp_1 != timestamp_2, "Path cache did not expire"


def test_parse_cache_timeout_expires(resolver, test_structure):
    """Parse cache should expire after timeout period."""
    query = TwoTierCachedQuery(resolver, test_structure, parse_cache_timeout=0.05)

    list(query.query())
    timestamp_1 = query._parse_cache_timestamp

    time.sleep(0.1)  # Wait for expiration

    list(query.query())
    timestamp_2 = query._parse_cache_timestamp

    assert timestamp_1 != timestamp_2, "Parse cache did not expire"


def test_different_timeout_values(resolver, test_structure):
    """Path and parse caches can have different timeout values."""
    query = TwoTierCachedQuery(
        resolver, test_structure, path_cache_timeout=0.2, parse_cache_timeout=0.05
    )

    list(query.query())
    path_timestamp_1 = query._path_cache_timestamp
    parse_timestamp_1 = query._parse_cache_timestamp

    time.sleep(0.1)  # Parse expires, path doesn't

    list(query.query())
    path_timestamp_2 = query._path_cache_timestamp
    parse_timestamp_2 = query._parse_cache_timestamp

    # Path cache should not have changed (still valid)
    assert path_timestamp_1 == path_timestamp_2, "Path cache expired too early"
    # Parse cache should have changed (expired)
    assert parse_timestamp_1 != parse_timestamp_2, "Parse cache did not expire"


def test_invalidate_path_cache_only(query):
    """invalidate_path_cache() should clear only path cache."""
    list(query.query())
    assert query._path_cache is not None
    assert len(query._parse_cache) > 0

    query.invalidate_path_cache()

    assert query._path_cache is None
    assert query._path_cache_timestamp is None
    assert len(query._parse_cache) > 0  # Parse cache unchanged


def test_invalidate_parse_cache_only(query):
    """invalidate_parse_cache() should clear only parse cache."""
    list(query.query())
    assert query._path_cache is not None
    assert len(query._parse_cache) > 0

    query.invalidate_parse_cache()

    assert query._path_cache is not None  # Path cache unchanged
    assert len(query._parse_cache) == 0
    assert query._parse_cache_timestamp is None


def test_invalidate_all_clears_both_caches(query):
    """invalidate_all() should clear both caches."""
    list(query.query())
    assert query._path_cache is not None
    assert len(query._parse_cache) > 0

    query.invalidate_all()

    assert query._path_cache is None
    assert query._path_cache_timestamp is None
    assert len(query._parse_cache) == 0
    assert query._parse_cache_timestamp is None


def test_path_cache_persists_after_parse_invalidation(query):
    """Path cache should remain valid after parse cache invalidation."""
    list(query.query())
    path_timestamp_1 = query._path_cache_timestamp

    query.invalidate_parse_cache()

    list(query.query())
    path_timestamp_2 = query._path_cache_timestamp

    # Path cache should not have been rescanned
    assert path_timestamp_1 == path_timestamp_2


def test_parse_cache_repopulates_after_invalidation(query):
    """Parse cache should repopulate after invalidation without path rescan."""
    list(query.query())
    initial_parse_count = len(query._parse_cache)
    path_timestamp_1 = query._path_cache_timestamp

    query.invalidate_parse_cache()
    assert len(query._parse_cache) == 0

    list(query.query())

    # Parse cache repopulated
    assert len(query._parse_cache) == initial_parse_count
    # Path cache not rescanned
    assert query._path_cache_timestamp == path_timestamp_1


def test_filesystem_changes_visible_after_path_cache_invalidation(
    query, test_structure
):
    """New files visible after path cache invalidation."""
    results_1 = list(query.query(show="demo"))
    assert len(results_1) == 4

    # Add new shot
    new_shot = test_structure / "shows" / "demo" / "seq" / "ABC" / "0030"
    new_shot.mkdir(parents=True, exist_ok=True)

    # Still cached
    results_2 = list(query.query(show="demo"))
    assert len(results_2) == 4, "Cache showed new file before invalidation"

    # Invalidate path cache
    query.invalidate_path_cache()

    # Should see new file
    results_3 = list(query.query(show="demo"))
    assert len(results_3) == 5, "New file not visible after path cache invalidation"


def test_empty_results_cached(query):
    """Empty result sets should be cached in both tiers."""
    results = list(query.query(show="nonexistent"))
    assert len(results) == 0
    assert query._path_cache is not None
    assert len(query._parse_cache) > 0  # Parsed all paths, just no matches


def test_path_cache_none_timeout_never_expires(resolver, test_structure):
    """Path cache with timeout=None should never expire."""
    query = TwoTierCachedQuery(resolver, test_structure, path_cache_timeout=None)

    list(query.query())
    timestamp_1 = query._path_cache_timestamp

    time.sleep(0.1)

    list(query.query())
    timestamp_2 = query._path_cache_timestamp

    assert timestamp_1 == timestamp_2


def test_parse_cache_none_timeout_never_expires(resolver, test_structure):
    """Parse cache with timeout=None should never expire."""
    query = TwoTierCachedQuery(resolver, test_structure, parse_cache_timeout=None)

    list(query.query())
    timestamp_1 = query._parse_cache_timestamp

    time.sleep(0.1)

    list(query.query())
    timestamp_2 = query._parse_cache_timestamp

    assert timestamp_1 == timestamp_2


def test_zero_path_timeout(resolver, tmp_path):
    """Path timeout of 0.0 should expire immediately."""
    query = TwoTierCachedQuery(resolver, tmp_path, path_cache_timeout=0.0)

    shot_path = tmp_path / "shows" / "demo" / "seq" / "ABC" / "0010"
    shot_path.mkdir(parents=True, exist_ok=True)

    list(query.query())

    time.sleep(0.001)
    assert not query._is_path_cache_valid()


def test_zero_parse_timeout(resolver, tmp_path):
    """Parse timeout of 0.0 should expire immediately."""
    query = TwoTierCachedQuery(resolver, tmp_path, parse_cache_timeout=0.0)

    shot_path = tmp_path / "shows" / "demo" / "seq" / "ABC" / "0010"
    shot_path.mkdir(parents=True, exist_ok=True)

    list(query.query())

    time.sleep(0.001)
    assert not query._is_parse_cache_valid()


def test_parse_cache_stores_none_for_nonmatching_paths(resolver, tmp_path):
    """Parse cache should store None for paths that don't match template."""
    # Create a path that won't match the template
    bad_path = tmp_path / "not_matching" / "anything"
    bad_path.mkdir(parents=True, exist_ok=True)

    # Also create a valid path
    good_path = tmp_path / "shows" / "demo" / "seq" / "ABC" / "0010"
    good_path.mkdir(parents=True, exist_ok=True)

    query = TwoTierCachedQuery(resolver, tmp_path)
    list(query.query())

    # Parse cache should have entries for both paths
    assert len(query._parse_cache) > 0
    # Some entries should be None (non-matching paths)
    none_values = [v for v in query._parse_cache.values() if v is None]
    assert len(none_values) > 0


def test_memory_efficiency_separate_caches(query):
    """Verify that caches are actually separate in memory."""
    list(query.query())

    path_cache_id = id(query._path_cache)
    parse_cache_id = id(query._parse_cache)

    # They should be different objects
    assert path_cache_id != parse_cache_id

    # Invalidating one shouldn't affect the other
    query.invalidate_parse_cache()
    assert id(query._path_cache) == path_cache_id  # Same object

    query.invalidate_path_cache()
    list(query.query())
    assert id(query._path_cache) != path_cache_id  # New object created
