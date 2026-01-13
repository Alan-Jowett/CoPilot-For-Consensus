# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Validate Docker Compose configs against service/adapter schemas.

Usage:
    python scripts/validate_compose_config.py --compose docker-compose.yml \
        --compose docker-compose.services.yml --compose docker-compose.infra.yml \
        --env .env [--verbose]

This script resolves environment variables defined in Compose services, applies
.substitutions from the provided .env file, and validates schema discriminants for
services that have JSON schemas (adapter-based microservices). Frontend/proxy
services (ui, gateway) are skipped.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

# Services with adapter schemas
VALIDATED_SERVICES = [
    "auth",
    "reporting",
    "ingestion",
    "parsing",
    "chunking",
    "embedding",
    "orchestrator",
    "summarization",
]

# Services to skip (no schema today)
SKIPPED_SERVICES = [
    "ui",
    "gateway",
]

SCHEMA_BASE = Path(__file__).parent.parent / "docs" / "schemas" / "configs"
SERVICE_SCHEMA_DIR = SCHEMA_BASE / "services"


def load_env_file(env_path: Path) -> Dict[str, str]:
    """Load a .env file into a dict."""
    env_vars: Dict[str, str] = {}
    if not env_path.exists():
        raise FileNotFoundError(f"Env file not found: {env_path}")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_vars[key.strip()] = value.strip()
    return env_vars


def load_compose_file(path: Path) -> dict:
    """Load a compose YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Compose file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def merge_services(compose_docs: List[dict]) -> Dict[str, dict]:
    """Merge services from multiple compose documents (later wins)."""
    merged: Dict[str, dict] = {}
    for doc in compose_docs:
        services = doc.get("services", {}) or {}
        for name, svc in services.items():
            merged[name] = svc
    return merged


def substitute_env(value: str, env: Dict[str, str]) -> Tuple[str | None, bool]:
    """Resolve ${VAR:-default} patterns. Returns (resolved_value, conditional)."""
    pattern = re.compile(r"\$\{([^}:]+)(?::-(.*?))?\}")

    def repl(match: re.Match[str]) -> str:
        var = match.group(1)
        default = match.group(2)
        if var in env:
            return env[var]
        if default is not None:
            return default
        # unresolved
        raise KeyError(var)

    try:
        resolved = pattern.sub(repl, value)
        return resolved, False
    except KeyError:
        return None, True


def collect_service_env(service_name: str, service_def: dict, env_overrides: Dict[str, str]) -> Dict[str, str | None]:
    """Collect resolved env vars for a service."""
    env_block = service_def.get("environment", {}) or {}
    env_vars: Dict[str, str | None] = {}

    if isinstance(env_block, list):
        for entry in env_block:
            if not entry:
                continue
            if "=" in entry:
                key, raw_val = entry.split("=", 1)
                key = key.strip()
                raw_val = raw_val.strip()
                val, conditional = substitute_env(raw_val, env_overrides) if "${" in raw_val else (raw_val, False)
                env_vars[key] = None if conditional else val
            else:
                key = entry.strip()
                env_vars[key] = env_overrides.get(key)
    elif isinstance(env_block, dict):
        for key, raw_val in env_block.items():
            if raw_val is None:
                env_vars[key] = env_overrides.get(key)
                continue
            if isinstance(raw_val, str) and "${" in raw_val:
                val, conditional = substitute_env(raw_val, env_overrides)
                env_vars[key] = None if conditional else val
            else:
                env_vars[key] = str(raw_val)

    # Apply env_file entries (later entries overwrite earlier ones only if not already set)
    env_files = service_def.get("env_file") or []
    if isinstance(env_files, str):
        env_files = [env_files]
    for env_file in env_files:
        env_path = Path(env_file)
        if not env_path.is_absolute():
            env_path = Path.cwd() / env_path
        if not env_path.exists():
            continue
        file_vars = load_env_file(env_path)
        for k, v in file_vars.items():
            env_vars.setdefault(k, v)

    return env_vars


def load_schema(service_name: str) -> dict:
    path = SERVICE_SCHEMA_DIR / f"{service_name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Schema not found for service '{service_name}': {path}")
    import json

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_ref(ref_path: str, base_path: Path) -> dict:
    resolved = (base_path / ref_path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Referenced schema not found: {resolved}")
    import json

    with resolved.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_against_schema(service_name: str, env_vars: Dict[str, str | None], verbose: bool = False) -> List[str]:
    issues: List[str] = []
    schema = load_schema(service_name)
    adapters = schema.get("adapters", {})
    schema_base = SERVICE_SCHEMA_DIR

    for adapter_name, adapter_ref in adapters.items():
        if not isinstance(adapter_ref, dict) or "$ref" not in adapter_ref:
            continue
        try:
            adapter_schema = resolve_ref(adapter_ref["$ref"], schema_base)
            discriminant = adapter_schema.get("properties", {}).get("discriminant")
            if not discriminant:
                continue
            discriminant_env_var = discriminant.get("env_var")
            enum_values = discriminant.get("enum", [])
            required = discriminant.get("required", False)
            if not discriminant_env_var:
                continue

            if discriminant_env_var not in env_vars:
                if required:
                    issues.append(
                        f"[{service_name}] Missing required env var '{discriminant_env_var}' for adapter '{adapter_name}'"
                    )
                continue

            value = env_vars[discriminant_env_var]
            if value is None:
                issues.append(
                    f"[{service_name}] Env var '{discriminant_env_var}' for adapter '{adapter_name}' is conditional/unresolved"
                )
                continue
            if enum_values and value not in enum_values:
                issues.append(
                    f"[{service_name}] Invalid value '{value}' for '{discriminant_env_var}'. Allowed: {enum_values}"
                )
        except FileNotFoundError as exc:
            issues.append(f"[{service_name}] {exc}")
        except Exception as exc:  # pragma: no cover
            issues.append(f"[{service_name}] Error validating adapter '{adapter_name}': {exc}")

    if verbose:
        print(f"Service: {service_name}")
        for key in sorted(env_vars.keys()):
            print(f"  {key} = {env_vars[key] if env_vars[key] is not None else '<unresolved>'}")
        if issues:
            print("  Issues:")
            for issue in issues:
                print(f"    - {issue}")
        print()

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Docker Compose env against schemas")
    parser.add_argument("--compose", action="append", required=True, help="Compose file path (can be repeated)")
    parser.add_argument("--env", dest="env_file", required=True, help="Path to .env overrides")
    parser.add_argument("--verbose", action="store_true", help="Print resolved env vars")
    args = parser.parse_args()

    compose_paths = [Path(p) for p in args.compose]
    env_path = Path(args.env_file)

    env_overrides = load_env_file(env_path)
    compose_docs = [load_compose_file(p) for p in compose_paths]
    services = merge_services(compose_docs)

    issues: List[str] = []
    for service_name, service_def in services.items():
        if service_name in SKIPPED_SERVICES:
            continue
        if service_name not in VALIDATED_SERVICES:
            continue

        env_vars = collect_service_env(service_name, service_def, env_overrides)
        issues.extend(validate_against_schema(service_name, env_vars, verbose=args.verbose))

    if issues:
        print("\n❌ Compose configuration validation failed:")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print("\n✅ Compose configuration is valid for all services")
    return 0


if __name__ == "__main__":
    sys.exit(main())
