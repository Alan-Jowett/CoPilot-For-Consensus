<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Schema-Driven Configuration Principles

This project is converging on **JSON Schemas as the single source of truth** for configuration shape, requiredness, defaults, and constraints.

The primary goal is to be able to reason about configuration correctness *ahead of time* (including comparing schemas against deployment templates like Bicep), rather than discovering missing/invalid configuration at runtime.

***

## Principles

### 1) Schemas define requirements and constraints

- **Requiredness lives in schema** via the schema-level `required: [...]` list.
- **Constraints live in schema**, e.g.:
  - non-empty strings: `minLength: 1`
  - bounded numbers: `minimum` / `maximum`
  - enumerations: `enum: [...]`
  - format/pattern validation: `format` / `pattern`
  - mutually exclusive credential sets: `oneOf` + a driver-level discriminant

Code should not duplicate schema constraints unless there is no viable schema encoding.

### 2) Defaults live in schema

- Any default value should be defined in the JSON Schema via `default`.
- Provider/driver code should not “invent” defaults.
- Generated dataclasses should reflect schema defaults so a config object is fully self-describing.

### 3) Generated dataclasses mirror the schema (type-level enforcement)

Generated config dataclasses (under `adapters/copilot_config/copilot_config/generated/**`) must:

- Use **non-Optional fields** for schema-required properties.
- Use **non-Optional fields** for properties with non-null schema defaults.
- Use `Optional[...] = None` only when the schema permits “not provided” (or explicitly allows null).

This ensures:
- Misconfigurations surface early via type errors (and are caught by tests/static analysis).
- The dataclass model stays aligned with the schema intent.

### 4) Loaders must fail fast and be schema-driven

Configuration loaders must:

- Load values using schema metadata (`source`, `env_var`, `secret_name`, etc.).
- Apply schema defaults.
- Fail fast on missing schema-required fields with **clear errors** that tell operators what variable/secret is missing.

This avoids partially-initialized configs and late failures inside providers.

### 5) Providers map config → implementation (no policy)

Provider/driver code should:

- Assume it receives a valid, typed config object.
- Focus on mapping config to library/client initialization.
- Avoid enforcing required fields or constraints already expressed in schema.

Providers may still validate *runtime inputs* (e.g., user text passed to an embedding call).

### 6) Complex configuration must be modeled explicitly

When a driver has mutually exclusive configuration modes (e.g., multiple auth strategies), model it explicitly in schema:

- Prefer a driver schema with `oneOf` variants.
- Use a driver-level `discriminant` (with `env_var`) to select a variant.
- Ensure each variant has `additionalProperties: false` to prevent silent typos.

The generator and loaders should select and instantiate the correct typed variant.

***

## How this helps deployment reasoning (Bicep, CI, and ops)

When schemas fully describe:

- which values must exist,
- which names they come from (env/secret), and
- what constraints they must satisfy,

we can:

- compare schema requirements against Bicep/container-app env var definitions,
- detect missing values before deployment,
- and avoid waiting for runtime crashes in a service container.

***

## Practical guidance for contributors

- When adding a new config field:
  - add it to the schema first, including `source` and any constraints/defaults.
  - regenerate typed configs.
  - keep provider changes as mapping-only.

- When you feel tempted to add `if not config.foo: raise ...`:
  - first ask: can this be expressed in the schema (e.g., `required`, `minLength`, `pattern`, `enum`)?
  - if yes: encode it there and remove the code-level check.

- When constraints cannot be expressed (rare):
  - document the reason, add a minimal runtime check, and prefer to keep it centralized (loader/factory) rather than scattered across providers.

***

## Pointers

- Schemas: `docs/schemas/configs/**`
- Generator: `scripts/generate_typed_configs.py`
- Typed runtime loader: `adapters/copilot_config/copilot_config/runtime_loader.py`
- Hierarchical loader: `adapters/copilot_config/copilot_config/typed_config.py`
