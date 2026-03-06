import re
from dataclasses import asdict
from typing import Callable
from typing import Generic
from typing import Optional

from templar.templartypes import ContextT


class PathTemplate(Generic[ContextT]):
    """
    A path template with optional token support.

    Represents a file path pattern with placeholders (tokens) that can be
    filled from a context dataclass.

    Tokens are denoted with angle brackets like <show> or <asset>.
    Tokens can have formatters: <seq:04> for padding, <show:upper> for case conversion.
    The template extracts all token names on initialization and can validate
    whether a given context contains all required values before formatting.
    """

    TOKEN_PATTERN = re.compile(r"<(\w+)(?::([^>]+))?>")

    def __init__(
        self,
        pattern: str,
        name: str = "",
        base: Optional["PathTemplate"] = None,
        normalizers: dict[str, Callable[[str], str]] = None,
    ) -> None:
        if base:
            self.pattern = f"{base.pattern}/{pattern}"
        else:
            self.pattern = pattern

        self.name = name
        self.base = base
        self.normalizers = normalizers or {}
        self.tokens = self._extract_tokens()

    def _extract_tokens(self) -> set[str]:
        """Extract all token names from pattern (without formatters)."""
        return set(match[0] for match in self.TOKEN_PATTERN.findall(self.pattern))

    @staticmethod
    def _apply_formatter(value: str, formatter: str) -> str:
        """
        Apply a formatter to a token value.

        Supported formatters:
            - Padding: 04, 03 (zero-pad to width)
            - Case: upper, lower, title
            - Default: default=value (use if token is None)

        Args:
            value (str): Token value to format.
            formatter (str): Formatter specification.
        Returns:
            str: Formatted value.
        """
        if formatter.startswith("default="):
            default_value = formatter[len("default=") :]
            return value if value else default_value

        if formatter.isdigit():
            width = int(formatter)
            if value.isdigit():
                return value.zfill(width)
            return value

        if formatter == "upper":
            return value.upper()
        elif formatter == "lower":
            return value.lower()
        elif formatter == "title":
            return value.title()

        return value

    def format(self, context: ContextT) -> str:
        """
        Format template using context values.

        Args:
            context (ContextT): Context dataclass containing token values.
        Returns:
            str: Formatted path string.
        Raises:
            ValueError: If required tokens are missing from context.
        """
        context_dict = {k: v for k, v in asdict(context).items() if v is not None}
        missing = set()

        for token_name, formatter in self.TOKEN_PATTERN.findall(self.pattern):
            if formatter and formatter.startswith("default="):
                continue
            if token_name not in context_dict:
                missing.add(token_name)

        if missing:
            raise ValueError(f"Missing required tokens: {missing}")

        result = self.pattern

        for match in self.TOKEN_PATTERN.finditer(self.pattern):
            token_name = match.group(1)
            formatter = match.group(2)
            full_token = match.group(0)  # e.g., "<seq:04>"
            value = context_dict.get(token_name, "")

            if token_name in self.normalizers:
                value = self.normalizers[token_name](value)
            if formatter:
                value = self._apply_formatter(value, formatter)

            result = result.replace(full_token, str(value))

        return result

    def can_format(self, context: ContextT) -> bool:
        """
        Check if context has all required tokens.

        Args:
            context (ContextT): Context dataclass to check.
        Returns:
            bool: True if all tokens present.
        """
        context_dict = {k: v for k, v in asdict(context).items() if v is not None}

        for token_name, formatter in self.TOKEN_PATTERN.findall(self.pattern):
            if formatter and formatter.startswith("default="):
                continue  # Tokens with defaults are always satisfied
            if token_name not in context_dict:
                return False

        return True

    def validate(self, context: ContextT) -> tuple[bool, list[str]]:
        """
        Validate that context has all required tokens to format this template.

        Args:
            context (ContextT): Context to validate.
        Returns:
            tuple[bool, list[str]]: (is_valid, list of missing token names)
        """
        context_dict = {k: v for k, v in asdict(context).items() if v is not None}
        missing = []

        for token_name, formatter in self.TOKEN_PATTERN.findall(self.pattern):
            if formatter and formatter.startswith("default="):
                continue
            if token_name not in context_dict:
                missing.append(token_name)

        return len(missing) == 0, missing
