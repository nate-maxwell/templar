import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from typing import Callable

from templar import PathResolver
from templar import CompositeResolver


def remove_spaces(value: str) -> str:
    """Remove all spaces."""
    return value.replace(" ", "")


def spaces_to_underscores(value: str) -> str:
    """Convert spaces to underscores."""
    return value.replace(" ", "_")


def remove_illegal_chars(value: str) -> str:
    """Remove characters illegal in Windows paths."""
    return re.sub(r'[<>:"|?*\x00-\x1f]', "", value)


def alphanumeric_only(value: str) -> str:
    """Keep only alphanumeric characters and underscores."""
    return re.sub(r"[^\w]", "", value)


def lowercase_alphanum(value: str) -> str:
    """Convert to lowercase and keep only alphanumeric + underscores."""
    return re.sub(r"[^\w]", "", value.lower())


def safe_filename(value: str) -> str:
    """Make value safe for filenames: remove illegal chars, convert spaces."""
    value = re.sub(r'[<>:"|?*\x00-\x1f]', "", value)
    value = value.replace(" ", "_")
    return value.strip("._")


def limit_length(max_len: int) -> Callable[[str], str]:
    """Create a normalizer that limits string length."""

    def normalizer(value: str) -> str:
        return value[:max_len]

    return normalizer


@dataclass
class VFXContext(object):
    show: Optional[str] = None
    seq: Optional[str] = None
    shot: Optional[str] = None
    task: Optional[str] = None
    version: Optional[str] = None


@dataclass
class AssetContext(object):
    category: Optional[str] = None
    asset: Optional[str] = None
    variant: Optional[str] = None


class TestNormalizers:
    def test_single_normalizer(self) -> None:
        normalizers = {"show": spaces_to_underscores}
        resolver = PathResolver(VFXContext, normalizers=normalizers)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>")

        ctx = VFXContext(show="My Show", seq="010")
        path = resolver.resolve("shot", ctx)

        assert path == Path("V:/shows/My_Show/seq/010")

    def test_multiple_normalizers(self) -> None:
        normalizers = {"show": spaces_to_underscores, "shot": alphanumeric_only}
        resolver = PathResolver(VFXContext, normalizers=normalizers)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>")

        ctx = VFXContext(show="My Show", seq="010", shot="shot-with-dashes")
        path = resolver.resolve("shot", ctx)

        assert path == Path("V:/shows/My_Show/seq/010/shotwithdashes")

    def test_remove_illegal_chars(self) -> None:
        normalizers = {"shot": remove_illegal_chars}
        resolver = PathResolver(VFXContext, normalizers=normalizers)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>")

        ctx = VFXContext(show="demo", seq="010", shot="shot:with|illegal*chars")
        path = resolver.resolve("shot", ctx)

        assert path == Path("V:/shows/demo/seq/010/shotwithillegalchars")

    def test_safe_filename_normalizer(self) -> None:
        normalizers = {"shot": safe_filename}
        resolver = PathResolver(VFXContext, normalizers=normalizers)
        resolver.register("shot", "V:/shows/<show>/<shot>")

        ctx = VFXContext(show="demo", shot="shot: with spaces|and*bad?chars")
        path = resolver.resolve("shot", ctx)

        assert path == Path("V:/shows/demo/shot_with_spacesandbadchars")

    def test_lowercase_normalizer(self) -> None:
        normalizers = {"show": lowercase_alphanum}
        resolver = PathResolver(VFXContext, normalizers=normalizers)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>")

        ctx = VFXContext(show="My BIG Show!", seq="010")
        path = resolver.resolve("shot", ctx)

        assert path == Path("V:/shows/mybigshow/seq/010")

    def test_normalizer_with_formatter(self) -> None:
        normalizers = {"show": spaces_to_underscores}
        resolver = PathResolver(VFXContext, normalizers=normalizers)
        resolver.register("shot", "V:/shows/<show:upper>/seq/<seq:03>")

        ctx = VFXContext(show="my show", seq="5")
        path = resolver.resolve("shot", ctx)

        # Normalizer runs first, then formatter
        assert path == Path("V:/shows/MY_SHOW/seq/005")

    def test_limit_length_normalizer(self) -> None:
        normalizers = {"show": limit_length(5)}
        resolver = PathResolver(VFXContext, normalizers=normalizers)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>")

        ctx = VFXContext(show="verylongshowname", seq="010")
        path = resolver.resolve("shot", ctx)

        assert path == Path("V:/shows/veryl/seq/010")

    def test_custom_normalizer(self) -> None:
        def custom_normalizer(value: str) -> str:
            """Custom: uppercase first letter of each word, remove spaces."""
            words = value.split()
            return "".join(word.capitalize() for word in words)

        normalizers = {"show": custom_normalizer}
        resolver = PathResolver(VFXContext, normalizers=normalizers)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>")

        ctx = VFXContext(show="my cool show", seq="010")
        path = resolver.resolve("shot", ctx)

        assert path == Path("V:/shows/MyCoolShow/seq/010")

    def test_normalizer_with_inheritance(self) -> None:
        normalizers = {"show": spaces_to_underscores}
        resolver = PathResolver(VFXContext, normalizers=normalizers)
        resolver.register("base", "V:/shows/<show>")
        resolver.register("seq", "seq/<seq>", base="base")

        ctx = VFXContext(show="My Show", seq="010")
        path = resolver.resolve("seq", ctx)

        assert path == Path("V:/shows/My_Show/seq/010")

    def test_normalizer_does_not_affect_parsing(self) -> None:
        normalizers = {"show": spaces_to_underscores}
        resolver = PathResolver(VFXContext, normalizers=normalizers)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>")

        # Parse a path with underscores
        path = Path("V:/shows/My_Show/seq/010")
        ctx = resolver.parse_path(path)

        # Parsing extracts as-is (normalizers don't affect parsing)
        assert ctx is not None
        assert ctx.show == "My_Show"
        assert ctx.seq == "010"

    def test_no_normalizers(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>")

        ctx = VFXContext(show="My Show", seq="010")
        path = resolver.resolve("shot", ctx)

        # No normalizers, values used as-is
        assert path == Path("V:/shows/My Show/seq/010")

    def test_normalizer_only_applied_to_specific_tokens(self) -> None:
        normalizers = {"show": spaces_to_underscores}
        resolver = PathResolver(VFXContext, normalizers=normalizers)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>")

        ctx = VFXContext(show="My Show", seq="010", shot="my shot")
        path = resolver.resolve("shot", ctx)

        # Only show gets normalized
        assert path == Path("V:/shows/My_Show/seq/010/my shot")

    def test_multiple_templates_same_normalizers(self) -> None:
        normalizers = {"show": spaces_to_underscores, "shot": alphanumeric_only}
        resolver = PathResolver(VFXContext, normalizers=normalizers)
        resolver.register("work", "V:/shows/<show>/__work__/<shot>")
        resolver.register("pub", "V:/shows/<show>/__pub__/<shot>")

        ctx = VFXContext(show="My Show", shot="shot-01")

        work_path = resolver.resolve("work", ctx)
        pub_path = resolver.resolve("pub", ctx)

        assert work_path == Path("V:/shows/My_Show/__work__/shot01")
        assert pub_path == Path("V:/shows/My_Show/__pub__/shot01")

    def test_normalizer_with_default_formatter(self) -> None:
        normalizers = {"task": spaces_to_underscores}
        resolver = PathResolver(VFXContext, normalizers=normalizers)
        resolver.register("shot", "V:/shows/<show>/<task:default=layout>")

        # Without task - default should NOT be normalized
        ctx = VFXContext(show="demo")
        path = resolver.resolve("shot", ctx)
        assert path == Path("V:/shows/demo/layout")

        # With task - should be normalized
        ctx = VFXContext(show="demo", task="my task")
        path = resolver.resolve("shot", ctx)
        assert path == Path("V:/shows/demo/my_task")

    def test_chained_normalizers(self) -> None:
        def chain(*funcs: Callable[[str], str]) -> Callable[[str], str]:
            """Chain multiple normalizers together."""

            def chained(value: str) -> str:
                for func in funcs:
                    value = func(value)
                return value

            return chained

        normalizers = {
            "show": chain(remove_illegal_chars, spaces_to_underscores, str.lower)
        }
        resolver = PathResolver(VFXContext, normalizers=normalizers)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>")

        ctx = VFXContext(show="My Show: Edition*", seq="010")
        path = resolver.resolve("shot", ctx)

        assert path == Path("V:/shows/my_show_edition/seq/010")


class TestCompositeResolverNormalizers:
    def test_normalizers_shared_across_context_types(self) -> None:
        normalizers = {"show": spaces_to_underscores, "category": alphanumeric_only}
        composite = CompositeResolver(normalizers=normalizers)

        composite.register(VFXContext, "shot", "V:/shows/<show>/seq/<seq>")
        composite.register(AssetContext, "asset", "V:/assets/<category>/<asset>")

        vfx_ctx = VFXContext(show="My Show", seq="010")
        asset_ctx = AssetContext(category="props-main", asset="table")

        vfx_path = composite.resolve("shot", vfx_ctx)
        asset_path = composite.resolve("asset", asset_ctx)

        assert vfx_path == Path("V:/shows/My_Show/seq/010")
        assert asset_path == Path("V:/assets/propsmain/table")

    def test_normalizers_with_variables(self) -> None:
        normalizers = {"show": spaces_to_underscores}
        composite = CompositeResolver(
            variables={"ROOT": "/mnt/storage"}, normalizers=normalizers
        )

        composite.register(VFXContext, "shot", "{ROOT}/shows/<show>/seq/<seq>")

        ctx = VFXContext(show="My Show", seq="010")
        path = composite.resolve("shot", ctx)

        assert path == Path("/mnt/storage/shows/My_Show/seq/010")

    def test_different_context_types_different_tokens(self) -> None:
        normalizers = {"show": spaces_to_underscores, "asset": alphanumeric_only}
        composite = CompositeResolver(normalizers=normalizers)

        composite.register(VFXContext, "shot", "V:/shows/<show>")
        composite.register(AssetContext, "asset", "V:/assets/<asset>")

        vfx_ctx = VFXContext(show="My Show")
        asset_ctx = AssetContext(asset="my-asset")

        vfx_path = composite.resolve("shot", vfx_ctx)
        asset_path = composite.resolve("asset", asset_ctx)

        assert vfx_path == Path("V:/shows/My_Show")
        assert asset_path == Path("V:/assets/myasset")
