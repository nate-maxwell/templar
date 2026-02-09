import time
from dataclasses import dataclass
from typing import Optional

import pytest

from templar import PathResolver
from templar._query import CachedQuery


@dataclass
class VFXContext(object):
    show: Optional[str] = None
    seq: Optional[str] = None
    shot: Optional[str] = None


@pytest.fixture
def test_structure(tmp_path):
    """Create test directory structure and return root path."""
    # Create: shows/{demo,other}/seq/{ABC,DEF}/{0010,0020}
    # Use individual path components to avoid path separator issues
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
    """Create CachedQuery instance."""
    return CachedQuery(resolver, test_structure)


def test_caches_results_on_first_query(query):
    """First query should populate cache."""
    assert query._cache is None

    list(query.query())

    assert query._cache is not None
    assert len(query._cache) == 8  # 2 shows * 2 seqs * 2 shots


def test_second_query_uses_cache(query):
    """Second query should reuse cached results."""
    list(query.query())
    timestamp_1 = query._cache_timestamp

    time.sleep(0.01)
    list(query.query())
    timestamp_2 = query._cache_timestamp

    assert timestamp_1 == timestamp_2, "Cache timestamp changed (cache miss)"


def test_filters_applied_to_cached_results(query):
    """Filters should work correctly with cached results."""
    results_demo = list(query.query(show="demo"))
    assert len(results_demo) == 4

    results_abc = list(query.query(seq="ABC"))
    assert len(results_abc) == 4

    results_specific = list(query.query(show="demo", seq="ABC", shot="0010"))
    assert len(results_specific) == 1


def test_cache_timeout_expires(resolver, test_structure):
    """Cache should expire after timeout period."""
    query = CachedQuery(resolver, test_structure, cache_timeout=0.05)

    list(query.query())
    timestamp_1 = query._cache_timestamp

    time.sleep(0.1)  # Wait for expiration

    list(query.query())
    timestamp_2 = query._cache_timestamp

    assert timestamp_1 != timestamp_2, "Cache did not expire"


def test_cache_timeout_none_never_expires(resolver, test_structure):
    """Cache with timeout=None should never expire."""
    query = CachedQuery(resolver, test_structure, cache_timeout=None)

    list(query.query())
    timestamp_1 = query._cache_timestamp

    time.sleep(0.1)

    list(query.query())
    timestamp_2 = query._cache_timestamp

    assert timestamp_1 == timestamp_2


def test_invalidate_cache_clears_state(query):
    """invalidate_cache() should clear cache and timestamp."""
    list(query.query())
    assert query._cache is not None
    assert query._cache_timestamp is not None

    query.invalidate_cache()

    assert query._cache is None
    assert query._cache_timestamp is None


def test_invalidate_forces_rescan(query):
    """After invalidation, next query should rescan filesystem."""
    list(query.query())
    timestamp_1 = query._cache_timestamp

    query.invalidate_cache()

    list(query.query())
    timestamp_2 = query._cache_timestamp

    assert timestamp_1 != timestamp_2


def test_filesystem_changes_ignored_until_invalidation(query, test_structure):
    """New files not visible until cache invalidated."""
    results_1 = list(query.query(show="demo"))
    assert len(results_1) == 4

    # Add new shot
    new_shot = test_structure / "shows" / "demo" / "seq" / "ABC" / "0030"
    new_shot.mkdir(parents=True, exist_ok=True)

    results_2 = list(query.query(show="demo"))
    assert len(results_2) == 4, "Cache showed new file before invalidation"

    query.invalidate_cache()

    results_3 = list(query.query(show="demo"))
    assert len(results_3) == 5, "New file not visible after invalidation"


def test_empty_results_cached(query):
    """Empty result sets should be cached."""
    results = list(query.query(show="nonexistent"))
    assert len(results) == 0
    assert query._cache is not None


def test_empty_directory_tree(resolver, tmp_path):
    """Query on empty directory should return empty results."""
    query = CachedQuery(resolver, tmp_path)
    results = list(query.query())
    assert len(results) == 0
    assert query._cache is not None
    assert len(query._cache) == 0


def test_zero_timeout(resolver, tmp_path):
    """Timeout of 0.0 should expire immediately."""
    query = CachedQuery(resolver, tmp_path, cache_timeout=0.0)

    # Create one shot for testing
    shot_path = tmp_path / "shows" / "demo" / "seq" / "ABC" / "0010"
    shot_path.mkdir(parents=True, exist_ok=True)

    list(query.query())

    time.sleep(0.001)
    assert not query._is_cache_valid()


def test_very_long_timeout(resolver, tmp_path):
    """Very long timeout should not expire during test."""
    query = CachedQuery(resolver, tmp_path, cache_timeout=999999.0)

    shot_path = tmp_path / "shows" / "demo" / "seq" / "ABC" / "0010"
    shot_path.mkdir(parents=True, exist_ok=True)

    list(query.query())
    time.sleep(0.1)

    assert query._is_cache_valid()


def test_none_filter_value(resolver, tmp_path):
    """Filtering for None should match contexts with None values."""
    shot_path = tmp_path / "shows" / "demo" / "seq" / "ABC" / "0010"
    shot_path.mkdir(parents=True, exist_ok=True)

    query = CachedQuery(resolver, tmp_path)

    # All contexts have show set, none have task set
    results = list(query.query(show=None))
    assert len(results) == 0
