# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""In-memory document store for testing and local development."""

import copy
import logging
import uuid
from collections import defaultdict
from typing import Any

from copilot_config.generated.adapters.document_store import DriverConfig_DocumentStore_Inmemory

from .document_store import DocumentAlreadyExistsError, DocumentNotFoundError, DocumentStore, DocumentStoreError
from .schema_registry import sanitize_document, sanitize_documents

logger = logging.getLogger(__name__)


class InMemoryDocumentStore(DocumentStore):
    """In-memory document store implementation for testing."""

    @classmethod
    def from_config(cls, driver_config: DriverConfig_DocumentStore_Inmemory) -> "InMemoryDocumentStore":
        """Create an InMemoryDocumentStore from configuration.

        Args:
            driver_config: Configuration object (ignored, no configuration needed)

        Returns:
            InMemoryDocumentStore instance
        """
        del driver_config
        # InMemoryDocumentStore has no configuration parameters
        return cls()

    def __init__(self):
        """Initialize in-memory document store."""
        self.collections: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        self.connected = False

    def connect(self) -> None:
        """Pretend to connect.

        Note: Always succeeds for in-memory store
        """
        self.connected = True
        logger.debug("InMemoryDocumentStore: connected")

    def disconnect(self) -> None:
        """Pretend to disconnect."""
        self.connected = False
        logger.debug("InMemoryDocumentStore: disconnected")

    def insert_document(self, collection: str, doc: dict[str, Any]) -> str:
        """Insert a document into the specified collection.

        Args:
            collection: Name of the collection
            doc: Document data as dictionary

        Returns:
            Document ID as string

        Raises:
            DocumentAlreadyExistsError: If document with same ID already exists
        """
        # Generate ID if not provided
        doc_id = doc.get("_id", str(uuid.uuid4()))

        # Check if document already exists
        if doc_id in self.collections[collection]:
            raise DocumentAlreadyExistsError(f"Document with id {doc_id} already exists in collection {collection}")

        # Make a deep copy to avoid external mutations affecting stored data
        doc_copy = copy.deepcopy(doc)
        doc_copy["_id"] = doc_id

        self.collections[collection][doc_id] = doc_copy
        logger.debug(f"InMemoryDocumentStore: inserted document {doc_id} into {collection}")

        return doc_id

    def get_document(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        """Retrieve a document by its ID.

        Returns a sanitized document without backend system fields or
        document store metadata fields.

        Args:
            collection: Name of the collection
            doc_id: Document ID

        Returns:
            Sanitized document data as dictionary, or None if not found
        """
        doc = self.collections[collection].get(doc_id)
        if doc:
            logger.debug(f"InMemoryDocumentStore: retrieved document {doc_id} from {collection}")
            # Return a deep copy to prevent external mutations affecting stored data
            return sanitize_document(copy.deepcopy(doc), collection)
        logger.debug(f"InMemoryDocumentStore: document {doc_id} not found in {collection}")
        return None

    def query_documents(
        self,
        collection: str,
        filter_dict: dict[str, Any],
        limit: int = 100,
        sort_by: str | None = None,
        sort_order: str = "desc",
    ) -> list[dict[str, Any]]:
        """Query documents matching the filter criteria.

        Returns sanitized documents without backend system fields or
        document store metadata fields.

        Args:
            collection: Name of the collection
            filter_dict: Filter criteria as dictionary (simple equality checks)
            limit: Maximum number of documents to return
            sort_by: Optional field name to sort results by
            sort_order: Sort order ('asc' or 'desc', default 'desc')

        Returns:
            List of sanitized matching documents
        """
        results = []

        for doc in self.collections[collection].values():
            # Check if document matches all filter criteria
            matches = all(doc.get(key) == value for key, value in filter_dict.items())

            if matches:
                # Use deep copy to prevent external mutations affecting stored data
                results.append(copy.deepcopy(doc))

                # When no sort is requested, stop once we have enough results
                if sort_by is None and len(results) >= limit:
                    break

        if sort_by:
            if sort_order not in ("asc", "desc"):
                raise DocumentStoreError(
                    f"Invalid sort_order '{sort_order}': must be 'asc' or 'desc'"
                )

            reverse = sort_order == "desc"

            # Two-phase stable sort: documents with None/missing sort_by
            # values are always placed at the end, independent of direction.
            non_none_results: list[dict[str, Any]] = []
            none_results: list[dict[str, Any]] = []
            for _doc in results:
                if _doc.get(sort_by) is None:
                    none_results.append(_doc)
                else:
                    non_none_results.append(_doc)

            def _sort_key(d: dict[str, Any]) -> str:
                """Return sort key; None values are already excluded."""
                val = d.get(sort_by)
                return str(val) if val is not None else ""

            non_none_results.sort(
                key=_sort_key,
                reverse=reverse,
            )
            results = non_none_results + none_results

        results = results[:limit]

        logger.debug(
            f"InMemoryDocumentStore: query on {collection} with {filter_dict} " f"returned {len(results)} documents"
        )
        return sanitize_documents(results, collection)

    def update_document(self, collection: str, doc_id: str, patch: dict[str, Any]) -> None:
        """Update a document with the provided patch.

        Args:
            collection: Name of the collection
            doc_id: Document ID
            patch: Update data as dictionary

        Raises:
            DocumentNotFoundError: If document does not exist
        """
        if doc_id not in self.collections[collection]:
            logger.debug(f"InMemoryDocumentStore: document {doc_id} not found in {collection}")
            raise DocumentNotFoundError(f"Document {doc_id} not found in collection {collection}")

        # Apply patch to document
        self.collections[collection][doc_id].update(patch)
        logger.debug(f"InMemoryDocumentStore: updated document {doc_id} in {collection}")

    def delete_document(self, collection: str, doc_id: str) -> None:
        """Delete a document by its ID.

        Args:
            collection: Name of the collection
            doc_id: Document ID

        Raises:
            DocumentNotFoundError: If document does not exist
        """
        if doc_id in self.collections[collection]:
            del self.collections[collection][doc_id]
            logger.debug(f"InMemoryDocumentStore: deleted document {doc_id} from {collection}")
        else:
            logger.debug(f"InMemoryDocumentStore: document {doc_id} not found in {collection}")
            raise DocumentNotFoundError(f"Document {doc_id} not found in collection {collection}")

    def clear_collection(self, collection: str) -> None:
        """Clear all documents in a collection (useful for testing).

        Args:
            collection: Name of the collection
        """
        self.collections[collection].clear()
        logger.debug(f"InMemoryDocumentStore: cleared collection {collection}")

    def clear_all(self) -> None:
        """Clear all collections (useful for testing)."""
        self.collections.clear()
        logger.debug("InMemoryDocumentStore: cleared all collections")

    def aggregate_documents(self, collection: str, pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Execute a simplified aggregation pipeline on a collection.

        Returns sanitized documents without backend system fields or
        document store metadata fields.

        This is a simplified implementation that supports common aggregation stages
        for testing purposes. It supports: $match, $lookup, $limit.

        **Note**: This implementation is optimized for testing with small datasets.
        Performance may degrade with large collections due to O(N*M) complexity in
        $lookup operations.

        **Supported operators in $match**:
        - $exists: Check if a field exists
        - $eq: Equality comparison

        Args:
            collection: Name of the collection
            pipeline: Aggregation pipeline (list of stage dictionaries)

        Returns:
            List of sanitized aggregation results
        """
        # Start with all documents in the collection
        # Return empty list if collection doesn't exist
        if collection not in self.collections:
            logger.debug(f"InMemoryDocumentStore: collection '{collection}' not found for aggregation")
            return []

        results = [copy.deepcopy(doc) for doc in self.collections[collection].values()]

        for stage in pipeline:
            stage_name = list(stage.keys())[0]
            stage_spec = stage[stage_name]

            if stage_name == "$match":
                # Filter documents based on match criteria
                results = self._apply_match(results, stage_spec)

            elif stage_name == "$lookup":
                # Join with another collection
                results = self._apply_lookup(results, stage_spec)

            elif stage_name == "$limit":
                # Limit number of results
                results = results[:stage_spec]

            else:
                logger.warning(f"InMemoryDocumentStore: aggregation stage '{stage_name}' not implemented, skipping")

        logger.debug(f"InMemoryDocumentStore: aggregation on {collection} " f"returned {len(results)} documents")
        return sanitize_documents(results, collection, preserve_extra=True)

    def _apply_match(self, documents: list[dict[str, Any]], match_spec: dict[str, Any]) -> list[dict[str, Any]]:
        """Apply $match stage to filter documents.

        Supports operators: $exists, $eq
        For unsupported operators, a warning is logged and the condition is skipped.

        Args:
            documents: List of documents to filter
            match_spec: Match specification

        Returns:
            Filtered list of documents
        """
        filtered = []
        for doc in documents:
            matches = True
            for key, condition in match_spec.items():
                if isinstance(condition, dict):
                    # Handle operators like $exists, $eq, etc.
                    for op, value in condition.items():
                        if op == "$exists":
                            if value and key not in doc:
                                matches = False
                                break
                            elif not value and key in doc:
                                matches = False
                                break
                        elif op == "$eq":
                            if doc.get(key) != value:
                                matches = False
                                break
                        else:
                            # Unsupported operator - log warning and skip
                            logger.warning(f"InMemoryDocumentStore: unsupported operator '{op}' in $match, skipping")

                    # If any operator failed, exit the key loop early
                    if not matches:
                        break
                else:
                    # Simple equality check
                    if doc.get(key) != condition:
                        matches = False
                        break

            if matches:
                filtered.append(doc)

        return filtered

    def _apply_lookup(self, documents: list[dict[str, Any]], lookup_spec: dict[str, Any]) -> list[dict[str, Any]]:
        """Apply $lookup stage to join with another collection.

        **Performance Note**: This implementation has O(N*M) complexity where N is
        the number of input documents and M is the size of the foreign collection.
        It is suitable for testing but may not perform well with large datasets.

        Args:
            documents: List of documents to enrich
            lookup_spec: Lookup specification with 'from', 'localField', 'foreignField', 'as'

        Returns:
            Documents with joined data
        """
        from_collection = lookup_spec["from"]
        local_field = lookup_spec["localField"]
        foreign_field = lookup_spec["foreignField"]
        as_field = lookup_spec["as"]

        # Check if the foreign collection exists
        if from_collection not in self.collections:
            logger.debug(f"InMemoryDocumentStore: foreign collection '{from_collection}' not found in $lookup")
            # Return documents with empty array for the 'as' field (mimics MongoDB behavior)
            result_docs = []
            for doc in documents:
                enriched_doc = copy.deepcopy(doc)
                enriched_doc[as_field] = []
                result_docs.append(enriched_doc)
            return result_docs

        result_docs = []
        for doc in documents:
            # Make a copy to avoid modifying original
            enriched_doc = copy.deepcopy(doc)

            # Find matching documents in the foreign collection
            local_value = doc.get(local_field)
            matches = []

            for foreign_doc in self.collections[from_collection].values():
                if foreign_doc.get(foreign_field) == local_value:
                    matches.append(copy.deepcopy(foreign_doc))

            # Add matches as an array field
            enriched_doc[as_field] = matches
            result_docs.append(enriched_doc)

        return result_docs
