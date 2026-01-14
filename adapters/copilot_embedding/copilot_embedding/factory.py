# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating embedding providers."""

import logging
import re
from pathlib import Path
from typing import Union

from copilot_config.generated.adapters.embedding_backend import (
    AdapterConfig_EmbeddingBackend,
    DriverConfig_EmbeddingBackend_AzureOpenai,
    DriverConfig_EmbeddingBackend_Huggingface,
    DriverConfig_EmbeddingBackend_Mock,
    DriverConfig_EmbeddingBackend_Openai,
    DriverConfig_EmbeddingBackend_Sentencetransformers,
)

from .base import EmbeddingProvider
from .huggingface_provider import HuggingFaceEmbeddingProvider
from .mock_provider import MockEmbeddingProvider
from .openai_provider import OpenAIEmbeddingProvider
from .sentence_transformer_provider import SentenceTransformerEmbeddingProvider

logger = logging.getLogger(__name__)


EmbeddingBackendDriverConfig = Union[
    DriverConfig_EmbeddingBackend_AzureOpenai,
    DriverConfig_EmbeddingBackend_Huggingface,
    DriverConfig_EmbeddingBackend_Mock,
    DriverConfig_EmbeddingBackend_Openai,
    DriverConfig_EmbeddingBackend_Sentencetransformers,
]


def _resolve_schema_directory() -> Path | None:
    """Resolve the repository schema directory if available.

    In installed package environments the docs/ folder may not exist; in that
    case we fall back to dataclass-derived validation only.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs" / "schemas" / "configs"
        if candidate.exists():
            return candidate
    return None


def _load_embedding_driver_schema(driver: str) -> dict | None:
    schema_dir = _resolve_schema_directory()
    if schema_dir is None:
        return None

    mapping = {
        "openai": "embedding_openai.json",
        "azure_openai": "embedding_azure_openai.json",
        "sentencetransformers": "embedding_sentencetransformers.json",
        "huggingface": "embedding_huggingface.json",
        "mock": "embedding_mock.json",
    }

    file_name = mapping.get(driver)
    if not file_name:
        return None

    schema_path = schema_dir / "adapters" / "drivers" / "embedding_backend" / file_name
    if not schema_path.exists():
        return None

    import json

    return json.loads(schema_path.read_text(encoding="utf-8"))


def _is_missing_required_value(value, prop_spec: dict) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        min_length = prop_spec.get("minLength")
        if isinstance(min_length, int) and min_length >= 1:
            if len(value.strip()) < min_length:
                return True
    return False


def _validate_config_against_schema(driver: str, config: object) -> None:
    """Validate a driver config instance against its JSON schema.

    This keeps 'what is required/valid' in schema while making the factory fail
    fast (useful for early deployment diagnostics and unit tests).
    """
    schema = _load_embedding_driver_schema(driver)
    if not schema:
        return

    properties = schema.get("properties", {})
    required = schema.get("required", [])
    required_fields = set(required) if isinstance(required, list) else set()

    for field_name in sorted(required_fields):
        spec = properties.get(field_name, {})
        if not isinstance(spec, dict):
            spec = {}
        value = getattr(config, field_name, None)

        if _is_missing_required_value(value, spec):
            raise ValueError(f"{field_name} parameter is required")

    # Validate provided (non-missing) optional fields too.
    for field_name, spec in properties.items():
        if not isinstance(spec, dict):
            continue
        value = getattr(config, field_name, None)
        if value is None:
            continue

        if isinstance(value, str):
            min_length = spec.get("minLength")
            if isinstance(min_length, int) and min_length >= 1 and len(value.strip()) < min_length:
                raise ValueError(f"{field_name} parameter is required")

            pattern = spec.get("pattern")
            if isinstance(pattern, str) and pattern:
                if re.match(pattern, value) is None:
                    raise ValueError(f"{field_name} parameter is invalid")

            enum = spec.get("enum")
            if isinstance(enum, list) and enum and value not in enum:
                raise ValueError(f"{field_name} parameter is invalid")



def create_embedding_provider(
    driver_name: str | AdapterConfig_EmbeddingBackend,
    driver_config: EmbeddingBackendDriverConfig | None = None,
) -> EmbeddingProvider:
    """Create an embedding provider from configuration.

    Args:
        driver_name:
            Backend type (required) or an adapter config object.
            Options: 'mock', 'sentencetransformers', 'openai', 'azure', 'azure_openai', 'huggingface'
        driver_config: Driver configuration for the selected backend.

    Returns:
        EmbeddingProvider instance

    Raises:
        ValueError: If driver_name is unknown or required configuration is missing
    """
    if isinstance(driver_name, AdapterConfig_EmbeddingBackend):
        adapter_config = driver_name
        backend = str(adapter_config.embedding_backend_type).lower()
        config = adapter_config.driver
    else:
        if not driver_name:
            raise ValueError(
                "driver_name parameter is required. "
                "Must be one of: mock, sentencetransformers, openai, azure, azure_openai, huggingface"
            )

        backend = str(driver_name).lower()
        config = driver_config

    if backend == "azure":
        backend = "azure_openai"

    if config is None:
        raise ValueError(
            "driver_name parameter is required. "
            "Must be one of: mock, sentencetransformers, openai, azure, azure_openai, huggingface"
        )

    logger.info(f"Creating embedding provider with backend: {backend}")

    # Fail fast on misconfiguration using schema-driven validation.
    _validate_config_against_schema(backend, config)

    if backend == "mock":
        return MockEmbeddingProvider.from_config(config)

    if backend == "sentencetransformers":
        return SentenceTransformerEmbeddingProvider.from_config(config)

    if backend == "openai":
        return OpenAIEmbeddingProvider.from_config(config, driver_name="openai")

    if backend == "azure_openai":
        return OpenAIEmbeddingProvider.from_config(config, driver_name="azure_openai")

    if backend == "huggingface":
        return HuggingFaceEmbeddingProvider.from_config(config)

    raise ValueError(
        f"Unknown embedding backend driver: {backend}. "
        f"Supported backends: mock, sentencetransformers, openai, azure_openai, huggingface"
    )
