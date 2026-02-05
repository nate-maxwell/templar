from dataclasses import dataclass
from typing import Optional
from templar import PathResolver

import pytest


@dataclass
class VFXContext(object):
    show: Optional[str] = None
    seq: Optional[str] = None
    shot: Optional[str] = None
    task: Optional[str] = None
    version: Optional[str] = None
    episode: Optional[str] = None


class TestValidation:
    def test_validate_all_tokens_present(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>")

        ctx = VFXContext(show="demo", seq="010", shot="0010")
        is_valid, missing = resolver.validate("shot", ctx)

        assert is_valid is True
        assert missing == []

    def test_validate_missing_one_token(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>")

        ctx = VFXContext(show="demo", seq="010")
        is_valid, missing = resolver.validate("shot", ctx)

        assert is_valid is False
        assert "shot" in missing

    def test_validate_missing_multiple_tokens(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>")

        ctx = VFXContext(show="demo")
        is_valid, missing = resolver.validate("shot", ctx)

        assert is_valid is False
        assert "seq" in missing
        assert "shot" in missing

    def test_validate_all_tokens_missing(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>")

        ctx = VFXContext()
        is_valid, missing = resolver.validate("shot", ctx)

        assert is_valid is False
        assert set(missing) == {"show", "seq", "shot"}

    def test_validate_with_extra_tokens(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>")

        ctx = VFXContext(show="demo", seq="010", shot="0010", task="anim")
        is_valid, missing = resolver.validate("shot", ctx)

        # Extra tokens don't matter
        assert is_valid is True
        assert missing == []

    def test_validate_with_default_formatter(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("shot", "V:/shows/<show>/ep/<episode:default=pilot>")

        # Episode not provided, but has default
        ctx = VFXContext(show="demo")
        is_valid, missing = resolver.validate("shot", ctx)

        assert is_valid is True
        assert missing == []

    def test_validate_with_default_and_value_provided(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("shot", "V:/shows/<show>/ep/<episode:default=pilot>")

        # Episode provided
        ctx = VFXContext(show="demo", episode="s01e01")
        is_valid, missing = resolver.validate("shot", ctx)

        assert is_valid is True
        assert missing == []

    def test_validate_with_formatters(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("shot", "V:/shows/<show:upper>/seq/<seq:03>/<shot:04>")

        ctx = VFXContext(show="demo", seq="10", shot="5")
        is_valid, missing = resolver.validate("shot", ctx)

        # Formatters don't affect validation
        assert is_valid is True
        assert missing == []

    def test_validate_template_not_found(self) -> None:
        resolver = PathResolver(VFXContext)

        ctx = VFXContext(show="demo")

        with pytest.raises(KeyError, match="Template 'nonexistent' not registered"):
            resolver.validate("nonexistent", ctx)

    def test_validate_with_inheritance(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("base", "V:/shows/<show>")
        resolver.register("seq", "seq/<seq>", base="base")
        resolver.register("shot", "<shot>/work", base="seq")

        # All tokens required by the full pattern
        ctx = VFXContext(show="demo", seq="010", shot="0010")
        is_valid, missing = resolver.validate("shot", ctx)

        assert is_valid is True
        assert missing == []

    def test_validate_with_inheritance_missing_tokens(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("base", "V:/shows/<show>")
        resolver.register("seq", "seq/<seq>", base="base")
        resolver.register("shot", "<shot>/work", base="seq")

        # Missing seq and shot
        ctx = VFXContext(show="demo")
        is_valid, missing = resolver.validate("shot", ctx)

        assert is_valid is False
        assert "seq" in missing
        assert "shot" in missing

    def test_validate_multiple_defaults(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register(
            "multi",
            "V:/shows/<show>/ep/<episode:default=pilot>/task/<task:default=layout>",
        )

        # Only show provided, both defaults should be satisfied
        ctx = VFXContext(show="demo")
        is_valid, missing = resolver.validate("multi", ctx)

        assert is_valid is True
        assert missing == []

    def test_validate_partial_defaults(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register(
            "partial", "V:/shows/<show>/ep/<episode:default=pilot>/seq/<seq>"
        )

        # show provided, episode has default, but seq missing
        ctx = VFXContext(show="demo")
        is_valid, missing = resolver.validate("partial", ctx)

        assert is_valid is False
        assert "seq" in missing
        assert "episode" not in missing

    def test_template_validate_directly(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>")

        template = resolver.templates["shot"]
        ctx = VFXContext(show="demo", seq="010")

        is_valid, missing = template.validate(ctx)

        assert is_valid is False
        assert "shot" in missing

    def test_validate_before_resolve(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>")

        ctx = VFXContext(show="demo", seq="010")

        # Check validation first
        is_valid, missing = resolver.validate("shot", ctx)

        if not is_valid:
            # Don't attempt to resolve
            assert "shot" in missing
        else:
            # Safe to resolve
            path = resolver.resolve("shot", ctx)

    def test_validate_empty_context(self) -> None:
        resolver = PathResolver(VFXContext)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>")

        ctx = VFXContext()
        is_valid, missing = resolver.validate("shot", ctx)

        assert is_valid is False
        assert len(missing) == 3

    def test_validate_with_normalizers(self) -> None:
        normalizers = {"show": lambda v: v.replace(" ", "_")}
        resolver = PathResolver(VFXContext, normalizers=normalizers)
        resolver.register("shot", "V:/shows/<show>/seq/<seq>")

        ctx = VFXContext(show="My Show", seq="010")
        is_valid, missing = resolver.validate("shot", ctx)

        # Validation doesn't care about normalizers
        assert is_valid is True
        assert missing == []

    def test_validate_with_variables(self) -> None:
        resolver = PathResolver(VFXContext, variables={"ROOT": "/mnt/storage"})
        resolver.register("shot", "{ROOT}/shows/<show>/seq/<seq>")

        ctx = VFXContext(show="demo", seq="010")
        is_valid, missing = resolver.validate("shot", ctx)

        # Variables don't affect validation
        assert is_valid is True
        assert missing == []
