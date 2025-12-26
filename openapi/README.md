<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# OpenAPI Specifications

This directory contains OpenAPI 3.0 specifications for the Copilot-for-Consensus system.

## Structure

```
openapi/
├── gateway.yaml          # Canonical spec for public API Gateway (spec-first)
└── generated/            # Auto-generated specs for internal services (code-first)
    ├── reporting.yaml    # Reporting service API spec
    ├── ingestion.yaml    # Ingestion service API spec
    ├── auth.yaml         # Authentication service API spec
    └── orchestrator.yaml # Orchestration service API spec
```

## Approach

We use a **hybrid OpenAPI strategy**:

1. **Spec-First for Public Gateway** (`gateway.yaml`)
   - Canonical source of truth for all externally exposed endpoints
   - Drives cloud-native gateway configuration (Azure APIM, AWS API Gateway, GCP API Gateway)
   - Manually maintained and validated in CI
   - Located at: `openapi/gateway.yaml`

2. **Code-First for Internal Services** (`generated/*.yaml`)
   - Auto-generated from FastAPI service definitions
   - Documents internal service interfaces
   - Validated in CI to ensure they're up-to-date
   - Regenerated automatically in CI pipeline

## Usage

### Updating the Gateway Spec

1. Edit `openapi/gateway.yaml` directly
2. Validate locally:
   ```bash
   openapi-spec-validator openapi/gateway.yaml
   ```
3. Generate gateway configurations:
   ```bash
   cd infra/gateway
   ./generate_gateway_config.py --provider nginx --output /tmp/test-nginx
   ```
4. Commit and push - CI will validate and generate configs for all providers

### Generating Internal Service Specs

Internal service specs are generated automatically in CI, but you can generate them locally:

```bash
# Generate spec for a single service
./scripts/generate_service_openapi.py --service reporting

# Generate all service specs
./scripts/generate_service_openapi.py --all

# Generate and validate
./scripts/generate_service_openapi.py --all --validate
```

### Validating Specs

All specs are validated in CI using `openapi-spec-validator`:

```bash
# Install validator
pip install openapi-spec-validator

# Validate gateway spec
openapi-spec-validator openapi/gateway.yaml

# Validate generated service spec
openapi-spec-validator openapi/generated/reporting.yaml
```

## CI/CD Integration

The `.github/workflows/openapi-validation.yml` workflow:

1. Validates `gateway.yaml` syntax and structure
2. Generates internal service specs from code
3. Validates generated specs
4. Fails if specs are missing, invalid, or out of sync
5. Uploads generated specs as artifacts

## Documentation

For detailed information, see:
- [docs/openapi.md](../docs/openapi.md) - Complete OpenAPI workflow guide
- [docs/gateway/overview.md](../docs/gateway/overview.md) - Gateway abstraction overview
- [docs/gateway/extending.md](../docs/gateway/extending.md) - Extending gateway adapters

## Benefits

- **Consistency**: Single source of truth for each API surface
- **Automation**: Gateway configs generated from spec, service specs from code
- **Validation**: CI ensures specs are always valid and up-to-date
- **Documentation**: Auto-generated API docs for contributors
- **Cloud-Native**: Easy deployment to multiple cloud providers
- **Maintainability**: Spec-first for stability, code-first for agility
