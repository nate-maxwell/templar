import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from templar import PathResolver
from templar import CompositeResolver


@dataclass
class VFXContext(object):
    show: Optional[str] = None
    seq: Optional[str] = None
    shot: Optional[str] = None
    dcc: Optional[str] = None


@dataclass
class AssetContext(object):
    category: Optional[str] = None
    asset: Optional[str] = None


class TestPathResolverWithVariables:
    def test_single_variable_substitution(self) -> None:
        resolver = PathResolver(VFXContext, variables={"ROOT": "V:/projects"})
        resolver.register("shot", "{ROOT}/shows/<show>/seq/<seq>")

        ctx = VFXContext(show="demo", seq="010")
        path = resolver.resolve("shot", ctx)

        assert path == Path("V:/projects/shows/demo/seq/010")

    def test_multiple_variable_substitution(self) -> None:
        variables = {"ROOT": "/mnt/storage", "SHOW_DIR": "productions"}
        resolver = PathResolver(VFXContext, variables=variables)
        resolver.register("shot", "{ROOT}/{SHOW_DIR}/<show>/seq/<seq>")

        ctx = VFXContext(show="demo", seq="010")
        path = resolver.resolve("shot", ctx)

        assert path == Path("/mnt/storage/productions/demo/seq/010")

    def test_no_variables_provided(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>")

        ctx = VFXContext(show="demo", seq="010")
        path = resolver.resolve("shot", ctx)

        assert path == Path("V:/shows/demo/seq/010")

    def test_variable_not_in_pattern(self) -> None:
        resolver = PathResolver(VFXContext, variables={"ROOT": "/mnt/storage"})
        resolver.register("shot", "V:/shows/<show>/seq/<seq>")

        ctx = VFXContext(show="demo", seq="010")
        path = resolver.resolve("shot", ctx)

        assert path == Path("V:/shows/demo/seq/010")

    def test_parse_path_with_variables(self) -> None:
        resolver = PathResolver(VFXContext, variables={"ROOT": "V:/projects"})
        resolver.register("shot", "{ROOT}/shows/<show>/seq/<seq>/<shot>")

        path = Path("V:/projects/shows/demo/seq/010/0010")
        ctx = resolver.parse_path(path)

        assert ctx is not None
        assert ctx.show == "demo"
        assert ctx.seq == "010"
        assert ctx.shot == "0010"

    def test_round_trip_with_variables(self) -> None:
        resolver = PathResolver(VFXContext, variables={"ROOT": "/mnt/storage"})
        resolver.register("shot", "{ROOT}/shows/<show>/seq/<seq>/<shot>")

        original_ctx = VFXContext(show="demo", seq="010", shot="0010")
        path = resolver.resolve("shot", original_ctx)
        parsed_ctx = resolver.parse_path(path)

        assert parsed_ctx.show == original_ctx.show
        assert parsed_ctx.seq == original_ctx.seq
        assert parsed_ctx.shot == original_ctx.shot

    def test_platform_specific_root(self) -> None:
        root = (
            "V:/projects" if platform.system() == "Windows" else "/mnt/storage/projects"
        )
        resolver = PathResolver(VFXContext, variables={"PROJECT_ROOT": root})
        resolver.register("shot", "{PROJECT_ROOT}/shows/<show>/seq/<seq>")

        ctx = VFXContext(show="demo", seq="010")
        path = resolver.resolve("shot", ctx)

        if platform.system() == "Windows":
            assert str(path).startswith("V:")
        else:
            assert str(path).startswith("/mnt/storage")


class TestCompositeResolverWithVariables:
    def test_single_context_with_variables(self) -> None:
        composite = CompositeResolver(variables={"ROOT": "V:/projects"})
        composite.register(VFXContext, "shot", "{ROOT}/shows/<show>/seq/<seq>")

        ctx = VFXContext(show="demo", seq="010")
        path = composite.resolve("shot", ctx)

        assert path == Path("V:/projects/shows/demo/seq/010")

    def test_multiple_contexts_share_variables(self) -> None:
        variables = {"ROOT": "/mnt/storage"}
        composite = CompositeResolver(variables=variables)

        composite.register(VFXContext, "shot", "{ROOT}/shows/<show>/seq/<seq>")
        composite.register(AssetContext, "asset", "{ROOT}/assets/<category>/<asset>")

        vfx_ctx = VFXContext(show="demo", seq="010")
        asset_ctx = AssetContext(category="props", asset="table")

        vfx_path = composite.resolve("shot", vfx_ctx)
        asset_path = composite.resolve("asset", asset_ctx)

        assert vfx_path == Path("/mnt/storage/shows/demo/seq/010")
        assert asset_path == Path("/mnt/storage/assets/props/table")

    def test_parse_path_with_variables(self) -> None:
        composite = CompositeResolver(variables={"ROOT": "V:/projects"})
        composite.register(VFXContext, "shot", "{ROOT}/shows/<show>/seq/<seq>/<shot>")

        path = Path("V:/projects/shows/demo/seq/010/0010")
        ctx = composite.parse_path(VFXContext, path)

        assert ctx is not None
        assert ctx.show == "demo"
        assert ctx.seq == "010"
        assert ctx.shot == "0010"

    def test_multiple_variables_multiple_contexts(self) -> None:
        variables = {
            "ROOT": "/mnt/storage",
            "SHOW_DIR": "productions",
            "ASSET_DIR": "library",
        }
        composite = CompositeResolver(variables=variables)

        composite.register(VFXContext, "shot", "{ROOT}/{SHOW_DIR}/<show>/seq/<seq>")
        composite.register(
            AssetContext, "asset", "{ROOT}/{ASSET_DIR}/<category>/<asset>"
        )

        vfx_ctx = VFXContext(show="demo", seq="010")
        asset_ctx = AssetContext(category="props", asset="table")

        vfx_path = composite.resolve("shot", vfx_ctx)
        asset_path = composite.resolve("asset", asset_ctx)

        assert vfx_path == Path("/mnt/storage/productions/demo/seq/010")
        assert asset_path == Path("/mnt/storage/library/props/table")

    def test_round_trip_with_variables(self) -> None:
        composite = CompositeResolver(variables={"ROOT": "V:/projects"})
        composite.register(VFXContext, "shot", "{ROOT}/shows/<show>/seq/<seq>/<shot>")

        original_ctx = VFXContext(show="demo", seq="010", shot="0010")
        path = composite.resolve("shot", original_ctx)
        parsed_ctx = composite.parse_path(VFXContext, path)

        assert parsed_ctx.show == original_ctx.show
        assert parsed_ctx.seq == original_ctx.seq
        assert parsed_ctx.shot == original_ctx.shot

    def test_no_variables_in_composite(self) -> None:
        composite = CompositeResolver()
        composite.register(VFXContext, "shot", "V:/shows/<show>/seq/<seq>")

        ctx = VFXContext(show="demo", seq="010")
        path = composite.resolve("shot", ctx)

        assert path == Path("V:/shows/demo/seq/010")

    def test_platform_specific_composite(self) -> None:
        root = (
            "V:/projects" if platform.system() == "Windows" else "/mnt/storage/projects"
        )
        composite = CompositeResolver(variables={"PROJECT_ROOT": root})

        composite.register(VFXContext, "shot", "{PROJECT_ROOT}/shows/<show>/seq/<seq>")
        composite.register(
            AssetContext, "asset", "{PROJECT_ROOT}/assets/<category>/<asset>"
        )

        vfx_ctx = VFXContext(show="demo", seq="010")
        asset_ctx = AssetContext(category="props", asset="table")

        vfx_path = composite.resolve("shot", vfx_ctx)
        asset_path = composite.resolve("asset", asset_ctx)

        if platform.system() == "Windows":
            assert str(vfx_path).startswith("V:")
            assert str(asset_path).startswith("V:")
        else:
            assert str(vfx_path).startswith("/mnt/storage")
            assert str(asset_path).startswith("/mnt/storage")

    def test_resolve_any_with_variables(self) -> None:
        composite = CompositeResolver(variables={"ROOT": "/mnt/storage"})
        composite.register(
            VFXContext, "shot_full", "{ROOT}/shows/<show>/seq/<seq>/<shot>/<dcc>"
        )
        composite.register(
            VFXContext, "shot_simple", "{ROOT}/shows/<show>/seq/<seq>/<shot>"
        )

        ctx = VFXContext(show="demo", seq="010", shot="0010")
        path = composite.resolve_any(ctx, prefer=["shot_full", "shot_simple"])

        assert path == Path("/mnt/storage/shows/demo/seq/010/0010")

    def test_find_matches_with_variables(self) -> None:
        composite = CompositeResolver(variables={"ROOT": "V:/projects"})
        composite.register(
            VFXContext, "shot_full", "{ROOT}/shows/<show>/seq/<seq>/<shot>/<dcc>"
        )
        composite.register(
            VFXContext, "shot_simple", "{ROOT}/shows/<show>/seq/<seq>/<shot>"
        )

        ctx = VFXContext(show="demo", seq="010", shot="0010")
        matches = composite.find_matches(ctx)

        assert "shot_simple" in matches
        assert "shot_full" not in matches
