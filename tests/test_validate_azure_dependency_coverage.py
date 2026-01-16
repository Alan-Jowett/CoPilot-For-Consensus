# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure dependency coverage validation script."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validate_azure_dependency_coverage import validate_repo


def test_validate_azure_dependency_coverage_has_no_errors():
    repo_root = Path(__file__).resolve().parent.parent

    errors = validate_repo(repo_root)
    assert errors == [], "\n" + "\n".join(errors)


def test_detects_missing_adapter_in_dockerfile(tmp_path: Path):
    repo_root = tmp_path

    # Minimal fake service
    svc = repo_root / "reporting"
    svc.mkdir()
    (svc / "Dockerfile.azure").write_text(
        "RUN python /app/adapters/scripts/install_adapters.py \\\n+  copilot_logging\n",
        encoding="utf-8",
    )
    (svc / "app").mkdir()
    (svc / "app" / "main.py").write_text("import copilot_metrics\n", encoding="utf-8")

    # Minimal bicep
    bicep = repo_root / "infra" / "azure" / "modules"
    bicep.mkdir(parents=True)
    (bicep / "containerapps.bicep").write_text("", encoding="utf-8")

    errors = validate_repo(repo_root, bicep_path=bicep / "containerapps.bicep")
    assert any("missing adapters" in e and "copilot_metrics" in e for e in errors)


def test_detects_missing_vectorstore_extras_for_qdrant(tmp_path: Path):
    repo_root = tmp_path

    svc = repo_root / "embedding"
    svc.mkdir()
    (svc / "Dockerfile.azure").write_text(
        "RUN pip install -e /app/adapters/copilot_vectorstore[azure]\n",
        encoding="utf-8",
    )
    (svc / "app").mkdir()
    (svc / "app" / "main.py").write_text("import copilot_vectorstore\n", encoding="utf-8")

    bicep = repo_root / "infra" / "azure" / "modules"
    bicep.mkdir(parents=True)
    (bicep / "containerapps.bicep").write_text(
        "resource apps 'Microsoft.App/containerApps@2022-03-01' = {\n"
        "  name: 'embedding'\n"
        "  properties: {\n"
        "    template: {\n"
        "      containers: [\n"
        "        {\n"
        "          name: 'embedding'\n"
        "          env: [\n"
        "            {\n"
        "              name: 'VECTOR_STORE_TYPE'\n"
        "              value: 'qdrant'\n"
        "            }\n"
        "          ]\n"
        "        }\n"
        "      ]\n"
        "    }\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    from scripts import validate_azure_dependency_coverage as v

    assert v._find_service_dirs(repo_root) == {"embedding": svc}
    assert v._scan_imported_adapters(svc) == {"copilot_vectorstore"}
    assert v._parse_bicep_container_envs(bicep / "containerapps.bicep") == {
        "embedding": {"VECTOR_STORE_TYPE": "'qdrant'"}
    }
    installed, extras_by_adapter = v._parse_dockerfile_installs(svc / "Dockerfile.azure")
    assert installed == {"copilot_vectorstore"}
    assert extras_by_adapter == {"copilot_vectorstore": {"azure"}}

    errors = validate_repo(repo_root, bicep_path=bicep / "containerapps.bicep")
    assert any("copilot_vectorstore" in e and "missing" in e and "qdrant" in e for e in errors), errors
