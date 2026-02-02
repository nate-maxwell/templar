"""
Templar - Type-safe path templating for production pipelines.

This module provides a lightweight templating system for building and parsing
file paths using strongly-typed dataclass contexts. Define path templates with
token placeholders, then generate paths from context values or parse existing
paths back into structured data.

Core Components:
    PathTemplate: Represents a single path pattern with token placeholders
    PathResolver: Manages multiple templates and resolves them from context

Example:
    >>> from dataclasses import dataclass
    >>> from typing import Optional
    >>> from pathlib import Path
    >>>
    >>> @dataclass
    >>> class VFXContext:
    ...     show: Optional[str] = None
    ...     seq: Optional[str] = None
    ...     shot: Optional[str] = None
    ...     dcc: Optional[str] = None
    ...
    >>> resolver = PathResolver(VFXContext)
    >>> resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>/__pub__/<dcc>")
    >>>
    >>> ctx = VFXContext(show="demo", seq="DEF", shot="0010", dcc="maya")
    >>> path = resolver.resolve("shot", ctx)
    >>> print(path)
    V:/shows/demo/seq/DEF/0010/__pub__/maya
    >>>
    >>> parsed = resolver.parse_path(path)
    >>> print(parsed.show, parsed.seq)
    demo DEF

Typical Usage:
    1. Define a dataclass with Optional[str] fields for your path components
    2. Create a PathResolver with your dataclass
    3. Register path templates using <token> syntax
    4. Build paths with resolve() or parse paths with parse_path()

The system automatically handles:
    - Optional tokens (templates match based on available context fields)
    - File name/extension extraction (file_name and file_type fields)
    - Cross-platform path separators
    - Round-trip conversion (path -> context -> path)
"""

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Generic
from typing import Optional
from typing import TypeVar

ContextT = TypeVar("ContextT")


class PathTemplate(Generic[ContextT]):
    """
    A path template with optional token support.

    Represents a file path pattern with placeholders (tokens) that can be
    filled from a context dataclass.

    Tokens are denoted with angle brackets like <show> or <asset>.
    The template extracts all token names on initialization and can validate
    whether a given context contains all required values before formatting.
    """

    TOKEN_PATTERN = re.compile(r"<(\w+)>")

    def __init__(self, pattern: str, name: str = "") -> None:
        self.pattern = pattern
        self.name = name
        self.tokens = self._extract_tokens()

    def _extract_tokens(self) -> set[str]:
        """Extract all token names from pattern."""
        return set(self.TOKEN_PATTERN.findall(self.pattern))

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

        missing = self.tokens - set(context_dict.keys())
        if missing:
            raise ValueError(f"Missing required tokens: {missing}")

        result = self.pattern
        for token in self.tokens:
            result = result.replace(f"<{token}>", str(context_dict[token]))

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
        return self.tokens.issubset(set(context_dict.keys()))


class PathResolver(Generic[ContextT]):
    """
    Resolves path templates based on context.

    Manages a registry of named PathTemplate instances and provides methods to
    resolve them into concrete file paths using a context dataclass.

    Templates can be resolved explicitly by name, or the resolver can
    automatically select the first matching template based on what fields are
    populated in the context.
    """

    def __init__(self, context_type: type[ContextT]) -> None:
        self.templates: dict[str, PathTemplate[ContextT]] = {}
        self.context_type = context_type

    def register(self, name: str, pattern: str) -> None:
        """
        Register a new path template.

        Args:
            name (str): Template identifier.
            pattern (str): Path pattern with <token> placeholders.
        """
        self.templates[name] = PathTemplate[ContextT](pattern, name)

    def load_from_json(self, json_path: Path) -> None:
        """
        Load templates from a JSON file.

        Args:
            json_path (Path): Path to JSON file containing templates.

        The JSON file should have the format:
        {
            "template_name": "pattern/with/<tokens>",
            "another_template": "another/pattern/<with>/<tokens>"
        }
        """
        with open(json_path, "r") as f:
            templates_data = json.load(f)

        for name, pattern in templates_data.items():
            self.register(name, pattern)

    def resolve(self, name: str, context: ContextT) -> Path:
        """
        Resolve a specific template by name.

        Args:
            name (str): Template name.
            context (ContextT): Context values.
        Returns:
            Path: Formatted path.
        """
        if name not in self.templates:
            raise KeyError(f"Template '{name}' not registered")

        return Path(self.templates[name].format(context))

    def resolve_any(
        self, context: ContextT, prefer: list[str] = None
    ) -> Optional[Path]:
        """
        Find and resolve first matching template.

        Args:
            context (ContextT): Context values.
            prefer (list[str]): Ordered list of template names to prefer.
        Returns:
            Path: Formatted path from first matching template, or None.
        """
        search_order = prefer if prefer else list(self.templates.keys())

        for name in search_order:
            template = self.templates.get(name)
            if template and template.can_format(context):
                return Path(template.format(context))

        return None

    def find_matches(self, context: ContextT) -> list[str]:
        """
        Find all template names that can be formatted with context.

        Args:
            context (ContextT): Context to check.
        Returns:
            list[str]: Names of matching templates.
        """
        return [
            name
            for name, template in self.templates.items()
            if template.can_format(context)
        ]

    def parse_path(self, path: Path) -> Optional[ContextT]:
        """
        Parse a file path into a context dataclass using registered templates.
        Attempts to match the given path against all registered templates in
        the resolver.
        Returns a context dataclass populated with extracted token values from
        the first matching template.

        Args:
            path (Path): File path to parse.
        Returns:
            ContextT: Context with extracted values, or None if no
                template matches.
        """
        path_str = path.as_posix()

        for template in self.templates.values():
            pattern = template.pattern.replace("\\", "/")
            pattern = re.escape(pattern)

            def replace_token(match_) -> str:
                """
                Replaces tokens with appropriate capture groups.
                Done in a single pass to avoid conflicts.
                """
                token_name = match_.group(1)
                if token_name in ("file_name", "file_type"):
                    # Exclude dots and slashes for filename components
                    return f"(?P<{token_name}>[^/.]+)"

                # Exclude only slashes for other tokens
                return f"(?P<{token_name}>[^/]+)"

            pattern = re.sub(r"<(\w+)>", replace_token, pattern)
            pattern = f"^{pattern}$"

            if not (match := re.match(pattern, path_str)):
                continue

            context_data = match.groupdict()
            had_file_name = "file_name" in template.tokens
            had_file_type_token = "file_type" in template.tokens

            if not had_file_name and path.stem:
                context_data["file_name"] = path.stem
            if not had_file_type_token and path.suffix:
                context_data["file_type"] = path.suffix.lstrip(".")

            return self.context_type(**context_data)

        return None
