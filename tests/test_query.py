from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from tempfile import TemporaryDirectory

from templar import PathResolver
from templar import Query


@dataclass
class VFXContext(object):
    """Test context for VFX pipeline paths."""

    show: Optional[str] = None
    seq: Optional[str] = None
    shot: Optional[str] = None
    task: Optional[str] = None
    version: Optional[str] = None
    ext: Optional[str] = None


@dataclass
class AssetContext(object):
    """Test context for asset paths."""

    project: Optional[str] = None
    asset_type: Optional[str] = None
    asset_name: Optional[str] = None
    version: Optional[str] = None


class TestQueryInitialization(object):
    """Test Query object initialization."""

    def test_init_with_resolver_and_root(self) -> None:
        """Query initializes with resolver and root path."""
        resolver = PathResolver(VFXContext)
        root = Path("/shows")
        query = Query(resolver, root)

        assert query.resolver is resolver
        assert query.root == root

    def test_init_stores_references(self) -> None:
        """Query stores references to resolver and root correctly."""
        resolver = PathResolver(VFXContext)
        root = Path("/tmp/test")
        query = Query(resolver, root)

        assert isinstance(query.resolver, PathResolver)
        assert isinstance(query.root, Path)


class TestMatchesFilters(object):
    """Test the _matches_filters static method."""

    def test_empty_filters_returns_true(self) -> None:
        """Empty filters match any context."""
        ctx = VFXContext(show="demo", seq="010")
        assert Query._matches_filters(ctx, {}) is True

    def test_single_matching_filter(self) -> None:
        """Single filter matches when attribute equals value."""
        ctx = VFXContext(show="demo", seq="010")
        assert Query._matches_filters(ctx, {"show": "demo"}) is True

    def test_single_non_matching_filter(self) -> None:
        """Single filter fails when attribute doesn't equal value."""
        ctx = VFXContext(show="demo", seq="010")
        assert Query._matches_filters(ctx, {"show": "other"}) is False

    def test_multiple_matching_filters(self) -> None:
        """Multiple filters match when all attributes equal values."""
        ctx = VFXContext(show="demo", seq="010", shot="0010")
        filters = {"show": "demo", "seq": "010"}
        assert Query._matches_filters(ctx, filters) is True

    def test_multiple_filters_partial_match(self) -> None:
        """Multiple filters fail when any attribute doesn't match."""
        ctx = VFXContext(show="demo", seq="010", shot="0010")
        filters = {"show": "demo", "seq": "020"}
        assert Query._matches_filters(ctx, filters) is False

    def test_filter_on_none_attribute(self) -> None:
        """Filter fails when checking against None attribute."""
        ctx = VFXContext(show="demo", seq=None)
        assert Query._matches_filters(ctx, {"seq": "010"}) is False

    def test_filter_for_none_value(self) -> None:
        """Filter matches when checking for None explicitly."""
        ctx = VFXContext(show="demo", seq=None)
        assert Query._matches_filters(ctx, {"seq": None}) is True

    def test_filter_nonexistent_attribute(self) -> None:
        """Filter fails gracefully on non-existent attribute."""
        ctx = VFXContext(show="demo")
        assert Query._matches_filters(ctx, {"nonexistent": "value"}) is False


class TestWalkPaths(object):
    """Test the _walk_paths method."""

    def test_walk_empty_directory(self) -> None:
        """Walking empty directory yields no paths."""
        with TemporaryDirectory() as tmpdir:
            resolver = PathResolver(VFXContext)
            query = Query(resolver, Path(tmpdir))
            paths = list(query._walk_paths())
            assert paths == []

    def test_walk_single_file(self) -> None:
        """Walking directory with one file yields that file."""
        with TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.touch()

            resolver = PathResolver(VFXContext)
            query = Query(resolver, Path(tmpdir))
            paths = list(query._walk_paths())

            assert len(paths) == 1
            assert paths[0] == test_file

    def test_walk_nested_files(self) -> None:
        """Walking directory finds nested files."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "dir1").mkdir()
            (root / "dir1" / "file1.txt").touch()
            (root / "dir2").mkdir()
            (root / "dir2" / "file2.txt").touch()

            resolver = PathResolver(VFXContext)
            query = Query(resolver, root)
            paths = list(query._walk_paths())

            assert len(paths) == 4  # 2 directories + 2 files

    def test_walk_includes_directories(self) -> None:
        """Walking includes both files and directories."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            subdir = root / "subdir"
            subdir.mkdir()
            (subdir / "file.txt").touch()

            resolver = PathResolver(VFXContext)
            query = Query(resolver, root)
            paths = list(query._walk_paths())

            assert subdir in paths
            assert subdir / "file.txt" in paths


class TestFindAssets(object):
    """Test the find_assets method."""

    def test_find_assets_empty_directory(self) -> None:
        """Finding assets in empty directory returns empty iterator."""
        with TemporaryDirectory() as tmpdir:
            resolver = PathResolver(VFXContext)
            resolver.register("shot", "shows/<show>/seq/<seq>/<shot>")
            query = Query(resolver, Path(tmpdir))

            results = list(query.query())
            assert results == []

    def test_find_assets_no_matching_templates(self) -> None:
        """Finding assets with no matching templates returns empty."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "random" / "path").mkdir(parents=True)
            (root / "random" / "path" / "file.txt").touch()

            resolver = PathResolver(VFXContext)
            resolver.register("shot", "shows/<show>/seq/<seq>/<shot>")
            query = Query(resolver, root)

            results = list(query.query())
            assert results == []

    def test_find_assets_single_match(self) -> None:
        """Finding assets returns single matching context."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "shows" / "demo" / "seq" / "010" / "0010"
            path.mkdir(parents=True)

            resolver = PathResolver(VFXContext)
            resolver.register("shot", f"{root}/shows/<show>/seq/<seq>/<shot>")
            query = Query(resolver, root)

            results = list(query.query())
            assert len(results) == 1
            assert results[0].show == "demo"
            assert results[0].seq == "010"
            assert results[0].shot == "0010"

    def test_find_assets_multiple_matches(self) -> None:
        """Finding assets returns multiple matching contexts."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "shows" / "demo" / "seq" / "010" / "0010").mkdir(parents=True)
            (root / "shows" / "demo" / "seq" / "010" / "0020").mkdir(parents=True)
            (root / "shows" / "demo" / "seq" / "020" / "0010").mkdir(parents=True)

            resolver = PathResolver(VFXContext)
            resolver.register("shot", f"{root}/shows/<show>/seq/<seq>/<shot>")
            query = Query(resolver, root)

            results = list(query.query())
            assert len(results) == 3

    def test_find_assets_with_show_filter(self) -> None:
        """Finding assets filters by show."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "shows" / "demo" / "seq" / "010" / "0010").mkdir(parents=True)
            (root / "shows" / "other" / "seq" / "010" / "0010").mkdir(parents=True)

            resolver = PathResolver(VFXContext)
            resolver.register("shot", f"{root}/shows/<show>/seq/<seq>/<shot>")
            query = Query(resolver, root)

            results = list(query.query(show="demo"))
            assert len(results) == 1
            assert results[0].show == "demo"

    def test_find_assets_with_multiple_filters(self) -> None:
        """Finding assets filters by multiple criteria."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "shows" / "demo" / "seq" / "010" / "0010").mkdir(parents=True)
            (root / "shows" / "demo" / "seq" / "010" / "0020").mkdir(parents=True)
            (root / "shows" / "demo" / "seq" / "020" / "0010").mkdir(parents=True)

            resolver = PathResolver(VFXContext)
            resolver.register("shot", f"{root}/shows/<show>/seq/<seq>/<shot>")
            query = Query(resolver, root)

            results = list(query.query(show="demo", seq="010"))
            assert len(results) == 2
            assert all(r.show == "demo" and r.seq == "010" for r in results)

    def test_find_assets_filter_no_matches(self) -> None:
        """Finding assets with non-matching filter returns empty."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "shows" / "demo" / "seq" / "010" / "0010").mkdir(parents=True)

            resolver = PathResolver(VFXContext)
            resolver.register("shot", f"{root}/shows/<show>/seq/<seq>/<shot>")
            query = Query(resolver, root)

            results = list(query.query(show="nonexistent"))
            assert results == []

    def test_find_assets_partial_path_no_match(self) -> None:
        """Finding assets ignores partial paths that don't fully match template."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "shows" / "demo").mkdir(parents=True)
            (root / "shows" / "demo" / "seq").mkdir()

            resolver = PathResolver(VFXContext)
            resolver.register("shot", f"{root}/shows/<show>/seq/<seq>/<shot>")
            query = Query(resolver, root)

            results = list(query.query())
            assert results == []

    def test_find_assets_mixed_matching_nonmatching(self) -> None:
        """Finding assets returns only matching paths from mixed directory."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "shows" / "demo" / "seq" / "010" / "0010").mkdir(parents=True)
            (root / "random" / "other" / "path").mkdir(parents=True)
            (root / "shows" / "incomplete").mkdir(parents=True)

            resolver = PathResolver(VFXContext)
            resolver.register("shot", f"{root}/shows/<show>/seq/<seq>/<shot>")
            query = Query(resolver, root)

            results = list(query.query())
            assert len(results) == 1
            assert results[0].shot == "0010"

    def test_find_assets_with_files(self) -> None:
        """Finding assets works with file paths not just directories."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            shot_dir = root / "shows" / "demo" / "seq" / "010" / "0010"
            shot_dir.mkdir(parents=True)
            (shot_dir / "file.ma").touch()

            resolver = PathResolver(VFXContext)
            resolver.register("shot", f"{root}/shows/<show>/seq/<seq>/<shot>")
            query = Query(resolver, root)

            results = list(query.query())
            # Should match both the directory and file paths
            assert len(results) >= 1
            assert any(r.shot == "0010" for r in results)

    def test_find_assets_multiple_templates(self) -> None:
        """Finding assets works with resolver having multiple templates."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "shows" / "demo" / "seq" / "010" / "0010").mkdir(parents=True)
            (root / "projects" / "proj1" / "chars" / "hero").mkdir(parents=True)

            resolver = PathResolver(AssetContext)
            resolver.register(
                "shot", f"{root}/shows/<project>/seq/<asset_type>/<asset_name>"
            )
            resolver.register(
                "asset", f"{root}/projects/<project>/<asset_type>/<asset_name>"
            )
            query = Query(resolver, root)

            results = list(query.query())
            assert len(results) == 2


class TestFindAssetsIntegration(object):
    """Integration tests for find_assets with realistic scenarios."""

    def test_vfx_pipeline_structure(self) -> None:
        """Finding assets in typical VFX pipeline structure."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create typical VFX structure
            for show in ["demo", "test"]:
                for seq in ["010", "020"]:
                    for shot in ["0010", "0020"]:
                        path = root / "shows" / show / "seq" / seq / shot
                        path.mkdir(parents=True)

            resolver = PathResolver(VFXContext)
            resolver.register("shot", f"{root}/shows/<show>/seq/<seq>/<shot>")
            query = Query(resolver, root)

            # Find all shots for show "demo"
            results = list(query.query(show="demo"))
            assert len(results) == 4

            # Find specific sequence
            results = list(query.query(show="demo", seq="010"))
            assert len(results) == 2

            # Find specific shot
            results = list(query.query(show="demo", seq="010", shot="0010"))
            assert len(results) == 1

    def test_asset_library_structure(self) -> None:
        """Finding assets in asset library structure."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create asset library
            for proj in ["film1", "film2"]:
                for atype in ["chars", "props", "envs"]:
                    for name in ["hero", "villain"]:
                        path = root / "projects" / proj / atype / name
                        path.mkdir(parents=True)

            resolver = PathResolver(AssetContext)
            resolver.register(
                "asset", f"{root}/projects/<project>/<asset_type>/<asset_name>"
            )
            query = Query(resolver, root)

            # Find all characters
            results = list(query.query(asset_type="chars"))
            assert len(results) == 4

            # Find specific project assets
            results = list(query.query(project="film1"))
            assert len(results) == 6
