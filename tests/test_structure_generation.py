"""
Unit tests for PathResolver.create_structure() feature.

Tests the ability to generate directory structures by expanding token values.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from tempfile import TemporaryDirectory

import pytest

from templar import PathResolver


@dataclass
class AssetContext(object):
    project: Optional[str] = None
    category: Optional[str] = None
    asset: Optional[str] = None
    subcontext: Optional[str] = None
    dcc: Optional[str] = None
    file_type: Optional[str] = None
    file_name: Optional[str] = None
    version: Optional[str] = None
    ext: Optional[str] = None


@dataclass
class SimpleContext(object):
    root: Optional[str] = None
    dept: Optional[str] = None
    task: Optional[str] = None


class TestRegisterTokenValues:
    """Tests for register_token_values() method."""

    def test_register_single_token(self):
        """Test registering values for a single token."""
        resolver = PathResolver(AssetContext)
        resolver.register_token_values("dcc", ["maya", "blender", "nuke"])

        assert resolver.get_token_values("dcc") == ["maya", "blender", "nuke"]

    def test_register_multiple_tokens(self):
        """Test registering values for multiple tokens."""
        resolver = PathResolver(AssetContext)
        resolver.register_token_values("dcc", ["maya", "blender"])
        resolver.register_token_values("file_type", ["ma", "fbx"])

        assert resolver.get_token_values("dcc") == ["maya", "blender"]
        assert resolver.get_token_values("file_type") == ["ma", "fbx"]

    def test_get_unregistered_token_returns_empty(self):
        """Test getting values for unregistered token returns empty list."""
        resolver = PathResolver(AssetContext)
        assert resolver.get_token_values("nonexistent") == []

    def test_overwrite_token_values(self):
        """Test that registering same token twice overwrites."""
        resolver = PathResolver(AssetContext)
        resolver.register_token_values("dcc", ["maya"])
        resolver.register_token_values("dcc", ["blender", "nuke"])

        assert resolver.get_token_values("dcc") == ["blender", "nuke"]


class TestCreateStructureDryRun:
    """Tests for create_structure() in dry-run mode (no filesystem changes)."""

    def test_single_token_expansion(self):
        """Test expanding a single token creates correct number of paths."""
        resolver = PathResolver(SimpleContext)
        resolver.register("simple", "<root>/<dept>/<task>")
        resolver.register_token_values("dept", ["modeling", "rigging", "animation"])

        ctx = SimpleContext(root="projects", task="work")
        paths = resolver.create_structure(
            "simple", ctx, dry_run=True, stop_at_token="task"
        )

        assert len(paths) == 3
        assert Path("projects/modeling") in paths
        assert Path("projects/rigging") in paths
        assert Path("projects/animation") in paths

    def test_two_token_expansion(self):
        """Test expanding two tokens creates cartesian product."""
        resolver = PathResolver(SimpleContext)
        resolver.register("simple", "<root>/<dept>/<task>")
        resolver.register_token_values("dept", ["modeling", "rigging"])
        resolver.register_token_values("task", ["work", "publish"])

        ctx = SimpleContext(root="projects")
        paths = resolver.create_structure("simple", ctx, dry_run=True)

        # 2 depts × 2 tasks = 4 paths
        assert len(paths) == 4
        assert Path("projects/modeling/work") in paths
        assert Path("projects/modeling/publish") in paths
        assert Path("projects/rigging/work") in paths
        assert Path("projects/rigging/publish") in paths

    def test_three_token_expansion(self):
        """Test expanding three tokens (like the VFX example)."""
        resolver = PathResolver(AssetContext)
        resolver.register(
            "asset",
            "<project>/Asset/<category>/<asset>/<subcontext>/<dcc>/<file_type>",
        )
        resolver.register_token_values("subcontext", ["anim", "model"])
        resolver.register_token_values("dcc", ["maya", "blender"])
        resolver.register_token_values("file_type", ["ma", "fbx"])

        ctx = AssetContext(project="TEST", category="Char", asset="Ghost")
        paths = resolver.create_structure("asset", ctx, dry_run=True)

        # 2 subcontexts × 2 dccs × 2 file_types = 8 paths
        assert len(paths) == 8

    def test_stop_at_token_limits_expansion(self):
        """Test that stop_at_token prevents deeper expansion."""
        resolver = PathResolver(AssetContext)
        resolver.register(
            "asset",
            "<project>/<category>/<asset>/<subcontext>/<dcc>/<file_type>",
        )
        resolver.register_token_values("subcontext", ["anim", "model"])
        resolver.register_token_values("dcc", ["maya", "blender"])
        resolver.register_token_values("file_type", ["ma", "fbx"])

        ctx = AssetContext(project="TEST", category="Char", asset="Ghost")

        # Stop at 'dcc' - should not expand dcc or file_type
        paths = resolver.create_structure(
            "asset", ctx, dry_run=True, stop_at_token="dcc"
        )

        # Only subcontext expanded: 2 paths
        assert len(paths) == 2
        assert Path("TEST/Char/Ghost/anim") in paths
        assert Path("TEST/Char/Ghost/model") in paths

    def test_stop_at_token_includes_previous_expansions(self):
        """Test that stop_at_token includes all prior token expansions."""
        resolver = PathResolver(AssetContext)
        resolver.register(
            "asset",
            "<project>/<category>/<asset>/<subcontext>/<dcc>/<file_type>",
        )
        resolver.register_token_values("subcontext", ["anim", "model"])
        resolver.register_token_values("dcc", ["maya", "blender"])
        resolver.register_token_values("file_type", ["ma", "fbx"])

        ctx = AssetContext(project="TEST", category="Char", asset="Ghost")

        # Stop at 'file_type' - should expand subcontext and dcc, but not file_type
        paths = resolver.create_structure(
            "asset", ctx, dry_run=True, stop_at_token="file_type"
        )

        # subcontext × dcc = 2 × 2 = 4 paths
        assert len(paths) == 4
        assert Path("TEST/Char/Ghost/anim/maya") in paths
        assert Path("TEST/Char/Ghost/anim/blender") in paths
        assert Path("TEST/Char/Ghost/model/maya") in paths
        assert Path("TEST/Char/Ghost/model/blender") in paths

    def test_partial_context_skips_populated_tokens(self):
        """Test that tokens already in context are not expanded."""
        resolver = PathResolver(AssetContext)
        resolver.register("asset", "<project>/<category>/<subcontext>/<dcc>")
        resolver.register_token_values("category", ["Char", "Prop", "Env"])
        resolver.register_token_values("subcontext", ["anim", "model"])
        resolver.register_token_values("dcc", ["maya", "blender"])

        # Provide category in context - it should not be expanded
        ctx = AssetContext(project="TEST", category="Char")
        paths = resolver.create_structure("asset", ctx, dry_run=True)

        # Only subcontext and dcc expanded: 2 × 2 = 4 paths
        assert len(paths) == 4
        for path in paths:
            assert "Char" in str(path)  # All should use 'Char'
            assert "Prop" not in str(path)
            assert "Env" not in str(path)

    def test_no_registered_values_returns_single_path(self):
        """Test that if no tokens have registered values, returns single formatted path."""
        resolver = PathResolver(SimpleContext)
        resolver.register("simple", "<root>/<dept>/<task>")

        # No token values registered
        ctx = SimpleContext(root="projects", dept="modeling", task="work")
        paths = resolver.create_structure("simple", ctx, dry_run=True)

        assert len(paths) == 1
        assert Path("projects/modeling/work") in paths

    def test_mixed_registered_and_unregistered_tokens(self):
        """Test expansion when only some tokens have registered values."""
        resolver = PathResolver(SimpleContext)
        resolver.register("simple", "<root>/<dept>/<task>")
        resolver.register_token_values("dept", ["modeling", "rigging"])
        # 'task' has no registered values

        ctx = SimpleContext(root="projects", task="work")
        paths = resolver.create_structure("simple", ctx, dry_run=True)

        # Only dept expanded: 2 paths
        assert len(paths) == 2
        assert Path("projects/modeling/work") in paths
        assert Path("projects/rigging/work") in paths


class TestCreateStructureErrors:
    """Tests for error handling in create_structure()."""

    def test_nonexistent_template_raises_error(self):
        """Test that using non-existent template name raises KeyError."""
        resolver = PathResolver(SimpleContext)
        ctx = SimpleContext(root="test")

        with pytest.raises(KeyError, match="Template 'nonexistent' not registered"):
            resolver.create_structure("nonexistent", ctx, dry_run=True)

    def test_invalid_stop_at_token_raises_error(self):
        """Test that invalid stop_at_token raises ValueError with helpful message."""
        resolver = PathResolver(SimpleContext)
        resolver.register("simple", "<root>/<dept>/<task>")
        ctx = SimpleContext(root="test")

        with pytest.raises(ValueError, match="stop_at_token 'invalid' not found"):
            resolver.create_structure(
                "simple", ctx, dry_run=True, stop_at_token="invalid"
            )

    def test_error_message_shows_available_tokens(self):
        """Test that error message lists available tokens."""
        resolver = PathResolver(SimpleContext)
        resolver.register("simple", "<root>/<dept>/<task>")
        ctx = SimpleContext(root="test")

        with pytest.raises(
            ValueError, match=r"Available tokens: \['root', 'dept', 'task'\]"
        ):
            resolver.create_structure(
                "simple", ctx, dry_run=True, stop_at_token="invalid"
            )


class TestCreateStructureFilesystem:
    """Tests for create_structure() with actual filesystem operations."""

    def test_creates_directories_on_filesystem(self):
        """Test that directories are actually created when dry_run=False."""
        with TemporaryDirectory() as tmpdir:
            resolver = PathResolver(SimpleContext)
            resolver.register("simple", f"{tmpdir}/<root>/<dept>/<task>")
            resolver.register_token_values("dept", ["modeling", "rigging"])

            ctx = SimpleContext(root="projects", task="work")
            paths = resolver.create_structure(
                "simple", ctx, dry_run=False, stop_at_token="task"
            )

            # Verify directories exist
            assert len(paths) == 2
            for path in paths:
                assert path.exists()
                assert path.is_dir()

    def test_creates_nested_directory_structure(self):
        """Test creating deep nested directory structures."""
        with TemporaryDirectory() as tmpdir:
            resolver = PathResolver(AssetContext)
            resolver.register(
                "asset",
                f"{tmpdir}/<project>/<category>/<asset>/<dcc>",
            )
            resolver.register_token_values("category", ["Char", "Prop"])
            resolver.register_token_values("asset", ["Ghost", "Table"])
            resolver.register_token_values("dcc", ["maya", "blender"])

            ctx = AssetContext(project="TEST")
            paths = resolver.create_structure("asset", ctx, dry_run=False)

            # 2 × 2 × 2 = 8 directories
            assert len(paths) == 8
            for path in paths:
                assert path.exists()
                assert path.is_dir()

            # Verify specific paths
            expected_path = Path(tmpdir) / "TEST" / "Char" / "Ghost" / "maya"
            assert expected_path.exists()

    def test_dry_run_does_not_create_directories(self):
        """Test that dry_run=True does not create any directories."""
        with TemporaryDirectory() as tmpdir:
            resolver = PathResolver(SimpleContext)
            resolver.register("simple", f"{tmpdir}/<root>/<dept>")
            resolver.register_token_values("dept", ["modeling", "rigging"])

            ctx = SimpleContext(root="projects")
            paths = resolver.create_structure("simple", ctx, dry_run=True)

            # Paths returned but not created
            assert len(paths) == 2
            for path in paths:
                assert not path.exists()

    def test_existing_directories_handled_gracefully(self):
        """Test that creating already-existing directories doesn't raise errors."""
        with TemporaryDirectory() as tmpdir:
            resolver = PathResolver(SimpleContext)
            resolver.register("simple", f"{tmpdir}/<root>/<dept>")
            resolver.register_token_values("dept", ["modeling"])

            ctx = SimpleContext(root="projects")

            # Create once
            paths1 = resolver.create_structure("simple", ctx, dry_run=False)
            assert len(paths1) == 1
            assert paths1[0].exists()

            # Create again - should not raise error
            paths2 = resolver.create_structure("simple", ctx, dry_run=False)
            assert len(paths2) == 1
            assert paths2[0].exists()


class TestCreateStructureComplexScenarios:
    """Tests for complex real-world scenarios."""

    def test_vfx_asset_structure_example(self):
        """Test the complete VFX asset structure example from documentation."""
        resolver = PathResolver(AssetContext)
        resolver.register(
            "asset",
            "T:/projects/<project>/Asset/<category>/<asset>/<subcontext>/<dcc>/<file_type>/<file_name>_v<version>.<ext>",
        )

        resolver.register_token_values(
            "subcontext", ["anim", "model", "rig", "lookdev"]
        )
        resolver.register_token_values("dcc", ["maya", "blender", "nuke", "houdini"])
        resolver.register_token_values("file_type", ["fbx", "ma", "blend", "abc", "mb"])

        ctx = AssetContext(
            project="TEST_PROJECT",
            category="Char",
            asset="Ghost_A",
        )

        paths = resolver.create_structure(
            "asset",
            ctx,
            dry_run=True,
            stop_at_token="file_name",
        )

        # 4 subcontexts × 4 dccs × 5 file_types = 80 paths
        assert len(paths) == 80

        # Verify some specific paths
        expected_paths = [
            Path("T:/projects/TEST_PROJECT/Asset/Char/Ghost_A/anim/maya/fbx"),
            Path("T:/projects/TEST_PROJECT/Asset/Char/Ghost_A/anim/maya/ma"),
            Path("T:/projects/TEST_PROJECT/Asset/Char/Ghost_A/model/blender/blend"),
            Path("T:/projects/TEST_PROJECT/Asset/Char/Ghost_A/rig/houdini/abc"),
        ]

        for expected in expected_paths:
            assert expected in paths

    def test_no_duplicates_in_output(self):
        """Test that output paths contain no duplicates."""
        resolver = PathResolver(AssetContext)
        resolver.register("asset", "<project>/<category>/<dcc>/<file_type>")
        resolver.register_token_values("dcc", ["maya", "blender"])
        resolver.register_token_values("file_type", ["ma", "fbx"])

        ctx = AssetContext(project="TEST", category="Char")
        paths = resolver.create_structure("asset", ctx, dry_run=True)

        # Check no duplicates
        assert len(paths) == len(set(paths))

    def test_formatters_preserved_in_expansion(self):
        """Test that token formatters are preserved during expansion."""
        resolver = PathResolver(AssetContext)
        resolver.register("asset", "<project>/<category:upper>/<dcc>")
        resolver.register_token_values("category", ["char", "prop"])
        resolver.register_token_values("dcc", ["maya"])

        ctx = AssetContext(project="TEST")
        paths = resolver.create_structure("asset", ctx, dry_run=True)

        # Categories should be uppercase
        assert Path("TEST/CHAR/maya") in paths
        assert Path("TEST/PROP/maya") in paths

    def test_single_value_token_still_expands(self):
        """Test that tokens with single value still work correctly."""
        resolver = PathResolver(SimpleContext)
        resolver.register("simple", "<root>/<dept>/<task>")
        resolver.register_token_values("dept", ["modeling"])  # Single value
        resolver.register_token_values("task", ["work", "publish"])

        ctx = SimpleContext(root="projects")
        paths = resolver.create_structure("simple", ctx, dry_run=True)

        # 1 dept × 2 tasks = 2 paths
        assert len(paths) == 2
        assert Path("projects/modeling/work") in paths
        assert Path("projects/modeling/publish") in paths

    def test_empty_token_values_list_skips_expansion(self):
        """Test that empty registered values list results in no expansion."""
        resolver = PathResolver(SimpleContext)
        resolver.register("simple", "<root>/<dept>/<task>")
        resolver.register_token_values("dept", [])  # Empty list

        ctx = SimpleContext(root="projects", task="work")
        paths = resolver.create_structure("simple", ctx, dry_run=True)

        # No expansion should occur, need dept in context to format
        assert len(paths) == 0
