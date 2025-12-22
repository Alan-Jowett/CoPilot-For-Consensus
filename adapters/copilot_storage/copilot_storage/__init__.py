# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Storage Adapter.

A shared library for document storage across microservices
in the Copilot-for-Consensus system.
"""

__version__ = "0.1.0"

from .document_store import (
    DocumentStore,
    DocumentStoreError,
    DocumentStoreNotConnectedError,
    DocumentStoreConnectionError,
    DocumentNotFoundError,
    create_document_store,
)
from .mongo_document_store import MongoDocumentStore
from .inmemory_document_store import InMemoryDocumentStore
from .azure_cosmos_document_store import AzureCosmosDocumentStore
from .validating_document_store import ValidatingDocumentStore, DocumentValidationError

__all__ = [
    # Version
    "__version__",
    # Document Stores
    "DocumentStore",
    "MongoDocumentStore",
    "InMemoryDocumentStore",
    "AzureCosmosDocumentStore",
    "create_document_store",
    "ValidatingDocumentStore",
    # Exceptions
    "DocumentStoreError",
    "DocumentStoreNotConnectedError",
    "DocumentStoreConnectionError",
    "DocumentNotFoundError",
    "DocumentValidationError",
]
