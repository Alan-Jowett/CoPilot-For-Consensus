# Generated Typed Configuration

This directory contains auto-generated Python dataclasses that provide strongly-typed configuration objects for all services.

## DO NOT EDIT MANUALLY

**These files are generated from JSON schemas** by `scripts/generate_typed_configs.py`. Any manual changes will be overwritten on the next generation run.

## File Structure

- `common.py` - **Shared adapter and driver classes** used across multiple services (metrics, logger, document_store, etc.)
- `<service>.py` - Service-specific configuration (imports from common.py)

This structure **eliminates duplication** - common adapters like `AdapterConfig_Metrics` and `DriverConfig_Metrics_Prometheus` are defined once in `common.py` and imported by all services that need them.

## Regenerating Typed Configs

When you modify a schema file in `docs/schemas/configs/`, regenerate the typed configs:

```bash
# For a specific service
python scripts/generate_typed_configs.py --service ingestion

# For all services (regenerates common.py too)
python scripts/generate_typed_configs.py --all
```

## Usage Example

Services should use the `get_config()` function to load strongly-typed configuration:

```python
from copilot_config import get_config

# Load typed config for ingestion service
config = get_config("ingestion")

# Access service settings (fully typed)
batch_size: int = config.service_settings.batch_size
http_port: int = config.service_settings.http_port
enable_incremental: bool = config.service_settings.enable_incremental

# Access adapter configs (with discriminant-based driver selection)
if config.metrics:
    metrics_type: Literal["prometheus", "pushgateway", "noop", "azure_monitor"] = config.metrics.metrics_type
    
    # Driver is a union type - use type narrowing or isinstance checks
    if config.metrics.metrics_type == "pushgateway":
        gateway: str = config.metrics.driver.gateway  # Type-safe access
        job: str | None = config.metrics.driver.job

# No need to know whether values came from env, secrets, or defaults!
```

## Type Safety Benefits

1. **IDE autocomplete** for all configuration fields
2. **Static type checking** with mypy/pyright
3. **Catch typos at development time**, not runtime
4. **No guessing** about field names, types, or defaults
5. **Schema is the single source of truth**
6. **No duplication** - common classes defined once in `common.py`

## CI Drift Protection

The CI pipeline includes a drift check that ensures generated files match the schemas. If schemas change without regenerating the typed configs, CI will fail with clear instructions on how to fix it.

## Architecture

The generator uses a two-phase approach:

1. **Phase 1**: Scan all services to collect unique adapters/drivers
2. **Phase 2**: Generate `common.py` with all shared classes
3. **Phase 3**: Generate service-specific files that import from common

This eliminates duplication while maintaining strong typing. Before this optimization, the same adapter classes were duplicated in every service file (2949 total lines). After optimization with a shared common module, we have only 985 total lines (67% reduction).
