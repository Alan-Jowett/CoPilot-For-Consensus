# Dependency Management Strategy

This document explains how dependencies are managed across Docker containers, CI environments, and local development to ensure all driver implementations have their required packages available.

## Problem Statement

Each adapter (e.g., `copilot_embedding`, `copilot_vectorstore`) supports multiple drivers:
- **copilot_embedding**: mock, sentencetransformers, openai, azure_openai, huggingface
- **copilot_vectorstore**: qdrant, azure_ai_search, faiss, inmemory
- **copilot_metrics**: prometheus, pushgateway, prometheus_pushgateway, azure_monitor, noop

Each driver has specific dependencies that must be installed for that driver to work. However:
1. **Docker containers** should only install dependencies needed for their configured drivers (minimize image size)
2. **CI tests** should validate ALL drivers can be instantiated (comprehensive testing)
3. **Local development** should support flexible installation (developer choice)

## Solution: Setuptools Extras

Each adapter's `setup.py` defines extras for different use cases:

### 1. Driver-Specific Extras

Install only the dependencies for one driver:

```bash
# Install only Qdrant driver dependencies
pip install -e adapters/copilot_vectorstore[qdrant]

# Install only Azure OpenAI embedding dependencies
pip install -e adapters/copilot_embedding[openai]
```

### 2. The "all" Extra

Install ALL driver dependencies for an adapter:

```bash
# Install all vectorstore backends
pip install -e adapters/copilot_vectorstore[all]

# Install all embedding backends
pip install -e adapters/copilot_embedding[all]
```

### 3. The "test" Extra

Install ALL dependencies needed for comprehensive factory testing:

```bash
# Install adapter with all drivers for testing
pip install -e adapters/copilot_embedding[test]
```

The `[test]` extra includes:
- `pytest` and `pytest-cov` for testing
- ALL driver-specific dependencies
- Any optional validation/schema dependencies

## Usage by Environment

### Docker Containers (Production)

**Goal:** Complete images with all driver dependencies (currently)

**Current Strategy (v1.0):** Install ALL drivers to prevent deployment failures

Example from `embedding/Dockerfile`:
```dockerfile
# Install all vectorstore backends
RUN pip install -e /app/adapters/copilot_vectorstore[all]

# Install all embedding backends
RUN pip install -e /app/adapters/copilot_embedding[all]
```

**Why:** Ensures no deployment fails due to missing dependencies. Images are larger but comprehensive.

**Future Strategy (v2.0):** Build separate optimized images:
- `embedding-azure.Dockerfile` - only Azure drivers: `[azure]`
- `embedding-oss.Dockerfile` - only OSS drivers: `[qdrant,sentencetransformers]`

**When to update:** Currently using `[all]` for all services. Will change when building specialized images.

### CI Unit Tests

**Goal:** Test ALL drivers can be instantiated (catch missing dependencies)

From `.github/workflows/adapter-reusable-unit-test-ci.yml`:
```yaml
- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install pytest pytest-cov pytest-timeout==2.4.0
    python adapters/scripts/install_adapters.py ${{ inputs.adapter_id }}
    # Install test extra (includes all driver dependencies)
    pip install -e "adapters/${{ inputs.adapter_id }}[test]" 2>/dev/null || echo "No test extra available"
```

**Why:** The `[test]` extra ensures factory tests (e.g., `test_factory_all_drivers.py`) can instantiate every driver listed in the schema. This validates:
1. All required dependencies are declared in `setup.py`
2. All drivers can be imported and instantiated
3. Schema and code stay in sync

### Local Development

**Goal:** Flexible installation based on developer needs

```bash
# Install everything in virtual environment
.venv/Scripts/python.exe -m pip install -e adapters/copilot_embedding[all]

# Or install only what you need
.venv/Scripts/python.exe -m pip install -e adapters/copilot_embedding[openai]

# Install for comprehensive testing
.venv/Scripts/python.exe -m pip install -e adapters/copilot_embedding[test]
```

## Adding a New Driver

When adding a new driver to an adapter:

### 1. Add Dependencies to setup.py

```python
extras_require={
    # ... existing extras ...
    "newdriver": [
        "some-new-package>=1.0.0",
    ],
    # Update "all" extra
    "all": [
        # ... existing packages ...
        "some-new-package>=1.0.0",
    ],
    # Update "test" extra
    "test": [
        "pytest>=7.0.0",
        "pytest-cov>=4.0.0",
        # ... all driver packages ...
        "some-new-package>=1.0.0",
    ],
}
```

### 2. Update Schema

Add the driver to `docs/schemas/configs/adapters/{adapter}.json`:
```json
{
  "properties": {
    "discriminant": {
      "enum": ["existing", "drivers", "newdriver"]
    }
  }
}
```

### 3. Factory Tests Automatically Discover It

The `test_factory_all_drivers.py` tests read the schema enum dynamically:
```python
drivers_enum = schema["properties"]["discriminant"]["enum"]
for driver in drivers_enum:
    # Test will automatically include "newdriver"
    ...
```

### 4. Update Docker Build (if needed)

If the new driver should be available in Docker, update the Dockerfile:
```dockerfile
RUN pip install -e /app/adapters/copilot_adapter[existing,newdriver]
```

## Verification

### Check CI Has All Dependencies

Run unit tests locally with the `[test]` extra:
```powershell
.\.venv\Scripts\python.exe -m pip install -e adapters/copilot_embedding[test]
.\.venv\Scripts\python.exe -m pytest adapters/copilot_embedding/tests/test_factory_all_drivers.py -v
```

Expected: All drivers instantiate successfully (PASSED).

### Check Docker Has Required Dependencies

Build and test the Docker image:
```powershell
docker build -t embedding:test -f embedding/Dockerfile .
docker run --rm embedding:test python -c "from copilot_embedding.factory import create_embedding_provider"
```

Expected: No ImportError.

### Check Schema-Factory Alignment

The factory tests validate this automatically. If a schema lists a driver but the factory doesn't support it, the test fails with:
```
ValueError: Unsupported driver: newdriver
```

## Benefits of This Approach

✅ **Docker images stay lean** - only install what's configured  
✅ **CI tests are comprehensive** - validate all drivers work  
✅ **Developers have flexibility** - install what they need  
✅ **Dependencies are centralized** - defined once in setup.py  
✅ **Tests stay synchronized** - schema changes automatically update tests  
✅ **New drivers are easy** - just update setup.py extras and schema  

## Troubleshooting

### CI Test Fails: "ModuleNotFoundError: No module named 'X'"

**Cause:** Driver dependency not listed in `[test]` extra.

**Fix:** Add the package to `setup.py` extras:
```python
"test": [
    "pytest>=7.0.0",
    "X>=1.0.0",  # Add missing package
],
```

### Docker Container Fails: "ImportError: cannot import name 'X'"

**Cause:** Driver not installed in Docker image.

**Fix:** Update Dockerfile to include the driver's extra:
```dockerfile
RUN pip install -e /app/adapters/copilot_adapter[driver]
```

### Factory Test Fails: "DriverConfig has no schema-defined key 'X'"

**Cause:** Test helper function doesn't populate all schema fields.

**Fix:** Update `get_minimal_config()` in the test to include all properties from schema:
```python
if "properties" in driver_schema:
    for field, field_schema in driver_schema["properties"].items():
        if field in defaults:
            config_dict[field] = defaults[field]
        elif "default" in field_schema:
            config_dict[field] = field_schema["default"]
```

## Summary

- **`setup.py` extras**: Source of truth for dependencies
- **`[test]` extra**: Used by CI for comprehensive testing
- **Docker**: Installs specific extras for production drivers
- **Factory tests**: Automatically validate all schema-declared drivers
- **Schema-driven**: Tests read enum from schema, no hardcoding

This strategy ensures dependencies are available where needed while maintaining flexibility and minimizing bloat.
