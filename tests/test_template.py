import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest

from templar import PathResolver
from templar import PathTemplate


@dataclass
class ExampleContext(object):
    show: Optional[str] = None
    episode: Optional[str] = None
    seq: Optional[str] = None
    shot: Optional[str] = None
    category: Optional[str] = None
    asset: Optional[str] = None
    dcc: Optional[str] = None
    file_type: Optional[str] = None
    file_name: Optional[str] = None


class TestPathTemplate:
    def test_extract_tokens(self) -> None:
        template = PathTemplate("V:/shows/<show>/seq/<seq>/<shot>")
        assert template.tokens == {"show", "seq", "shot"}

    def test_format_success(self) -> None:
        template = PathTemplate("V:/shows/<show>/seq/<seq>")
        ctx = ExampleContext(show="demo", seq="010")
        result = template.format(ctx)
        assert result == "V:/shows/demo/seq/010"

    def test_format_missing_token(self) -> None:
        template = PathTemplate("V:/shows/<show>/seq/<seq>")
        ctx = ExampleContext(show="demo")
        with pytest.raises(ValueError, match="Missing required tokens: {'seq'}"):
            template.format(ctx)

    def test_can_format_true(self) -> None:
        template = PathTemplate("V:/shows/<show>/seq/<seq>")
        ctx = ExampleContext(show="demo", seq="010")
        assert template.can_format(ctx) is True

    def test_can_format_false(self) -> None:
        template = PathTemplate("V:/shows/<show>/seq/<seq>")
        ctx = ExampleContext(show="demo")
        assert template.can_format(ctx) is False

    def test_can_format_with_extra_fields(self) -> None:
        template = PathTemplate("V:/shows/<show>")
        ctx = ExampleContext(show="demo", seq="010", shot="0010")
        assert template.can_format(ctx) is True


class TestPathResolver:
    def test_register_template(self) -> None:
        resolver = PathResolver(ExampleContext)
        resolver.register("test", "V:/shows/<show>")
        assert "test" in resolver.templates
        assert resolver.templates["test"].pattern == "V:/shows/<show>"

    def test_resolve_success(self) -> None:
        resolver = PathResolver(ExampleContext)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>")
        ctx = ExampleContext(show="demo", seq="010", shot="0010")
        result = resolver.resolve("shot", ctx)
        assert result == Path("V:/shows/demo/seq/010/0010")

    def test_resolve_missing_template(self) -> None:
        resolver = PathResolver(ExampleContext)
        ctx = ExampleContext(show="demo")
        with pytest.raises(KeyError, match="Template 'nonexistent' not registered"):
            resolver.resolve("nonexistent", ctx)

    def test_resolve_any_first_match(self) -> None:
        resolver = PathResolver(ExampleContext)
        resolver.register("episodic", "V:/shows/<show>/seq/<episode>/<seq>")
        resolver.register("flat", "V:/shows/<show>/seq/<seq>")

        ctx = ExampleContext(show="demo", seq="010")
        result = resolver.resolve_any(ctx)
        assert result == Path("V:/shows/demo/seq/010")

    def test_resolve_any_with_prefer(self) -> None:
        resolver = PathResolver(ExampleContext)
        resolver.register("episodic", "V:/shows/<show>/seq/<episode>/<seq>")
        resolver.register("flat", "V:/shows/<show>/seq/<seq>")

        ctx = ExampleContext(show="demo", episode="e01", seq="010")
        result = resolver.resolve_any(ctx, prefer=["episodic", "flat"])
        assert result == Path("V:/shows/demo/seq/e01/010")

    def test_resolve_any_no_match(self) -> None:
        resolver = PathResolver(ExampleContext)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>")

        ctx = ExampleContext(show="demo")
        result = resolver.resolve_any(ctx)
        assert result is None

    def test_find_matches(self) -> None:
        resolver = PathResolver(ExampleContext)
        resolver.register("episodic", "V:/shows/<show>/seq/<episode>/<seq>")
        resolver.register("flat", "V:/shows/<show>/seq/<seq>")
        resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>")

        ctx = ExampleContext(show="demo", seq="010")
        matches = resolver.find_matches(ctx)
        # episodic requires <episode> which ctx doesn't have
        assert set(matches) == {"flat"}

    def test_parse_path_success(self) -> None:
        resolver = PathResolver(ExampleContext)
        resolver.register(
            "shot", "V:/shows/<show>/seq/<seq>/<shot>/__pub__/<dcc>/<file_type>"
        )

        path = Path("V:/shows/demo/seq/010/0010/__pub__/maya/mb")
        ctx = resolver.parse_path(path)

        assert ctx is not None
        assert ctx.show == "demo"
        assert ctx.seq == "010"
        assert ctx.shot == "0010"
        assert ctx.dcc == "maya"
        assert ctx.file_type == "mb"

    def test_parse_path_no_match(self) -> None:
        resolver = PathResolver(ExampleContext)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>")

        path = Path("V:/completely/different/path")
        ctx = resolver.parse_path(path)
        assert ctx is None

    def test_parse_path_with_filename(self) -> None:
        resolver = PathResolver(ExampleContext)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>/<file_name>.<file_type>")

        path = Path("V:/shows/demo/seq/010/scene_v001.ma")
        ctx = resolver.parse_path(path)

        assert ctx is not None
        assert ctx.show == "demo"
        assert ctx.seq == "010"
        assert ctx.file_name == "scene_v001"
        assert ctx.file_type == "ma"

    def test_parse_path_auto_extract_filename(self) -> None:
        resolver = PathResolver(ExampleContext)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>/__pub__/<dcc>")

        path = Path("V:/shows/demo/seq/010/0010/__pub__/maya")
        ctx = resolver.parse_path(path)

        assert ctx is not None
        assert ctx.show == "demo"
        assert ctx.seq == "010"
        assert ctx.shot == "0010"
        assert ctx.dcc == "maya"

    def test_round_trip(self) -> None:
        resolver = PathResolver(ExampleContext)
        resolver.register(
            "shot", "V:/shows/<show>/seq/<seq>/<shot>/__pub__/<dcc>/<file_type>"
        )

        original = Path("V:/shows/demo/seq/010/0010/__pub__/maya/mb")
        ctx = resolver.parse_path(original)
        reconstructed = resolver.resolve("shot", ctx)

        assert original == reconstructed

    def test_load_from_json(self, tmp_path: Path) -> None:
        json_file = tmp_path / "templates.json"
        templates = {
            "shot": "V:/shows/<show>/seq/<seq>/<shot>",
            "asset": "V:/shows/<show>/asset/<asset>",
        }

        with open(json_file, "w") as f:
            json.dump(templates, f)

        resolver = PathResolver(ExampleContext)
        resolver.load_from_json(json_file)

        assert "shot" in resolver.templates
        assert "asset" in resolver.templates
        assert resolver.templates["shot"].pattern == "V:/shows/<show>/seq/<seq>/<shot>"

    def test_windows_and_posix_paths(self) -> None:
        resolver = PathResolver(ExampleContext)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>")

        # Both forward and backslash should work
        path1 = Path("V:/shows/demo/seq/010")
        path2 = Path("V:\\shows\\demo\\seq\\010")

        ctx1 = resolver.parse_path(path1)
        ctx2 = resolver.parse_path(path2)

        assert ctx1.show == ctx2.show == "demo"
        assert ctx1.seq == ctx2.seq == "010"


class TestEdgeCases:
    def test_empty_context(self) -> None:
        resolver = PathResolver(ExampleContext)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>")

        ctx = ExampleContext()
        matches = resolver.find_matches(ctx)
        assert matches == []

    def test_special_characters_in_values(self) -> None:
        resolver = PathResolver(ExampleContext)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>")

        ctx = ExampleContext(show="demo_2024", seq="010A")
        result = resolver.resolve("shot", ctx)
        assert result == Path("V:/shows/demo_2024/seq/010A")

    def test_underscore_in_path(self) -> None:
        resolver = PathResolver(ExampleContext)
        resolver.register("shot", "V:/shows/<show>/__pub__/<seq>")

        path = Path("V:/shows/demo/__pub__/010")
        ctx = resolver.parse_path(path)

        assert ctx.show == "demo"
        assert ctx.seq == "010"
