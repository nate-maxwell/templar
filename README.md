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

# Use {variable} syntax in templates (different from <token> syntax)
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
