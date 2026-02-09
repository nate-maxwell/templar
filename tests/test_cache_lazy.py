from dataclasses import dataclass
from typing import Optional

import pytest

from templar import PathResolver
from templar import LazyQuery


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
    """Create LazyQuery instance."""
    return LazyQuery(resolver, test_structure)


def test_cache_empty_initially(query):
    """Cache should be empty before any queries."""
    assert len(query._cache) == 0


def test_first_query_populates_cache(query):
    """First query should populate cache for that specific filter."""
    list(query.query(show="demo"))

    assert len(query._cache) == 1
    # Verify cache key is frozenset of filter items
    cache_keys = list(query._cache.keys())
    assert cache_keys[0] == frozenset([("show", "demo")])


def test_second_identical_query_uses_cache(query):
    """Second identical query should use cached results."""
    # First query
    results_1 = list(query.query(show="demo"))
    cache_size_1 = len(query._cache)

    # Second query - should hit cache
    results_2 = list(query.query(show="demo"))
    cache_size_2 = len(query._cache)

    # Cache shouldn't grow
    assert cache_size_1 == cache_size_2 == 1
    # Results should be identical
    assert results_1 == results_2


def test_different_queries_cache_separately(query):
    """Different filter combinations should cache separately."""
    list(query.query(show="demo"))
    assert len(query._cache) == 1

    list(query.query(show="other"))
    assert len(query._cache) == 2

    list(query.query(seq="ABC"))
    assert len(query._cache) == 3

    list(query.query(show="demo", seq="ABC"))
    assert len(query._cache) == 4


def test_filters_work_correctly(query):
    """Filters should correctly filter results."""
    results_demo = list(query.query(show="demo"))
    assert len(results_demo) == 4

    results_abc = list(query.query(seq="ABC"))
    assert len(results_abc) == 4

    results_specific = list(query.query(show="demo", seq="ABC", shot="0010"))
    assert len(results_specific) == 1


def test_no_filters_caches_all_results(query):
    """Query with no filters should cache all results."""
    results = list(query.query())

    assert len(results) == 8  # 2 shows * 2 seqs * 2 shots
    assert len(query._cache) == 1

    # Cache key for no filters is empty frozenset
    assert frozenset() in query._cache


def test_filter_order_doesnt_matter(query):
    """Filter order shouldn't affect cache key."""
    # Query with filters in one order
    list(query.query(show="demo", seq="ABC"))

    # Query with filters in different order
    list(query.query(seq="ABC", show="demo"))

    # Should use same cache entry (frozenset ignores order)
    assert len(query._cache) == 1


def test_invalidate_cache_specific_filter(query):
    """invalidate_cache() should invalidate specific filter combination."""
    list(query.query(show="demo"))
    list(query.query(show="other"))
    assert len(query._cache) == 2

    # Invalidate only show="demo"
    query.invalidate_cache(show="demo")

    assert len(query._cache) == 1
    assert frozenset([("show", "other")]) in query._cache
    assert frozenset([("show", "demo")]) not in query._cache


def test_invalidate_cache_nonexistent_filter(query):
    """Invalidating nonexistent filter should not raise error."""
    list(query.query(show="demo"))

    # This shouldn't raise an error
    query.invalidate_cache(show="nonexistent")

    # Original cache should remain
    assert len(query._cache) == 1


def test_invalidate_all_clears_entire_cache(query):
    """invalidate_all() should clear all cached queries."""
    list(query.query(show="demo"))
    list(query.query(show="other"))
    list(query.query(seq="ABC"))
    assert len(query._cache) == 3

    query.invalidate_all()

    assert len(query._cache) == 0


def test_query_after_invalidation_repopulates(query):
    """Query after invalidation should repopulate that cache entry."""
    list(query.query(show="demo"))
    assert len(query._cache) == 1

    query.invalidate_cache(show="demo")
    assert len(query._cache) == 0

    # Query again - should repopulate
    results = list(query.query(show="demo"))
    assert len(results) == 4
    assert len(query._cache) == 1


def test_filesystem_changes_not_visible_until_invalidation(query, test_structure):
    """New files not visible until cache invalidated."""
    results_1 = list(query.query(show="demo"))
    assert len(results_1) == 4

    # Add new shot
    new_shot = test_structure / "shows" / "demo" / "seq" / "ABC" / "0030"
    new_shot.mkdir(parents=True, exist_ok=True)

    # Query again - should use cache
    results_2 = list(query.query(show="demo"))
    assert len(results_2) == 4, "Cache showed new file before invalidation"

    # Invalidate cache for this filter
    query.invalidate_cache(show="demo")

    # Query again - should see new file
    results_3 = list(query.query(show="demo"))
    assert len(results_3) == 5, "New file not visible after invalidation"


def test_empty_results_cached(query):
    """Empty result sets should be cached."""
    results = list(query.query(show="nonexistent"))
    assert len(results) == 0

    # Should still create cache entry
    assert len(query._cache) == 1
    assert frozenset([("show", "nonexistent")]) in query._cache


def test_cache_grows_with_unique_queries(query):
    """Cache should grow as different queries are made."""
    # Make 10 different queries
    for i in range(5):
        list(query.query(show="demo", shot=f"00{i}0"))

    # Cache should have 5 entries (even though some return empty results)
    assert len(query._cache) == 5


def test_memory_efficient_for_repeated_queries(query):
    """Repeated identical queries shouldn't increase cache size."""
    # Query same filter combination 100 times
    for _ in range(100):
        list(query.query(show="demo"))

    # Cache should still only have 1 entry
    assert len(query._cache) == 1


def test_multiple_filter_values(query):
    """Multiple filter combinations should work correctly."""
    # Different combinations
    results_1 = list(query.query(show="demo", seq="ABC"))
    results_2 = list(query.query(show="demo", seq="DEF"))
    results_3 = list(query.query(show="other", seq="ABC"))

    assert len(results_1) == 2
    assert len(results_2) == 2
    assert len(results_3) == 2

    # Should have 3 separate cache entries
    assert len(query._cache) == 3


def test_invalidate_respects_exact_filter_match(query):
    """Invalidation should only clear exact filter match."""
    list(query.query(show="demo"))
    list(query.query(show="demo", seq="ABC"))
    assert len(query._cache) == 2

    # Invalidate only show="demo" (not show="demo" + seq="ABC")
    query.invalidate_cache(show="demo")

    assert len(query._cache) == 1
    # The multi-filter query should remain
    assert frozenset([("show", "demo"), ("seq", "ABC")]) in query._cache


def test_cached_results_are_lists(query):
    """Cached results should be stored as lists."""
    list(query.query(show="demo"))

    cache_key = frozenset([("show", "demo")])
    cached_value = query._cache[cache_key]

    assert isinstance(cached_value, list)
    assert len(cached_value) == 4


def test_none_filter_value(query):
    """Filtering for None should work correctly."""
    # Query for None explicitly
    results = list(query.query(show=None))
    assert len(results) == 0

    # Should cache this query
    assert frozenset([("show", None)]) in query._cache


def test_cache_key_is_immutable(query):
    """Cache keys should be immutable frozensets."""
    list(query.query(show="demo"))

    cache_keys = list(query._cache.keys())
    assert all(isinstance(key, frozenset) for key in cache_keys)
