# Generated Typed Configuration

This directory contains auto-generated Python dataclasses that provide strongly-typed configuration objects for all services.

## DO NOT EDIT MANUALLY

**These files are generated from JSON schemas** by `scripts/generate_typed_configs.py`. Any manual changes will be overwritten on the next generation run.

## File Structure (1:1 Schema-to-Module Mapping)

The generated modules mirror the schema file organization for clarity and modularity:

```
generated/
├── adapters/           # One module per adapter (matches docs/schemas/configs/adapters/)
│   ├── metrics.py      # Contains AdapterConfig_Metrics + all metrics drivers
│   ├── logger.py       # Contains AdapterConfig_Logger + all logger drivers
│   ├── document_store.py
│   └── ...
└── services/           # One module per service (matches docs/schemas/configs/services/)
    ├── ingestion.py    # Imports only the adapters it needs
    ├── parsing.py
    └── ...
```

This **1:1 mapping** between schema files and Python modules means:
- **Adapters are self-contained**: `adapters/metrics.py` has everything metrics-related
- **Services import what they need**: `services/ingestion.py` imports only `AdapterConfig_Metrics`, etc.
- **Drivers can reference their config**: A metrics driver only needs to import `adapters.metrics`

## Regenerating Typed Configs

When you modify a schema file in `docs/schemas/configs/`, regenerate the typed configs:

```bash
# For a specific adapter
python scripts/generate_typed_configs.py --adapter metrics

# For a specific service
python scripts/generate_typed_configs.py --service ingestion

# For everything (adapters + services)
python scripts/generate_typed_configs.py --all
```

## Usage Examples

### Service using typed config

```python
from copilot_config import get_config

# Load typed config for ingestion service
config = get_config("ingestion")

# Access service settings (fully typed)
batch_size: int = config.service_settings.batch_size
http_port: int = config.service_settings.http_port
```

### Adapter factory using typed config

```python
from copilot_config.generated.adapters.metrics import AdapterConfig_Metrics

def create_metrics_adapter(config: AdapterConfig_Metrics):
    # config.metrics_type is Literal["prometheus", "pushgateway", "noop", "azure_monitor"]
    if config.metrics_type == "pushgateway":
        # config.driver is type-narrowed to DriverConfig_Metrics_Pushgateway
        return PushgatewayMetrics(config.driver.gateway, config.driver.job)
    # ... other drivers
```

### Driver using typed config

```python
from copilot_config.generated.adapters.metrics import DriverConfig_Metrics_Pushgateway

class PushgatewayMetrics:
    def __init__(self, config: DriverConfig_Metrics_Pushgateway):
        # config.gateway is guaranteed to be a str (required field)
        # config.job is str | None (optional field)
        self.gateway = config.gateway
        self.job = config.job
```

## Type Safety Benefits

1. **IDE autocomplete** for all configuration fields
2. **Static type checking** with mypy/pyright
3. **Catch typos at development time**, not runtime
4. **No guessing** about field names, types, or defaults
5. **Schema is the single source of truth**
6. **1:1 mapping** makes it easy to find the right module
7. **Modular imports** - only import what you need

## CI Drift Protection

The CI pipeline includes a drift check that ensures generated files match the schemas. If schemas change without regenerating the typed configs, CI will fail with clear instructions on how to fix it.

## Architecture Goals

The 1:1 schema-to-module mapping supports:

1. **Pylance/mypy validation**: Each component can import only its config type
2. **Clear boundaries**: Services don't need to know about driver internals
3. **Easier testing**: Mock just the adapter config module you need
4. **Future extensibility**: New adapters/drivers just add new modules

This structure aligns with the long-term goal of using static analysis tools to validate that services, adapters, and drivers correctly use their configuration data.
