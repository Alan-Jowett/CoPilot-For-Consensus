# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Compatibility shim for the old MongoSchemaProvider name.

Use DocumentStoreSchemaProvider instead; this alias remains for legacy imports.
"""

from .document_store_schema_provider import DocumentStoreSchemaProvider as MongoSchemaProvider

__all__ = ["MongoSchemaProvider"]
