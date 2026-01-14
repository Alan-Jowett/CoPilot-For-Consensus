# Generated Typed Configuration

This directory contains auto-generated Python dataclasses that provide strongly-typed configuration objects for all services.

## DO NOT EDIT MANUALLY

**These files are generated from JSON schemas** by `scripts/generate_typed_configs.py`. Any manual changes will be overwritten on the next generation run.

## Regenerating Typed Configs

When you modify a schema file in `docs/schemas/configs/`, regenerate the typed configs:

```bash
# For a specific service
python scripts/generate_typed_configs.py --service ingestion

# For all services
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

## CI Drift Protection

The CI pipeline includes a drift check that ensures generated files match the schemas. If schemas change without regenerating the typed configs, CI will fail with clear instructions on how to fix it.

## File Structure

- `__init__.py` - Package marker
- `ingestion.py` - Typed config for ingestion service
- `parsing.py` - Typed config for parsing service
- `chunking.py` - Typed config for chunking service
- `embedding.py` - Typed config for embedding service
- `orchestrator.py` - Typed config for orchestrator service
- `summarization.py` - Typed config for summarization service
- `reporting.py` - Typed config for reporting service
- `auth.py` - Typed config for auth service

Each file contains:
- `ServiceConfig_<Service>` - Top-level config class
- `ServiceSettings_<Service>` - Service-specific settings
- `AdapterConfig_<Adapter>` - Adapter configuration classes
- `DriverConfig_<Adapter>_<Driver>` - Driver-specific config classes
