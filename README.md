# Templar

A lightweight, type-safe path templating system for building and parsing file
paths from dataclass contexts.

## Overview

PathForge provides a clean way to manage file path structures in production
pipelines.
Define path templates once, then build or parse paths using strongly-typed
dataclass contexts with full IDE autocomplete support.

## Features

- **Type-safe contexts**: Use dataclasses instead of raw dictionaries for full IDE support
- **Bidirectional**: Build paths from context, or parse context from paths
- **JSON configuration**: Load path templates from external JSON files
- **Generic design**: Works with any dataclass structure
- **Variable supper**: Create reusable variables to prefill path parts
- **Path Inheritance**: Paths can extend base paths

## Usage

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from templar import PathResolver


# Define your context
@dataclass
class VFXContext(object):
    show: Optional[str] = None
    episode: Optional[str] = None
    seq: Optional[str] = None
    shot: Optional[str] = None
    dcc: Optional[str] = None
    file_type: Optional[str] = None
    file_name: Optional[str] = None


resolver = PathResolver(VFXContext)

# Register templates manually
resolver.register(
    name="shot_pub",
    pattern="V:/shows/<show>/seq/<seq>/<shot>/__pub__/<dcc>/<file_type>"
)

resolver.register(
    name="shot_pub_episodic",
    pattern="V:/shows/<show>/seq/<episode>/<seq>/<shot>/__pub__/<dcc>/<file_type>"
)

# Or load from JSON
# templates.json:
# {
#   "asset_pub": "V:/shows/_alexandria/asset/<category>/<asset>/__pub__/<dcc>/<file_type>",
#   "render": "V:/shows/<show>/render/<seq>/<shot>/<element>",
#   ...
# }
resolver.load_from_json(Path("templates.json"))

# Build paths from context
ctx = VFXContext(
    show="supernatural",
    episode="e01",
    seq="010",
    shot="0010",
    dcc="maya",
    file_type="mb"
)

# Resolve specific template
path = resolver.resolve("shot_pub_episodic", ctx)
# V:\shows\supernatural\seq\e01\010\0010\__pub__\maya\mb

# Auto-select with preference order
path = resolver.resolve_any(ctx,
                            prefer=["shot_pub_episodic", "shot_pub_feature"])
# V:\shows\supernatural\seq\e01\010\0010\__pub__\maya\mb

# Parse paths back to context
path = Path("V:/shows/supernatural/seq/e01/DEF/0010/__pub__/maya/scene.ma")
ctx = resolver.parse_path(path)
# VFXContext(
#     show='supernatural', episode='e01', seq='DEF', shot='0010',
#     dcc='maya', file_name='scene', file_type='ma'
# )
```

## Composite Resolver

You can use a CompositeResolver to register multiple dataclasses and manage
their corresponding templates like so:

```python
from templar import CompositeResolver


@dataclass
class ShotContext:
    show: Optional[str] = None
    seq: Optional[str] = None
    shot: Optional[str] = None


@dataclass
class AssetContext:
    category: Optional[str] = None
    asset: Optional[str] = None


# Single composite resolver for all context types
composite = CompositeResolver()

# Register templates for different contexts
composite.register(ShotContext, "shot", "V:/shows/<show>/seq/<seq>/<shot>")
composite.register(AssetContext, "asset", "V:/assets/<category>/<asset>")

shot_path = Path("V:/shows/demo/seq/010/0010")
asset_path = Path("V:/assets/props/table")

shot_parsed = composite.parse_path(ShotContext, shot_path)
asset_parsed = composite.parse_path(AssetContext, asset_path)

print(f"\nshow: {shot_parsed.show}")  # show: demo
print(f"seq: {shot_parsed.seq}")  # seq: 010
print(f"shot: {shot_parsed.shot}")  # shot: 0010
```

## Variables

Use variables in templates with `{variable}` syntax like so:
```python
import platform

# Define variables once
root = "V:/projects" if platform.system() == "Windows" else "/mnt/storage/projects"
resolver = PathResolver(VFXContext, variables={"PROJECT_ROOT": root})

resolver.register("shot", "{PROJECT_ROOT}/shows/<show>/seq/<seq>/<shot>")

# Variables are substituted when templates are registered
ctx = VFXContext(show="demo", seq="010", shot="0010")
path = resolver.resolve("shot", ctx)

# Windows: V:\projects\shows\demo\seq\010\0010
# Linux:   /mnt/storage/projects/shows/demo/seq/010/0010
```

Variables work with `CompositeResolver` too - just pass them during initialization and all registered templates will use them:
```python
composite = CompositeResolver(variables={"PROJECT_ROOT": root, "ASSET_LIB": "library"})
composite.register(ShotContext, "shot", "{PROJECT_ROOT}/shows/<show>")
composite.register(AssetContext, "asset", "{PROJECT_ROOT}/{ASSET_LIB}/<category>/<asset>")
```

## Template Inheritance

Build complex path hierarchies by extending base templates:
```python
from dataclasses import dataclass
from typing import Optional
from templar import PathResolver

@dataclass
class VFXContext:
    show: Optional[str] = None
    seq: Optional[str] = None
    shot: Optional[str] = None
    task: Optional[str] = None
    version: Optional[str] = None

resolver = PathResolver(VFXContext)

# Define base templates
resolver.register("show_base", "V:/shows/<show>")
resolver.register("seq_base", "seq/<seq>", base="show_base")
resolver.register("shot_base", "<shot>/work", base="seq_base")

# Extend to create specific paths
resolver.register("task_version", "<task>/v<version>", base="shot_base")

ctx = VFXContext(show="demo", seq="DEF", shot="0010", task="anim", version="001")
path = resolver.resolve("task_version", ctx)
print(path)  # V:\shows\demo\seq\DEF\0010\work\anim\v001
```

Path inheritance JSON storing:
```json
{
  "show_base": "V:/shows/<show>",
  "seq_base": {
    "pattern": "seq/<seq>",
    "base": "show_base"
  },
  "shot_work": {
    "pattern": "<shot>/__work__",
    "base": "seq_base"
  },
  "shot_pub": {
    "pattern": "<shot>/__pub__",
    "base": "seq_base"
  }
}
```

## Token Formatters

Apply formatting to token values when building paths:
```python
@dataclass
class VFXContext:
    show: Optional[str] = None
    seq: Optional[str] = None
    shot: Optional[str] = None
    version: Optional[str] = None

resolver = PathResolver(VFXContext)

# Padding - zero-pad numbers to fixed width
resolver.register("padded", "V:/shows/<show>/seq/<seq:03>/<shot:04>/v<version:03>")
ctx = VFXContext(show="demo", seq="5", shot="10", version="2")
path = resolver.resolve("padded", ctx)
# V:\shows\demo\seq\005\0010\v002

# Case conversion
resolver.register("uppercase", "V:/shows/<show:upper>/seq/<seq>")
ctx = VFXContext(show="demo", seq="010")
path = resolver.resolve("uppercase", ctx)
# V:\shows\DEMO\seq\010

# Default values - use fallback if token not provided
resolver.register("with_default", "V:/shows/<show>/ep/<episode:default=pilot>")
ctx = VFXContext(show="demo")  # No episode provided
path = resolver.resolve("with_default", ctx)
# V:\shows\demo\ep\pilot
```

**Available formatters:**
- `<token:04>` - Zero-pad numbers to width (e.g., `5` → `0005`)
- `<token:upper>` - Convert to uppercase
- `<token:lower>` - Convert to lowercase
- `<token:title>` - Title case
- `<token:default=value>` - Use default if token not provided

## Normalizers

Automatically sanitize token values to ensure valid paths:
```python
# Define normalizer functions
def spaces_to_underscores(value: str) -> str:
    return value.replace(" ", "_")

def remove_illegal_chars(value: str) -> str:
    return re.sub(r'[<>:"|?*\x00-\x1f]', '', value)

def safe_filename(value: str) -> str:
    value = re.sub(r'[<>:"|?*\x00-\x1f]', '', value)
    value = value.replace(" ", "_")
    return value.strip("._")

@dataclass
class VFXContext:
    show: Optional[str] = None
    seq: Optional[str] = None
    shot: Optional[str] = None
    task: Optional[str] = None

# Register normalizers per token
normalizers = {
    "show": spaces_to_underscores,
    "shot": safe_filename,
    "task": lambda v: re.sub(r'[^\w]', '', v)  # Alphanumeric only
}

resolver = PathResolver(VFXContext, normalizers=normalizers)
resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>/work/<task>")

# Values are automatically sanitized
ctx = VFXContext(
    show="My Cool Show",        # Becomes: My_Cool_Show
    seq="010",
    shot="shot: with colons",   # Becomes: shot_with_colons
    task="anim-final"           # Becomes: animfinal
)

path = resolver.resolve("shot", ctx)
print(path)
# V:\shows\My_Cool_Show\seq\010\shot_with_colons\work\animfinal
```

**Normalizers run before formatters:**
```python
normalizers = {"show": spaces_to_underscores}
resolver = PathResolver(VFXContext, normalizers=normalizers)
resolver.register("shot", "V:/shows/<show:upper>/seq/<seq:03>")

ctx = VFXContext(show="my show", seq="5")
path = resolver.resolve("shot", ctx)
# V:\shows\MY_SHOW\seq\005
# (normalized to my_show, then uppercased to MY_SHOW, seq padded to 005)
```

Works with `CompositeResolver` - normalizers apply to all registered context types:
```python
normalizers = {"show": spaces_to_underscores, "asset": safe_filename}
composite = CompositeResolver(normalizers=normalizers)

composite.register(ShotContext, "shot", "V:/shows/<show>")
composite.register(AssetContext, "asset", "V:/assets/<asset>")
# Both contexts use the same normalizers
```
