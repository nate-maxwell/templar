from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from templar import PathResolver

import pytest


@dataclass
class VFXContext(object):
    show: Optional[str] = None
    episode: Optional[str] = None
    seq: Optional[str] = None
    shot: Optional[str] = None
    version: Optional[str] = None
    task: Optional[str] = None


class TestTokenFormatters:
    def test_padding_formatter(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("padded", "V:/shows/<show>/seq/<seq:03>/<shot:04>")

        ctx = VFXContext(show="demo", seq="10", shot="5")
        path = resolver.resolve("padded", ctx)

        assert path == Path("V:/shows/demo/seq/010/0005")

    def test_padding_already_long_enough(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("padded", "V:/shows/<show>/seq/<seq:03>")

        ctx = VFXContext(show="demo", seq="1000")
        path = resolver.resolve("padded", ctx)

        assert path == Path("V:/shows/demo/seq/1000")

    def test_padding_non_numeric_value(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("padded", "V:/shows/<show:04>/seq/<seq>")

        ctx = VFXContext(show="demo", seq="010")
        path = resolver.resolve("padded", ctx)

        # Non-numeric values aren't padded
        assert path == Path("V:/shows/demo/seq/010")

    def test_upper_formatter(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("upper", "V:/shows/<show:upper>/seq/<seq>")

        ctx = VFXContext(show="demo", seq="010")
        path = resolver.resolve("upper", ctx)

        assert path == Path("V:/shows/DEMO/seq/010")

    def test_lower_formatter(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("lower", "V:/shows/<show:lower>/seq/<seq>")

        ctx = VFXContext(show="DEMO", seq="010")
        path = resolver.resolve("lower", ctx)

        assert path == Path("V:/shows/demo/seq/010")

    def test_title_formatter(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("title", "V:/shows/<show:title>/seq/<seq>")

        ctx = VFXContext(show="demo show", seq="010")
        path = resolver.resolve("title", ctx)

        assert path == Path("V:/shows/Demo Show/seq/010")

    def test_default_formatter_with_value(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("default", "V:/shows/<show>/ep/<episode:default=pilot>")

        ctx = VFXContext(show="demo", episode="s01e01")
        path = resolver.resolve("default", ctx)

        assert path == Path("V:/shows/demo/ep/s01e01")

    def test_default_formatter_without_value(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("default", "V:/shows/<show>/ep/<episode:default=pilot>")

        ctx = VFXContext(show="demo")
        path = resolver.resolve("default", ctx)

        assert path == Path("V:/shows/demo/ep/pilot")

    def test_multiple_formatters_same_template(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register(
            "multi", "V:/shows/<show:upper>/seq/<seq:03>/shot/<shot:04>/v<version:03>"
        )

        ctx = VFXContext(show="demo", seq="5", shot="10", version="2")
        path = resolver.resolve("multi", ctx)

        assert path == Path("V:/shows/DEMO/seq/005/shot/0010/v002")

    def test_can_format_with_default(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("default", "V:/shows/<show>/ep/<episode:default=pilot>")

        # Should match even without episode
        ctx = VFXContext(show="demo")
        assert resolver.templates["default"].can_format(ctx) is True

    def test_can_format_without_default(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("no_default", "V:/shows/<show>/ep/<episode>")

        ctx = VFXContext(show="demo")
        assert resolver.templates["no_default"].can_format(ctx) is False

    def test_find_matches_with_defaults(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("with_episode", "V:/shows/<show>/ep/<episode>")
        resolver.register("with_default", "V:/shows/<show>/ep/<episode:default=pilot>")

        ctx = VFXContext(show="demo")
        matches = resolver.find_matches(ctx)

        assert "with_default" in matches
        assert "with_episode" not in matches

    def test_formatters_with_inheritance(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("base", "V:/shows/<show:upper>")
        resolver.register("seq", "seq/<seq:03>", base="base")

        ctx = VFXContext(show="demo", seq="5")
        path = resolver.resolve("seq", ctx)

        assert path == Path("V:/shows/DEMO/seq/005")

    def test_default_with_inheritance(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("base", "V:/shows/<show>")
        resolver.register("ep", "ep/<episode:default=pilot>", base="base")

        ctx = VFXContext(show="demo")
        path = resolver.resolve("ep", ctx)

        assert path == Path("V:/shows/demo/ep/pilot")

    def test_combination_padding_and_case(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register(
            "combo", "V:/shows/<show:upper>/SEQ_<seq:04>/<shot:04>/v<version:03>"
        )

        ctx = VFXContext(show="supernatural", seq="10", shot="100", version="5")
        path = resolver.resolve("combo", ctx)

        assert path == Path("V:/shows/SUPERNATURAL/SEQ_0010/0100/v005")

    def test_missing_token_with_formatter(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("padded", "V:/shows/<show>/seq/<seq:03>")

        ctx = VFXContext(show="demo")

        with pytest.raises(ValueError, match="Missing required tokens: {'seq'}"):
            resolver.resolve("padded", ctx)

    def test_parse_path_ignores_formatters(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("formatted", "V:/shows/<show:upper>/seq/<seq:03>/<shot:04>")

        # Path has formatted values
        path = Path("V:/shows/DEMO/seq/010/0005")
        ctx = resolver.parse_path(path)

        # Values are extracted as-is (formatters don't affect parsing)
        assert ctx is not None
        assert ctx.show == "DEMO"
        assert ctx.seq == "010"
        assert ctx.shot == "0005"

    def test_unknown_formatter_ignored(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("unknown", "V:/shows/<show:unknown>/seq/<seq>")

        ctx = VFXContext(show="demo", seq="010")
        path = resolver.resolve("unknown", ctx)

        # Unknown formatters are ignored
        assert path == Path("V:/shows/demo/seq/010")

    def test_default_with_special_characters(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("special", "V:/shows/<show>/task/<task:default=pre_vis>")

        ctx = VFXContext(show="demo")
        path = resolver.resolve("special", ctx)

        assert path == Path("V:/shows/demo/task/pre_vis")

    def test_multiple_defaults_in_template(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register(
            "multi_default",
            "V:/shows/<show>/ep/<episode:default=pilot>/task/<task:default=anim>",
        )

        ctx = VFXContext(show="demo")
        path = resolver.resolve("multi_default", ctx)

        assert path == Path("V:/shows/demo/ep/pilot/task/anim")

    def test_resolve_any_with_defaults(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("full", "V:/shows/<show>/ep/<episode>/seq/<seq>")
        resolver.register("partial", "V:/shows/<show>/ep/<episode:default=pilot>")

        ctx = VFXContext(show="demo")
        path = resolver.resolve_any(ctx, prefer=["full", "partial"])

        # Should match partial because it has a default
        assert path == Path("V:/shows/demo/ep/pilot")

    def test_formatters_with_variables(self) -> None:
        resolver = PathResolver(VFXContext, variables={"ROOT": "/mnt/storage"})
        resolver.register("combo", "{ROOT}/shows/<show:upper>/seq/<seq:03>")

        ctx = VFXContext(show="demo", seq="5")
        path = resolver.resolve("combo", ctx)

        assert path == Path("/mnt/storage/shows/DEMO/seq/005")
