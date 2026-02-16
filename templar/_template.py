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
from typing import Callable
from typing import Generic
from typing import Optional

from templar._templartypes import ContextT


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


class PathResolver(Generic[ContextT]):
    """
    Resolves path templates based on context.

    Manages a registry of named PathTemplate instances and provides methods to
    resolve them into concrete file paths using a context dataclass.

    Templates can be resolved explicitly by name, or the resolver can
    automatically select the first matching template based on what fields are
    populated in the context.
    """

    def __init__(
        self,
        context_type: type[ContextT],
        variables: dict[str, str] = None,
        normalizers: dict[str, Callable[[str], str]] = None,
    ) -> None:
        self.templates: dict[str, PathTemplate[ContextT]] = {}
        self.context_type = context_type
        self.variables = variables or {}
        self.normalizers = normalizers or {}
        self._token_values: dict[str, list[str]] = {}

    def register(self, name: str, pattern: str, base: Optional[str] = None) -> None:
        """
        Register a new path template.

        Args:
            name (str): Template identifier.
            pattern (str): Path pattern with <token> placeholders.
            base (str): Optional name of base template to extend.
        """
        resolved_pattern = pattern
        for var_name, var_value in self.variables.items():
            resolved_pattern = resolved_pattern.replace(f"{{{var_name}}}", var_value)

        base_template = None
        if base:
            if base not in self.templates:
                raise KeyError(f"Base template '{base}' not found")
            base_template = self.templates[base]

        self.templates[name] = PathTemplate[ContextT](
            resolved_pattern, name, base=base_template, normalizers=self.normalizers
        )

    def from_dict(self, data: dict) -> None:
        """
        Load templates from a dictionary.

        Args:
            data (dict): The dictionary to load from.

        The dict file should have the format:
        {
            "template_name": "pattern/with/<tokens>",
            "another_template": {
                "pattern": "another/pattern/<with>/<tokens>",
                "base": "template_name"
            }
        }
        """
        for name, value in data.items():
            if isinstance(value, str):
                self.register(name, value)

            elif isinstance(value, dict):  # Pattern with base template
                pattern = value["pattern"]
                base = value.get("base")
                self.register(name, pattern, base=base)

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

    def validate(self, name: str, context: ContextT) -> tuple[bool, list[str]]:
        """
        Validate that context has all required tokens for a template.

        Args:
            name (str): Template name.
            context (ContextT): Context to validate.
        Returns:
            tuple[bool, list[str]]: (is_valid, list of missing token names)
        Raises:
            KeyError: If template not found.
        """
        if name not in self.templates:
            raise KeyError(f"Template '{name}' not registered")

        return self.templates[name].validate(context)

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
            ContextT: Context with extracted values, or None if no template
                matches.
        """
        path_str = path.as_posix()

        for template in self.templates.values():
            pattern = template.pattern.replace("\\", "/")
            pattern = re.escape(pattern)

            # Strip formatters before creating regex - match <token> or <token:formatter>
            pattern = re.sub(r"<(\w+)(?::[^>]+)?>", r"(?P<\1>[^/]+)", pattern)
            pattern = f"^{pattern}$"

            if not (match := re.match(pattern, path_str)):
                continue

            context_data = match.groupdict()
            return self.context_type(**context_data)

        return None

    def register_token_values(self, token: str, values: list[str]) -> None:
        """
        Register possible values for a token to enable structure generation.

        Args:
            token (str): Token name (e.g., 'file_type', 'dcc').
            values (list[str]): All possible values for this token.
        """
        self._token_values[token] = values

    def get_token_values(self, token: str) -> list[str]:
        """
        Get registered values for a token.

        Args:
            token (str): Token name.
        Returns:
            list[str]: Registered values, or empty list if none.
        """
        return self._token_values.get(token, [])

    def create_structure(
        self,
        name: str,
        context: ContextT,
        dry_run: bool = False,
        stop_at_token: Optional[str] = None,
    ) -> list[Path]:
        """
        Create directory structure by expanding partial context with registered
        token values.

        For any token in the template that:
        1. Has registered values via register_token_values()
        2. Is NOT populated in the provided context
        3. Comes before stop_at_token (if specified)

        This method will create all combinations of directories.

        Args:
            name (str): Template name to use.
            context (ContextT): Partial context with some values populated.
            dry_run (bool): If True, return paths without creating directories.
            stop_at_token (str): Optional token name to stop expansion at.
                All tokens after this in the template will not be expanded.
        Returns:
            list[Path]: All created (or would-be-created) directory paths.

        Example:
            >>> resolver.register_token_values('dcc', ['maya', 'blender', 'nuke'])
            >>> resolver.register_token_values('file_type', ['ma', 'fbx', 'abc'])
            >>> ctx = AssetContext(project='TEST', category='char', asset='Ghost_A')
            >>> paths = resolver.create_structure('asset', ctx, stop_at_token='file_type')
            # Creates: .../Ghost_A/maya/ma, .../Ghost_A/maya/fbx, etc.
        """
        if name not in self.templates:
            raise KeyError(f"Template '{name}' not registered")

        template = self.templates[name]
        context_dict = {k: v for k, v in asdict(context).items() if v is not None}
        ordered_tokens = self._extract_ordered_tokens(template.pattern)

        stop_index = len(ordered_tokens)
        if stop_at_token:
            token_names = [t["name"] for t in ordered_tokens]
            try:
                stop_index = token_names.index(stop_at_token)
            except ValueError:
                raise ValueError(
                    f"stop_at_token '{stop_at_token}' not found in template. "
                    f"Available tokens: {token_names}"
                )

        expansion_tokens = []
        for i, token_info in enumerate(ordered_tokens[:stop_index]):
            token_name = token_info["name"]

            # Skip if already in context
            if token_name in context_dict:
                continue

            # Skip if no registered values
            if token_name not in self._token_values:
                continue

            expansion_tokens.append(token_name)

        paths = self._expand_contexts(
            template, context, expansion_tokens, stop_index, ordered_tokens
        )

        if not dry_run:
            for path in paths:
                path.mkdir(parents=True, exist_ok=True)

        return paths

    @staticmethod
    def _extract_ordered_tokens(pattern: str) -> list[dict]:
        """
        Extract tokens in the order they appear in the pattern.

        Returns:
            list[dict]: List of dicts with 'name', 'formatter', 'position'.
        """
        tokens = []
        for match in PathTemplate.TOKEN_PATTERN.finditer(pattern):
            tokens.append(
                {
                    "name": match.group(1),
                    "formatter": match.group(2),
                    "position": match.start(),
                }
            )
        return tokens

    def _expand_contexts(
        self,
        template: PathTemplate[ContextT],
        base_context: ContextT,
        expansion_tokens: list[str],
        stop_index: int,
        ordered_tokens: list[dict],
    ) -> list[Path]:
        """
        Recursively expand context with all token value combinations.

        Args:
            template (PathTemplate): Template to format.
            base_context (ContextT): Starting context.
            expansion_tokens (list[str]): Tokens that need expansion.
            stop_index (int): Index in ordered_tokens to stop at.
            ordered_tokens (list[dict]): All tokens in order.
        Returns:
            list[Path]: All expanded directory paths.
        """
        if not expansion_tokens:
            # Base case: no more tokens to expand
            # Format up to stop_index tokens only
            partial_pattern = self._truncate_pattern_at_index(
                template.pattern, stop_index, ordered_tokens
            )
            partial_template = PathTemplate(
                partial_pattern,
                normalizers=template.normalizers,
            )

            # Only format if we have all required tokens for partial pattern
            if partial_template.can_format(base_context):
                formatted = partial_template.format(base_context)
                return [Path(formatted)]
            return []

        # Recursive case: expand next token
        token_name = expansion_tokens[0]
        remaining_tokens = expansion_tokens[1:]

        paths = []
        for value in self._token_values[token_name]:
            context_dict = asdict(base_context)
            context_dict[token_name] = value
            new_context = self.context_type(**context_dict)

            # Recursively expand remaining tokens
            paths.extend(
                self._expand_contexts(
                    template, new_context, remaining_tokens, stop_index, ordered_tokens
                )
            )

        return paths

    @staticmethod
    def _truncate_pattern_at_index(
        pattern: str,
        stop_index: int,
        ordered_tokens: list[dict],
    ) -> str:
        """
        Truncate pattern to include all tokens up to (but not including) stop_index.
        Returns the directory path that includes the last expanded token.

        Args:
            pattern (str): Full template pattern.
            stop_index (int): Index to stop at (exclusive).
            ordered_tokens (list[dict]): Ordered token information.
        Returns:
            str: Truncated pattern string.
        """
        if stop_index == 0:
            return ""

            # If stop_index >= len(ordered_tokens), we want ALL tokens
            # Don't truncate, return full pattern
        if stop_index >= len(ordered_tokens):
            return pattern

        # We want to include tokens 0 through stop_index-1
        # Find where token at stop_index starts, and truncate just before it
        stop_token = ordered_tokens[stop_index]
        stop_position = stop_token["position"]

        # Walk backwards from stop_position to find the directory separator
        # that comes BEFORE the stop_token
        truncate_pos = stop_position - 1
        while truncate_pos > 0 and pattern[truncate_pos] not in ("/", "\\"):
            truncate_pos -= 1

        if truncate_pos > 0:
            return pattern[:truncate_pos]

        return pattern[:stop_position]  # No sep


class CompositeResolver(object):
    """
    Manages multiple PathResolvers for different context types.

    Allows registration and resolution of path templates across multiple
    context dataclasses without needing separate resolver instances. Routes
    operations to the appropriate resolver based on context type.
    """

    def __init__(
        self,
        variables: dict[str, str] = None,
        normalizers: dict[str, Callable[[str], str]] = None,
    ) -> None:
        self._registry: dict[type, PathResolver] = {}
        self.variables = variables or {}
        self.normalizers = normalizers or {}

    def register(
        self,
        context_type: type[ContextT],
        name: str,
        pattern: str,
        base: Optional[str] = None,
    ) -> None:
        if context_type not in self._registry:
            resolver = PathResolver(
                context_type, variables=self.variables, normalizers=self.normalizers
            )
            self._registry[context_type] = resolver
        else:
            resolver = self._registry[context_type]

        resolver.register(name, pattern, base=base)

    def resolve(self, name: str, context: ContextT) -> Path:
        """
        Resolve a template by name using the context's type.

        Args:
            name (str): Template name.
            context (ContextT): Context instance with values.
        Returns:
            Path: Formatted path.
        """
        resolver = self._registry[type(context)]
        return resolver.resolve(name, context)

    def resolve_any(
        self, context: ContextT, prefer: list[str] = None
    ) -> Optional[Path]:
        """
        Find and resolve the first matching template for the context's type.

        Args:
            context (ContextT): Context instance with values.
            prefer (list[str]): Optional ordered list of template names to try first.
        Returns:
            Path: Formatted path from first matching template, or None.
        """
        resolver = self._registry[type(context)]
        return resolver.resolve_any(context, prefer)

    def find_matches(self, context: ContextT) -> list[str]:
        """
        Find all templates that can be formatted with the given context.

        Args:
            context (ContextT): Context instance to check.
        Returns:
            list[str]: Names of matching templates.
        """
        resolver = self._registry[type(context)]
        return resolver.find_matches(context)

    def parse_path(
        self, context_type: type[ContextT], path: Path
    ) -> Optional[ContextT]:
        """
        Parse a path into a context instance using registered templates.

        Args:
            context_type (type[ContextT]): Dataclass type to parse into.
            path (Path): File path to parse.
        Returns:
            ContextT: Context with extracted values, or None if no match.
        Raises:
            ValueError: If context_type has no registered templates.
        """
        if context_type not in self._registry:
            raise ValueError(
                f"Context type {context_type} is not currently registered!"
            )
        resolver = self._registry[context_type]
        return resolver.parse_path(path)

    def get_resolver_for(self, context_type: type[ContextT]) -> PathResolver:
        """
        Returns the specific path resolver the composite resolver is using for
        the given dataclass type.

        Args:
            context_type (type[ContextT]): The dataclass type to get the tracked
                path resolver for.
        Returns:
            PathResolver: The requested path resolver.
        """
        if context_type in self._registry:
            return self._registry[context_type]
        else:
            raise ValueError(f"{context_type} is not registered in CompositeResolver.")
