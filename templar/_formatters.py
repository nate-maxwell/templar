import operator
from typing import Callable


def _pad(value: str, spec: str) -> str:
    """
    Zero-pad numeric values to the width given by the spec.

    Args:
        value (str): Token value to pad.
        spec (str): Formatter specification, a string of digits such as "04".
    Returns:
        str: Zero-padded value, or the value unchanged if it is not numeric.
    """
    return value.zfill(int(spec)) if value.isdigit() else value


def _default(value: str, spec: str) -> str:
    """
    Substitute a fallback when the value is empty.

    Args:
        value (str): Token value.
        spec (str): Formatter specification, such as "default=main".
    Returns:
        str: The value, or the text after "default=" if the value is empty.
    """
    return value or spec[len("default=") :]


_Predicate = Callable[[str], bool]
_Handler = Callable[[str, str], str]

PREDICATE_FORMATTERS: tuple[tuple[_Predicate, _Handler], ...] = (
    (lambda spec: spec.startswith("default="), _default),
    (lambda spec: spec.isdigit(), _pad),
)
"""
Formatters selected by a predicate on the spec, checked in order.
Each handler receives (value, spec).
"""

NAMED_FORMATTERS: dict[str, Callable[[str], str]] = {
    "upper": operator.methodcaller("upper"),
    "lower": operator.methodcaller("lower"),
    "title": operator.methodcaller("title"),
}
"""Formatters selected by exact spec name."""
