from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest

from templar import CompositeResolver


@dataclass
class VFXContext(object):
    show: Optional[str] = None
    seq: Optional[str] = None
    shot: Optional[str] = None
    dcc: Optional[str] = None


@dataclass
class GameContext(object):
    project: Optional[str] = None
    level: Optional[str] = None
    asset: Optional[str] = None


class TestCompositeResolver:
    def test_register_single_context_type(self) -> None:
        composite = CompositeResolver()
        composite.register(VFXContext, "shot", "V:/shows/<show>/seq/<seq>/<shot>")

        assert VFXContext in composite._registry
        assert "shot" in composite._registry[VFXContext].templates

    def test_register_multiple_context_types(self) -> None:
        composite = CompositeResolver()
        composite.register(VFXContext, "shot", "V:/shows/<show>/seq/<seq>")
        composite.register(GameContext, "level", "projects/<project>/levels/<level>")

        assert VFXContext in composite._registry
        assert GameContext in composite._registry
        assert len(composite._registry) == 2

    def test_register_multiple_templates_same_context(self) -> None:
        composite = CompositeResolver()
        composite.register(VFXContext, "shot", "V:/shows/<show>/seq/<seq>")
        composite.register(VFXContext, "asset", "V:/shows/<show>/assets/<asset>")

        assert len(composite._registry[VFXContext].templates) == 2

    def test_resolve_correct_context_type(self) -> None:
        composite = CompositeResolver()
        composite.register(VFXContext, "shot", "V:/shows/<show>/seq/<seq>/<shot>")
        composite.register(GameContext, "level", "projects/<project>/levels/<level>")

        vfx_ctx = VFXContext(show="demo", seq="010", shot="0010")
        game_ctx = GameContext(project="rpg", level="castle")

        vfx_path = composite.resolve("shot", vfx_ctx)
        game_path = composite.resolve("level", game_ctx)

        assert vfx_path == Path("V:/shows/demo/seq/010/0010")
        assert game_path == Path("projects/rpg/levels/castle")

    def test_resolve_any(self) -> None:
        composite = CompositeResolver()
        composite.register(
            VFXContext, "shot_full", "V:/shows/<show>/seq/<seq>/<shot>/<dcc>"
        )
        composite.register(
            VFXContext, "shot_simple", "V:/shows/<show>/seq/<seq>/<shot>"
        )

        ctx = VFXContext(show="demo", seq="010", shot="0010")
        path = composite.resolve_any(ctx)

        assert path == Path("V:/shows/demo/seq/010/0010")

    def test_resolve_any_with_prefer(self) -> None:
        composite = CompositeResolver()
        composite.register(
            VFXContext, "shot_full", "V:/shows/<show>/seq/<seq>/<shot>/<dcc>"
        )
        composite.register(
            VFXContext, "shot_simple", "V:/shows/<show>/seq/<seq>/<shot>"
        )

        ctx = VFXContext(show="demo", seq="010", shot="0010", dcc="maya")
        path = composite.resolve_any(ctx, prefer=["shot_full", "shot_simple"])

        assert path == Path("V:/shows/demo/seq/010/0010/maya")

    def test_find_matches(self) -> None:
        composite = CompositeResolver()
        composite.register(
            VFXContext, "shot_full", "V:/shows/<show>/seq/<seq>/<shot>/<dcc>"
        )
        composite.register(
            VFXContext, "shot_simple", "V:/shows/<show>/seq/<seq>/<shot>"
        )

        ctx = VFXContext(show="demo", seq="010", shot="0010")
        matches = composite.find_matches(ctx)

        assert "shot_simple" in matches
        assert "shot_full" not in matches

    def test_parse_path(self) -> None:
        composite = CompositeResolver()
        composite.register(VFXContext, "shot", "V:/shows/<show>/seq/<seq>/<shot>")

        path = Path("V:/shows/demo/seq/010/0010")
        ctx = composite.parse_path(VFXContext, path)

        assert ctx is not None
        assert ctx.show == "demo"
        assert ctx.seq == "010"
        assert ctx.shot == "0010"

    def test_parse_path_unregistered_context_type(self) -> None:
        composite = CompositeResolver()

        path = Path("V:/shows/demo/seq/010")
        with pytest.raises(
            ValueError, match="Context type .* is not currently registered"
        ):
            composite.parse_path(VFXContext, path)

    def test_parse_path_correct_context_type(self) -> None:
        composite = CompositeResolver()
        composite.register(VFXContext, "shot", "V:/shows/<show>/seq/<seq>")
        composite.register(GameContext, "level", "projects/<project>/levels/<level>")

        vfx_path = Path("V:/shows/demo/seq/010")
        game_path = Path("projects/rpg/levels/castle")

        vfx_ctx = composite.parse_path(VFXContext, vfx_path)
        game_ctx = composite.parse_path(GameContext, game_path)

        assert isinstance(vfx_ctx, VFXContext)
        assert isinstance(game_ctx, GameContext)
        assert vfx_ctx.show == "demo"
        assert game_ctx.level == "castle"

    def test_round_trip(self) -> None:
        composite = CompositeResolver()
        composite.register(VFXContext, "shot", "V:/shows/<show>/seq/<seq>/<shot>")

        original_ctx = VFXContext(show="demo", seq="010", shot="0010")
        path = composite.resolve("shot", original_ctx)
        parsed_ctx = composite.parse_path(VFXContext, path)

        assert parsed_ctx.show == original_ctx.show
        assert parsed_ctx.seq == original_ctx.seq
        assert parsed_ctx.shot == original_ctx.shot

    def test_isolated_context_types(self) -> None:
        composite = CompositeResolver()
        composite.register(VFXContext, "template", "V:/shows/<show>")
        composite.register(GameContext, "template", "projects/<project>")

        vfx_ctx = VFXContext(show="demo")
        game_ctx = GameContext(project="rpg")

        vfx_path = composite.resolve("template", vfx_ctx)
        game_path = composite.resolve("template", game_ctx)

        assert vfx_path == Path("V:/shows/demo")
        assert game_path == Path("projects/rpg")
