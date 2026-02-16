# Templar

A lightweight, type-safe path templating system for building and parsing file paths from dataclass contexts.

## Features

- **Type-safe contexts**: Dataclasses with full IDE autocomplete support
- **Bidirectional**: Build paths from context, or parse context from paths
- **Template inheritance**: Extend base templates to build complex hierarchies
- **Token formatters**: Padding, case conversion, and default values
- **Normalizers**: Auto-sanitize values for valid paths
- **Variables**: Cross-platform path roots and reusable substitutions
- **Validation**: Check if context has all required tokens before building paths
- **Queryable**: Finds all paths matching criteria and creates a dataclass from them
- **JSON configuration**: Load templates from external files

## Quick Start
```python
from dataclasses import dataclass
from typing import Optional
from templar import PathResolver

@dataclass
class VFXContext:
    show: Optional[str] = None
    seq: Optional[str] = None
    shot: Optional[str] = None
    dcc: Optional[str] = None

resolver = PathResolver(VFXContext)
resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>/__pub__/<dcc>")

# Build paths
ctx = VFXContext(show="demo", seq="DEF", shot="0010", dcc="maya")
path = resolver.resolve("shot", ctx)
# V:\shows\demo\seq\DEF\0010\__pub__\maya

# Resolve any of multiple templates
path = resolver.resolve_any(ctx, ["shot_feature", "shot_episodic"])

# Parse paths
ctx = resolver.parse_path(path)
# VFXContext(show='demo', seq='DEF', shot='0010', dcc='maya')
```

## Variables

Support cross-platform paths:
```python
import platform

root = "V:/projects" if platform.system() == "Windows" else "/mnt/storage/projects"
resolver = PathResolver(VFXContext, variables={"ROOT": root})
resolver.register("shot", "{ROOT}/shows/<show>/seq/<seq>")
```

## Template Inheritance

Build paths from reusable base templates:
```python
resolver.register("show_base", "V:/shows/<show>")
resolver.register("seq_base", "seq/<seq>", base="show_base")
resolver.register("shot", "<shot>/work", base="seq_base")

ctx = VFXContext(show="demo", seq="DEF", shot="0010")
path = resolver.resolve("shot", ctx)
# V:\shows\demo\seq\DEF\0010\work
```

## Token Formatters

Format values during path generation:
```python
# Padding, case conversion, defaults
resolver.register("formatted", "V:/shows/<show:upper>/seq/<seq>/v<version:03>")
ctx = VFXContext(show="demo", seq="DEF", version="2")
path = resolver.resolve("formatted", ctx)
# V:\shows\DEMO\seq\DEF\v002

# Available: :04 (padding), :upper, :lower, :title, :default=value
```

## Normalizers

Sanitize values automatically:
```python
def spaces_to_underscores(value: str) -> str:
    return value.replace(" ", "_")

normalizers = {"show": spaces_to_underscores}
resolver = PathResolver(VFXContext, normalizers=normalizers)

ctx = VFXContext(show="My Show", seq="DEF")
path = resolver.resolve("shot", ctx)
# V:\shows\My_Show\seq\DEF
```

## Validation

Check if a context has all required tokens before building paths:
```python
resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>")

ctx = VFXContext(show="demo", seq="DEF")
is_valid, missing = resolver.validate("shot", ctx)

if is_valid:
    path = resolver.resolve("shot", ctx)
else:
    print(f"Missing tokens: {missing}")  # ['shot']

# Tokens with defaults are always valid
resolver.register("with_default", "V:/shows/<show>/ep/<episode:default=pilot>")
ctx = VFXContext(show="demo")
is_valid, missing = resolver.validate("with_default", ctx)
# is_valid=True, missing=[]
```

## CompositeResolver

Manage multiple context types in one resolver:
```python
from templar import CompositeResolver

composite = CompositeResolver()
composite.register(ShotContext, "shot", "V:/shows/<show>/seq/<seq>/<shot>")
composite.register(AssetContext, "asset", "V:/assets/<category>/<asset>")

shot_ctx = ShotContext(show="demo", seq="DEF", shot="0010")
asset_ctx = AssetContext(category="props", asset="table")

shot_path = composite.resolve("shot", shot_ctx)
asset_path = composite.resolve("asset", asset_ctx)
```

## Query

Find existing files on disk that match your templates:

```python
from pathlib import Path
from templar import PathResolver, Query

resolver = PathResolver(VFXContext)
resolver.register("shot", "V:/shows/<show>/seq/<seq>/<shot>")

# Search a directory tree for all shots
query = Query(resolver, Path("V:/shows"))

# Find all shots in a specific show
for ctx in query.query(show="demo"):
    print(f"{ctx.show}/{ctx.seq}/{ctx.shot}")
# demo/DEF/0010
# demo/DEF/0020
# demo/DEF/0030

# Find shots matching multiple criteria
for ctx in query.query(show="demo", seq="DEF"):
    print(f"{ctx.shot}")
# 0010
# 0020

# Find all shots (no filters)
for ctx in query.query():
    print(f"{ctx.show}/{ctx.seq}/{ctx.shot}")
```

Templar provides three caching strategies for improved query performance:

### CachedQuery - Simple Full Caching

Caches all results for fast repeated queries.
```python
from templar import CachedQuery

query = CachedQuery(resolver, Path("V:/shows"), cache_timeout=300.0)

# First query - scans filesystem
for ctx in query.query(show="demo"):
    print(ctx.shot)

# Second query - uses cache (instant)
for ctx in query.query(show="demo"):
    print(ctx.shot)

# Manual invalidation
query.invalidate_cache()
```

### TwoTierCachedQuery - Separate Path/Parse Caching

Caches filesystem scanning and parsing separately for memory efficiency.
```python
from templar import TwoTierCachedQuery

query = TwoTierCachedQuery(
    resolver, 
    Path("V:/shows"),
    path_cache_timeout=600.0,    # Filesystem scan cache
    parse_cache_timeout=60.0     # Parse results cache
)

# Invalidate only parsing (keeps filesystem scan)
query.invalidate_parse_cache()

# Invalidate only paths
query.invalidate_path_cache()

# Invalidate both
query.invalidate_all()
```

### LazyQuery - Selective Caching

Only caches specific filter combinations that have been queried.
```python
from templar import LazyQuery

query = LazyQuery(resolver, Path("V:/shows"))

# Each unique filter combination caches separately
list(query.query(show="demo"))            # Caches: show="demo"
list(query.query(show="demo", seq="ABC")) # Caches: show="demo" + seq="ABC"

# Invalidate specific filter combination
query.invalidate_cache(show="demo")

# Invalidate all
query.invalidate_all()
```

## Structure Generation

Create entire directory structures by expanding registered token values:

```python
from templar import PathResolver

@dataclass
class AssetContext:
    project: Optional[str] = None
    category: Optional[str] = None
    asset: Optional[str] = None
    dept: Optional[str] = None
    status: Optional[str] = None

resolver = PathResolver(AssetContext)
resolver.register(
    "asset",
    "T:/projects/<project>/assets/<category>/<asset>/<dept>/<status>"
)

# Register all possible values for tokens
resolver.register_token_values('dept', ['model', 'rig', 'anim'])
resolver.register_token_values('status', ['work', 'publish'])

# Create all combinations
ctx = AssetContext(project='demo', category='char', asset='skeleton_king')
paths = resolver.create_structure('asset', ctx)

# T:/projects/demo/assets/char/skeleton_king/anim/publish
# T:/projects/demo/assets/char/skeleton_king/anim/work
# T:/projects/demo/assets/char/skeleton_king/model/publish
# T:/projects/demo/assets/char/skeleton_king/model/work
# T:/projects/demo/assets/char/skeleton_king/rig/publish
# T:/projects/demo/assets/char/skeleton_king/rig/work

# Dry run to preview without creating
paths = resolver.create_structure('asset', ctx, dry_run=True)
```

The `stop_at_token` parameter controls expansion depth - only tokens **before** it are expanded. Tokens already populated in the context are skipped.

## Dict Configuration

Templates can be loaded from a dict formatted like so:

```python
data = {
  "show_base": "V:/shows/<show>",
  "seq_base": {
    "pattern": "seq/<seq>",
    "base": "show_base"
  },
  "shot": {
    "pattern": "<shot>/__pub__",
    "base": "seq_base"
  }
}

resolver.from_dict(data)
```
