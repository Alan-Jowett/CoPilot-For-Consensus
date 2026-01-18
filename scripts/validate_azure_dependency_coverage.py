#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Validate Azure deployment dependency coverage.

This script aims to prevent drift between:
- Azure infra configuration (Bicep) that selects adapter drivers/backends, and
- Azure-optimized Docker images that must include the corresponding Python deps.

It is intentionally conservative:
- It validates *what services actually import* (copilot_* adapters) against what
  their Dockerfile.azure installs.
- It validates a small set of known Azure driver types against adapter packaging
  metadata (setup.py install_requires/extras_require).

Run:
  python scripts/validate_azure_dependency_coverage.py
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BICEP_PATH = REPO_ROOT / "infra" / "azure" / "modules" / "containerapps.bicep"

SERVICE_DOCKERFILE = "Dockerfile.azure"


@dataclass(frozen=True)
class AdapterPackaging:
    install_requires: set[str]
    extras_require: dict[str, set[str]]


def _parse_bicep_container_envs(bicep_path: Path) -> dict[str, dict[str, str]]:
    """Return mapping of container name -> env var name -> raw value expression.

    Notes / assumptions (intentionally simple parser):
    - Expects env blocks in the form `env: [` on a single line.
    - Expects each env entry as separate `name:` and `value:` lines.
    - Multi-line value expressions are not supported; only the first `value:` line is
        captured.
    - Used to detect driver selections like `VECTOR_STORE_TYPE` to validate that
        Dockerfile.azure installs the right adapter extras.
    """
    if not bicep_path.exists():
        raise FileNotFoundError(f"Bicep file not found: {bicep_path}")

    envs: dict[str, dict[str, str]] = {}
    current_container: str | None = None
    in_env = False
    current_var: str | None = None

    for line_number, raw_line in enumerate(bicep_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()

        # Detect container name: typically lowercase service name (e.g., 'reporting')
        # Avoid env var names (UPPER_SNAKE_CASE) and interpolated resource names.
        m_container = re.search(r"\bname:\s*'([A-Za-z0-9_-]+)'", line)
        if m_container:
            candidate = m_container.group(1)
            # Skip obvious env-var-style names (UPPER_SNAKE_CASE), which are not containers.
            if not re.fullmatch(r"[A-Z0-9_]+", candidate):
                # Ignore common non-container names that can appear in other contexts
                if candidate not in {"Consumption"}:
                    current_container = candidate

        if line.startswith("env:") and line.endswith("[") and current_container:
            in_env = True
            envs.setdefault(current_container, {})
            current_var = None
            continue

        if in_env and line == "]":
            in_env = False
            current_var = None
            continue

        if not in_env:
            continue

        m_var = re.match(r"name:\s*'([A-Z0-9_]+)'\s*$", line)
        if m_var:
            current_var = m_var.group(1)
            continue

        if current_var and line.startswith("value:"):
            value_expr = line.removeprefix("value:").strip()
            envs[current_container][current_var] = value_expr

            # Heuristic warning for multi-line expressions. This parser is simple on purpose;
            # if a value continues onto the next line, our captured expression may be incomplete.
            if not value_expr or value_expr.endswith(("(", "[", "{", "+", "?", ":", ",")):
                print(
                    f"Warning: {bicep_path}:{line_number}: multi-line env value for '{current_var}' "
                    "is not supported; parsing may be incomplete.",
                    file=sys.stderr,
                )

            current_var = None

    return envs


def _find_service_dirs(repo_root: Path) -> dict[str, Path]:
    """Return mapping of service name -> service dir for Azure-optimized images."""
    services: dict[str, Path] = {}
    for dockerfile in repo_root.glob(f"*/{SERVICE_DOCKERFILE}"):
        service_dir = dockerfile.parent
        if service_dir.name == "adapters":
            continue
        services[service_dir.name] = service_dir
    return services


def _scan_imported_adapters(service_dir: Path) -> set[str]:
    """Scan service Python code for imports of copilot_* adapters."""
    imported: set[str] = set()

    def _is_test_or_cache_file(path: Path) -> bool:
        try:
            rel_path = path.relative_to(service_dir)
        except ValueError:
            rel_path = path

        parts = rel_path.parts
        return "tests" in parts or "__pycache__" in parts

    def iter_py_files() -> list[Path]:
        return [p for p in service_dir.rglob("*.py") if not _is_test_or_cache_file(p)]

    for py_file in iter_py_files():
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError as exc:
            raise RuntimeError(f"Failed to parse Python file: {py_file}: {exc}") from exc

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root.startswith("copilot_"):
                        imported.add(root)
            elif isinstance(node, ast.ImportFrom):
                if not node.module:
                    continue
                root = node.module.split(".", 1)[0]
                if root.startswith("copilot_"):
                    imported.add(root)

    return imported


def _parse_dockerfile_installs(dockerfile_path: Path) -> tuple[set[str], dict[str, set[str]]]:
    """Return (installed_adapters, extras_by_adapter) from a Dockerfile.azure."""
    text = dockerfile_path.read_text(encoding="utf-8")
    installed: set[str] = set()
    extras: dict[str, set[str]] = {}

    lines = text.splitlines()

    # Parse install_adapters.py invocation blocks (multi-line RUN with \\)
    in_block = False
    for line in lines:
        if "install_adapters.py" in line:
            in_block = True

        if in_block:
            line_wo_comment = line.split("#", 1)[0]
            for m in re.finditer(
                r"(?:^|[\s\\])(?P<adapter>copilot_[a-z0-9_]+)(?=$|[\s\\])",
                line_wo_comment,
            ):
                installed.add(m.group("adapter"))
            if not line.rstrip().endswith("\\"):
                in_block = False

    # Parse explicit editable installs with extras
    for m in re.finditer(
        r"pip\s+install\s+-e\s+/app/adapters/(?P<adapter>copilot_[a-z0-9_]+)(?:\[(?P<extras>[^\]]+)\])?",
        text,
    ):
        adapter = m.group("adapter")
        installed.add(adapter)
        extras_raw = m.group("extras")
        if extras_raw:
            extras_set = {e.strip() for e in extras_raw.split(",") if e.strip()}
            extras.setdefault(adapter, set()).update(extras_set)

    return installed, extras


def _is_setup_call(node: ast.expr) -> bool:
    if isinstance(node, ast.Name) and node.id == "setup":
        return True
    if isinstance(node, ast.Attribute) and node.attr == "setup":
        return True
    return False


def _parse_adapter_packaging(adapter_dir: Path) -> AdapterPackaging:
    setup_path = adapter_dir / "setup.py"
    if not setup_path.exists():
        return AdapterPackaging(install_requires=set(), extras_require={})

    install_requires: set[str] = set()
    extras_require: dict[str, set[str]] = {}

    try:
        tree = ast.parse(setup_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_setup_call(node.func):
                continue

            for kw in node.keywords:
                if kw.arg == "install_requires":
                    value = ast.literal_eval(kw.value)
                    if isinstance(value, list):
                        install_requires.update(str(item) for item in value)
                if kw.arg == "extras_require":
                    value = ast.literal_eval(kw.value)
                    if isinstance(value, dict):
                        for extra_name, reqs in value.items():
                            if isinstance(reqs, list):
                                extras_require[str(extra_name)] = {str(r) for r in reqs}

    except Exception as exc:
        # Fail-fast: packaging metadata must be parseable to reliably validate
        # required Azure SDK dependencies.
        raise RuntimeError(f"Failed to parse {setup_path}: {exc}") from exc

    return AdapterPackaging(install_requires=install_requires, extras_require=extras_require)


def _check_adapter_has_packages(
    *,
    errors: list[str],
    adapters_root: Path,
    service_name: str,
    adapter: str,
    required_pkgs: list[str],
    extra_hint: str | None = None,
) -> None:
    adapter_dir = adapters_root / adapter
    if not adapter_dir.exists():
        errors.append(f"{service_name}: adapter directory missing: adapters/{adapter}")
        return

    packaging = _parse_adapter_packaging(adapter_dir)
    all_reqs = set(packaging.install_requires)
    for reqs in packaging.extras_require.values():
        all_reqs.update(reqs)

    for pkg in required_pkgs:
        if not _requirement_contains(all_reqs, pkg):
            hint = f" (expected via extras '{extra_hint}')" if extra_hint else ""
            errors.append(
                f"{service_name}: adapters/{adapter}/setup.py does not declare required dependency '{pkg}'{hint}"
            )


def _requirement_contains(requirements: set[str], needle: str) -> bool:
    """Return True if any requirement line contains the given package name."""
    lower = needle.lower()
    return any(lower in req.lower() for req in requirements)


def _get_env_driver_values(env_value_expr: str) -> set[str]:
    """Extract string literal values from a Bicep env var value expression."""
    # Common patterns:
    # - 'qdrant'
    # - vectorStoreBackend == 'qdrant' ? 'qdrant' : 'azure_ai_search'
    # We only extract quoted string literals.
    return set(re.findall(r"'([^']+)'", env_value_expr))


def validate_repo(repo_root: Path = REPO_ROOT, *, bicep_path: Path = BICEP_PATH) -> list[str]:
    errors: list[str] = []

    bicep_envs = _parse_bicep_container_envs(bicep_path)
    services = _find_service_dirs(repo_root)

    adapters_root = repo_root / "adapters"

    for service_name, service_dir in sorted(services.items()):
        dockerfile = service_dir / SERVICE_DOCKERFILE
        installed_adapters, extras_by_adapter = _parse_dockerfile_installs(dockerfile)
        imported_adapters = _scan_imported_adapters(service_dir)

        missing = sorted(imported_adapters - installed_adapters)
        if missing:
            errors.append(
                f"{service_name}: {SERVICE_DOCKERFILE} is missing adapters imported by code: {', '.join(missing)}"
            )

        env = bicep_envs.get(service_name, {})

        # Vector store extras coverage (qdrant vs azure_ai_search)
        if "copilot_vectorstore" in imported_adapters:
            expr = env.get("VECTOR_STORE_TYPE")
            if expr:
                drivers = _get_env_driver_values(expr)
                required_extras: set[str] = set()
                if "qdrant" in drivers:
                    required_extras.add("qdrant")
                if "azure_ai_search" in drivers:
                    required_extras.add("azure")

                declared = extras_by_adapter.get("copilot_vectorstore", set())

                # Treat [all] as covering any required extras, without hardcoding
                # the full set of available extras for copilot_vectorstore.
                if "all" not in declared:
                    missing_extras = sorted(required_extras - declared)
                    if missing_extras:
                        errors.append(
                            f"{service_name}: {SERVICE_DOCKERFILE} should install copilot_vectorstore with extras "
                            f"covering VECTOR_STORE_TYPE={expr} (missing: {', '.join(missing_extras)})"
                        )

        # Embedding backend coverage (azure_openai requires openai extra)
        if "copilot_embedding" in imported_adapters:
            expr = env.get("EMBEDDING_BACKEND_TYPE")
            if expr and "azure_openai" in _get_env_driver_values(expr):
                declared = extras_by_adapter.get("copilot_embedding", set())
                if "openai" not in declared and "all" not in declared:
                    errors.append(
                        f"{service_name}: {SERVICE_DOCKERFILE} should install copilot_embedding[openai] "
                        f"because EMBEDDING_BACKEND_TYPE={expr}"
                    )

        # Summarization/LLM backend coverage (OpenAI-based backends require openai extra)
        if "copilot_summarization" in imported_adapters:
            expr = env.get("LLM_BACKEND_TYPE")
            if expr and any("openai" in v for v in _get_env_driver_values(expr)):
                declared = extras_by_adapter.get("copilot_summarization", set())
                if "openai" not in declared and "all" not in declared:
                    errors.append(
                        f"{service_name}: {SERVICE_DOCKERFILE} should install copilot_summarization[openai] "
                        f"because LLM_BACKEND_TYPE={expr}"
                    )

        # Adapter packaging checks for known Azure driver types used by this service.
        # These checks ensure the adapter declares the required Azure SDK deps.

        # Secrets: Azure Key Vault
        if env.get("SECRET_PROVIDER_TYPE") and "azure_key_vault" in _get_env_driver_values(env["SECRET_PROVIDER_TYPE"]):
            if "copilot_secrets" in imported_adapters:
                _check_adapter_has_packages(
                    errors=errors,
                    adapters_root=adapters_root,
                    service_name=service_name,
                    adapter="copilot_secrets",
                    required_pkgs=["azure-keyvault-secrets", "azure-identity"],
                    extra_hint="azure",
                )

        # Document store: Cosmos DB
        if env.get("DOCUMENT_STORE_TYPE") and "azure_cosmosdb" in _get_env_driver_values(env["DOCUMENT_STORE_TYPE"]):
            if "copilot_storage" in imported_adapters:
                _check_adapter_has_packages(
                    errors=errors,
                    adapters_root=adapters_root,
                    service_name=service_name,
                    adapter="copilot_storage",
                    required_pkgs=["azure-cosmos", "azure-identity"],
                )

        # Message bus: Azure Service Bus
        if env.get("MESSAGE_BUS_TYPE") and "azure_service_bus" in _get_env_driver_values(env["MESSAGE_BUS_TYPE"]):
            if "copilot_message_bus" in imported_adapters:
                _check_adapter_has_packages(
                    errors=errors,
                    adapters_root=adapters_root,
                    service_name=service_name,
                    adapter="copilot_message_bus",
                    required_pkgs=["azure-servicebus", "azure-identity"],
                )

        # Metrics: Azure Monitor
        if env.get("METRICS_TYPE") and "azure_monitor" in _get_env_driver_values(env["METRICS_TYPE"]):
            if "copilot_metrics" in imported_adapters:
                _check_adapter_has_packages(
                    errors=errors,
                    adapters_root=adapters_root,
                    service_name=service_name,
                    adapter="copilot_metrics",
                    required_pkgs=["azure-monitor-opentelemetry-exporter"],
                    extra_hint="azure",
                )

        # Vector store: Azure AI Search
        if env.get("VECTOR_STORE_TYPE") and "azure_ai_search" in _get_env_driver_values(env["VECTOR_STORE_TYPE"]):
            if "copilot_vectorstore" in imported_adapters:
                _check_adapter_has_packages(
                    errors=errors,
                    adapters_root=adapters_root,
                    service_name=service_name,
                    adapter="copilot_vectorstore",
                    required_pkgs=["azure-search-documents", "azure-identity"],
                    extra_hint="azure",
                )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bicep",
        type=Path,
        default=BICEP_PATH,
        help="Path to containerapps.bicep (defaults to repo Azure module)",
    )
    args = parser.parse_args(argv)

    errors = validate_repo(REPO_ROOT, bicep_path=args.bicep)
    if errors:
        print("Dependency coverage validation failed:\n", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    print("Dependency coverage validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
