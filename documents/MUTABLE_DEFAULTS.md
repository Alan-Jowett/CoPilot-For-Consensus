# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Mutable Default Arguments

## Overview

This document describes the mutable default arguments anti-pattern, why it's problematic, and how we prevent it in this codebase.

## The Problem

In Python, default argument values are evaluated **once** when the function is defined, not each time the function is called. When you use a mutable object (like a list, dictionary, or set) as a default argument, all calls to that function share the same object, leading to unexpected behavior.

### Bad Example

```python
def add_item(item, items=[]):  # ❌ BAD
    items.append(item)
    return items

# First call
result1 = add_item("apple")  # Returns: ["apple"]

# Second call - expects empty list, but gets previous result!
result2 = add_item("banana")  # Returns: ["apple", "banana"] ⚠️ Unexpected!
```

### Why It Happens

The empty list `[]` is created **once** when Python defines the function. Every subsequent call to `add_item()` without providing `items` uses the **same list object**.

## The Solution

Use `None` as the default value and create a new mutable object inside the function:

### Good Example

```python
def add_item(item, items=None):  # ✅ GOOD
    if items is None:
        items = []
    items.append(item)
    return items

# First call
result1 = add_item("apple")  # Returns: ["apple"]

# Second call - gets a fresh list as expected
result2 = add_item("banana")  # Returns: ["banana"] ✓ Correct!
```

## Common Patterns

### Lists

```python
# ❌ Bad
def process_batch(data, results=[]):
    results.append(data)
    return results

# ✅ Good
def process_batch(data, results=None):
    if results is None:
        results = []
    results.append(data)
    return results
```

### Dictionaries

```python
# ❌ Bad
def configure(settings={}):
    settings['configured'] = True
    return settings

# ✅ Good
def configure(settings=None):
    if settings is None:
        settings = {}
    settings['configured'] = True
    return settings
```

### Sets

```python
# ❌ Bad
def track_items(item, seen=set()):
    seen.add(item)
    return seen

# ✅ Good
def track_items(item, seen=None):
    if seen is None:
        seen = set()
    seen.add(item)
    return seen
```

## Detection

This codebase includes automated detection of mutable default arguments:

### Pre-commit Hook

The mutable defaults checker runs automatically before commits:

```bash
# Install pre-commit hooks
pre-commit install

# Manually run the check
pre-commit run mutable-defaults-check --all-files
```

### Manual Check

You can manually run the checker:

```bash
python scripts/check_mutable_defaults.py --root .
```

### CI/CD

The check also runs in GitHub Actions on every pull request and push to main.

## Current Status

✅ **As of the latest scan, this codebase has NO instances of mutable default arguments.**

The codebase was scanned on 2025-12-13 and found to be clean:
- **Files scanned:** 249 Python files
- **Issues found:** 0

## Implementation Details

The checker (`scripts/check_mutable_defaults.py`) uses Python's AST (Abstract Syntax Tree) to detect:

1. **Literal mutable defaults:**
   - `def func(items=[]):`
   - `def func(config={}):`
   - `def func(tags={1, 2}):`

2. **Constructor call defaults:**
   - `def func(items=list()):`
   - `def func(config=dict()):`
   - `def func(tags=set()):`

3. **All function types:**
   - Regular functions (`def`)
   - Async functions (`async def`)
   - Keyword-only arguments (`def func(*, items=[]):`)

## When Is It Safe?

Mutable defaults are **only** safe when you intentionally want to share state across function calls. This is rarely what you want and should be used with extreme caution.

Example of intentional shared state (still not recommended):

```python
def get_cache(cache={}):  # Intentional shared cache
    # This works but is confusing
    # Better to use a class or module-level variable
    return cache
```

Even in these cases, it's clearer to use a class attribute or module-level variable:

```python
# Better approach
_cache = {}

def get_cache():
    return _cache
```

## References

- [Python Common Gotchas - Mutable Default Arguments](https://docs.python-guide.org/writing/gotchas/#mutable-default-arguments)
- [PEP 8 - Programming Recommendations](https://www.python.org/dev/peps/pep-0008/#programming-recommendations)
- [Pylint W0102 - dangerous-default-value](https://pylint.pycqa.org/en/latest/user_guide/messages/warning/dangerous-default-value.html)

## Contributing

When contributing to this codebase:

1. ✅ Always use `None` for optional mutable parameters
2. ✅ Initialize mutable objects inside the function
3. ✅ Run the pre-commit checks before pushing
4. ✅ The CI will catch any issues if you forget

Thank you for helping keep our codebase clean and bug-free!
