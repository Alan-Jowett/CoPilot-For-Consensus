# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Storage Adapter.

A shared library for document storage across microservices
in the Copilot-for-Consensus system.
"""

__version__ = "0.1.0"

from .document_store import (  # noqa: E402
    DocumentNotFoundError,
    DocumentStore,
    DocumentStoreConnectionError,
    DocumentStoreError,
    DocumentStoreNotConnectedError,
)
from .factory import create_document_store  # noqa: E402
from .schema_registry import (  # noqa: E402
    get_collection_fields,
    reset_registry,
    sanitize_document,
    sanitize_documents,
)
from .validating_document_store import (  # noqa: E402
    DocumentValidationError,
    ValidatingDocumentStore,
)

__all__ = [
    "__version__",
    "create_document_store",
    "DocumentStore",
    "DocumentStoreError",
    "DocumentStoreNotConnectedError",
    "DocumentStoreConnectionError",
    "DocumentNotFoundError",
    "DocumentValidationError",
    "ValidatingDocumentStore",
    "get_collection_fields",
    "reset_registry",
    "sanitize_document",
    "sanitize_documents",
]
