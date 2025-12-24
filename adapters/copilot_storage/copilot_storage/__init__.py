# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Storage Adapter.

A shared library for document storage across microservices
in the Copilot-for-Consensus system.
"""

__version__ = "0.1.0"

from .azure_cosmos_document_store import AzureCosmosDocumentStore
from .document_store import (
    DocumentNotFoundError,
    DocumentStore,
    DocumentStoreConnectionError,
    DocumentStoreError,
    DocumentStoreNotConnectedError,
    create_document_store,
)
from .inmemory_document_store import InMemoryDocumentStore
from .mongo_document_store import MongoDocumentStore
from .validating_document_store import DocumentValidationError, ValidatingDocumentStore

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
