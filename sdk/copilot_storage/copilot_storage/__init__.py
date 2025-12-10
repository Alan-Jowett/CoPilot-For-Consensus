# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Storage SDK.

A shared library for document storage across microservices
in the Copilot-for-Consensus system.
"""

__version__ = "0.1.0"

from .document_store import DocumentStore, create_document_store
from .mongo_document_store import MongoDocumentStore
from .inmemory_document_store import InMemoryDocumentStore

__all__ = [
    # Version
    "__version__",
    # Document Stores
    "DocumentStore",
    "MongoDocumentStore",
    "InMemoryDocumentStore",
    "create_document_store",
]
