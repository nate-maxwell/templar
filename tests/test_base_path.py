from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest

from templar import PathResolver
from templar import CompositeResolver


@dataclass
class VFXContext(object):
    show: Optional[str] = None
    seq: Optional[str] = None
    shot: Optional[str] = None
    task: Optional[str] = None
    version: Optional[str] = None
    dcc: Optional[str] = None


@dataclass
class AssetContext(object):
    category: Optional[str] = None
    asset: Optional[str] = None
    variant: Optional[str] = None


class TestPathResolverInheritance:
    def test_simple_inheritance(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("base", "V:/shows/<show>")
        resolver.register("seq", "seq/<seq>", base="base")

        ctx = VFXContext(show="demo", seq="010")
        path = resolver.resolve("seq", ctx)

        assert path == Path("V:/shows/demo/seq/010")

    def test_multi_level_inheritance(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("show_base", "V:/shows/<show>")
        resolver.register("seq_base", "seq/<seq>", base="show_base")
        resolver.register("shot", "<shot>/work", base="seq_base")

        ctx = VFXContext(show="demo", seq="010", shot="0010")
        path = resolver.resolve("shot", ctx)

        assert path == Path("V:/shows/demo/seq/010/0010/work")

    def test_three_level_inheritance(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("show_base", "V:/shows/<show>")
        resolver.register("seq_base", "seq/<seq>", base="show_base")
        resolver.register("shot_base", "<shot>/work", base="seq_base")
        resolver.register("task", "<task>/v<version>", base="shot_base")

        ctx = VFXContext(
            show="demo", seq="010", shot="0010", task="anim", version="001"
        )
        path = resolver.resolve("task", ctx)

        assert path == Path("V:/shows/demo/seq/010/0010/work/anim/v001")

    def test_multiple_children_same_base(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("show_base", "V:/shows/<show>/seq/<seq>")
        resolver.register("shot_work", "<shot>/__work__", base="show_base")
        resolver.register("shot_pub", "<shot>/__pub__", base="show_base")

        ctx = VFXContext(show="demo", seq="010", shot="0010")

        work_path = resolver.resolve("shot_work", ctx)
        pub_path = resolver.resolve("shot_pub", ctx)

        assert work_path == Path("V:/shows/demo/seq/010/0010/__work__")
        assert pub_path == Path("V:/shows/demo/seq/010/0010/__pub__")

    def test_base_template_not_found(self) -> None:
        resolver = PathResolver(VFXContext)

        with pytest.raises(KeyError, match="Base template 'nonexistent' not found"):
            resolver.register("child", "<seq>", base="nonexistent")

    def test_parse_path_with_inheritance(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("show_base", "V:/shows/<show>")
        resolver.register("seq_base", "seq/<seq>", base="show_base")
        resolver.register("shot", "<shot>/work", base="seq_base")

        path = Path("V:/shows/demo/seq/010/0010/work")
        ctx = resolver.parse_path(path)

        assert ctx is not None
        assert ctx.show == "demo"
        assert ctx.seq == "010"
        assert ctx.shot == "0010"

    def test_round_trip_with_inheritance(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("show_base", "V:/shows/<show>")
        resolver.register("seq_base", "seq/<seq>", base="show_base")
        resolver.register("shot", "<shot>/work/<task>", base="seq_base")

        original_ctx = VFXContext(show="demo", seq="010", shot="0010", task="anim")
        path = resolver.resolve("shot", original_ctx)
        parsed_ctx = resolver.parse_path(path)

        assert parsed_ctx.show == original_ctx.show
        assert parsed_ctx.seq == original_ctx.seq
        assert parsed_ctx.shot == original_ctx.shot
        assert parsed_ctx.task == original_ctx.task

    def test_inheritance_with_variables(self) -> None:
        resolver = PathResolver(VFXContext, variables={"ROOT": "/mnt/storage"})
        resolver.register("show_base", "{ROOT}/shows/<show>")
        resolver.register("seq_base", "seq/<seq>", base="show_base")

        ctx = VFXContext(show="demo", seq="010")
        path = resolver.resolve("seq_base", ctx)

        assert path == Path("/mnt/storage/shows/demo/seq/010")

    def test_load_from_json_with_inheritance(self, tmp_path: Path) -> None:
        json_file = tmp_path / "templates.json"
        templates = {
            "show_base": "V:/shows/<show>",
            "seq_base": {"pattern": "seq/<seq>", "base": "show_base"},
            "shot": {"pattern": "<shot>/work", "base": "seq_base"},
        }

        import json

        with open(json_file, "w") as f:
            json.dump(templates, f)

        resolver = PathResolver(VFXContext)
        resolver.load_from_json(json_file)

        ctx = VFXContext(show="demo", seq="010", shot="0010")
        path = resolver.resolve("shot", ctx)

        assert path == Path("V:/shows/demo/seq/010/0010/work")

    def test_find_matches_with_inheritance(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("show_base", "V:/shows/<show>")
        resolver.register("seq_base", "seq/<seq>", base="show_base")
        resolver.register("shot_full", "<shot>/work/<task>", base="seq_base")
        resolver.register("shot_simple", "<shot>/work", base="seq_base")

        ctx = VFXContext(show="demo", seq="010", shot="0010")
        matches = resolver.find_matches(ctx)

        assert "shot_simple" in matches
        assert "shot_full" not in matches


class TestCompositeResolverInheritance:
    def test_simple_inheritance(self) -> None:
        composite = CompositeResolver()
        composite.register(VFXContext, "base", "V:/shows/<show>")
        composite.register(VFXContext, "seq", "seq/<seq>", base="base")

        ctx = VFXContext(show="demo", seq="010")
        path = composite.resolve("seq", ctx)

        assert path == Path("V:/shows/demo/seq/010")

    def test_multi_level_inheritance(self) -> None:
        composite = CompositeResolver()
        composite.register(VFXContext, "show_base", "V:/shows/<show>")
        composite.register(VFXContext, "seq_base", "seq/<seq>", base="show_base")
        composite.register(VFXContext, "shot", "<shot>/work", base="seq_base")

        ctx = VFXContext(show="demo", seq="010", shot="0010")
        path = composite.resolve("shot", ctx)

        assert path == Path("V:/shows/demo/seq/010/0010/work")

    def test_multiple_context_types_with_inheritance(self) -> None:
        composite = CompositeResolver()

        # VFX context templates
        composite.register(VFXContext, "vfx_base", "V:/shows/<show>")
        composite.register(VFXContext, "vfx_seq", "seq/<seq>", base="vfx_base")

        # Asset context templates
        composite.register(AssetContext, "asset_base", "V:/assets/<category>")
        composite.register(
            AssetContext, "asset_variant", "<asset>/<variant>", base="asset_base"
        )

        vfx_ctx = VFXContext(show="demo", seq="010")
        asset_ctx = AssetContext(category="props", asset="table", variant="damaged")

        vfx_path = composite.resolve("vfx_seq", vfx_ctx)
        asset_path = composite.resolve("asset_variant", asset_ctx)

        assert vfx_path == Path("V:/shows/demo/seq/010")
        assert asset_path == Path("V:/assets/props/table/damaged")

    def test_inheritance_with_variables(self) -> None:
        composite = CompositeResolver(variables={"ROOT": "/mnt/storage"})
        composite.register(VFXContext, "show_base", "{ROOT}/shows/<show>")
        composite.register(VFXContext, "seq_base", "seq/<seq>", base="show_base")

        ctx = VFXContext(show="demo", seq="010")
        path = composite.resolve("seq_base", ctx)

        assert path == Path("/mnt/storage/shows/demo/seq/010")

    def test_parse_path_with_inheritance(self) -> None:
        composite = CompositeResolver()
        composite.register(VFXContext, "show_base", "V:/shows/<show>")
        composite.register(VFXContext, "seq_base", "seq/<seq>", base="show_base")
        composite.register(VFXContext, "shot", "<shot>/work", base="seq_base")

        path = Path("V:/shows/demo/seq/010/0010/work")
        ctx = composite.parse_path(VFXContext, path)

        assert ctx is not None
        assert ctx.show == "demo"
        assert ctx.seq == "010"
        assert ctx.shot == "0010"

    def test_round_trip_with_inheritance(self) -> None:
        composite = CompositeResolver()
        composite.register(VFXContext, "show_base", "V:/shows/<show>")
        composite.register(VFXContext, "seq_base", "seq/<seq>", base="show_base")
        composite.register(VFXContext, "shot", "<shot>/work/<dcc>", base="seq_base")

        original_ctx = VFXContext(show="demo", seq="010", shot="0010", dcc="maya")
        path = composite.resolve("shot", original_ctx)
        parsed_ctx = composite.parse_path(VFXContext, path)

        assert parsed_ctx.show == original_ctx.show
        assert parsed_ctx.seq == original_ctx.seq
        assert parsed_ctx.shot == original_ctx.shot
        assert parsed_ctx.dcc == original_ctx.dcc

    def test_base_template_not_found(self) -> None:
        composite = CompositeResolver()

        with pytest.raises(KeyError, match="Base template 'nonexistent' not found"):
            composite.register(VFXContext, "child", "<seq>", base="nonexistent")

    def test_isolated_inheritance_per_context_type(self) -> None:
        composite = CompositeResolver()

        # VFX has a "base" template
        composite.register(VFXContext, "base", "V:/shows/<show>")
        composite.register(VFXContext, "seq", "seq/<seq>", base="base")

        # Asset also has a "base" template (different from VFX base)
        composite.register(AssetContext, "base", "V:/assets/<category>")
        composite.register(AssetContext, "variant", "<asset>/<variant>", base="base")

        vfx_ctx = VFXContext(show="demo", seq="010")
        asset_ctx = AssetContext(category="props", asset="table", variant="clean")

        vfx_path = composite.resolve("seq", vfx_ctx)
        asset_path = composite.resolve("variant", asset_ctx)

        # Each should use its own context's base template
        assert vfx_path == Path("V:/shows/demo/seq/010")
        assert asset_path == Path("V:/assets/props/table/clean")
