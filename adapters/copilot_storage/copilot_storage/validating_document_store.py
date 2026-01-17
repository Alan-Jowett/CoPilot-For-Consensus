# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Validating document store that enforces schema validation."""

import logging
from typing import Any, Callable, Protocol, cast, runtime_checkable

from .document_store import DocumentNotFoundError, DocumentStore

logger = logging.getLogger(__name__)


@runtime_checkable
class _SupportsAggregateDocuments(Protocol):
    def aggregate_documents(
        self, collection: str, pipeline: list[dict[str, Any]]
    ) -> list[dict[str, Any]]: ...


class DocumentValidationError(Exception):
    """Exception raised when document validation fails.

    Attributes:
        collection: The collection where validation failed
        errors: List of validation error messages
    """

    def __init__(self, collection: str, errors: list[str]):
        self.collection = collection
        self.errors = errors
        error_msg = f"Validation failed for collection '{collection}': {'; '.join(errors)}"
        super().__init__(error_msg)


class ValidatingDocumentStore(DocumentStore):
    """Document store that validates documents against schemas before operations.

    This is a decorator/wrapper around any DocumentStore implementation that
    adds schema validation. It uses a SchemaProvider to retrieve schemas and
    validates documents before delegating to the underlying store.

    Schema names are derived from collection names by converting to PascalCase
    (e.g., "archive_metadata" -> "ArchiveMetadata").

    Example:
        >>> from copilot_storage import create_document_store
        >>> from copilot_schema_validation import FileSchemaProvider
        >>>
        >>> base_store = create_document_store("inmemory")
        >>> schema_provider = FileSchemaProvider()
        >>> validating_store = ValidatingDocumentStore(
        ...     store=base_store,
        ...     schema_provider=schema_provider
        ... )
        >>>
        >>> doc = {"archive_id": "abc", "status": "success"}
        >>> validating_store.insert_document("archive_metadata", doc)
    """

    def __init__(
        self,
        store: DocumentStore,
        schema_provider: Any | None = None,
        strict: bool = True,
        validate_reads: bool = False,
    ):
        """Initialize the validating document store.

        Args:
            store: Underlying DocumentStore to delegate to
            schema_provider: SchemaProvider for retrieving schemas (optional)
            strict: If True, raise DocumentValidationError on validation failure.
                   If False, log error and allow operation to proceed.
            validate_reads: If True, validate documents on read operations (get_document).
                           Useful for debugging but has performance impact.
        """
        self._store = store
        self._schema_provider = schema_provider
        self._strict = strict
        self._validate_reads = validate_reads

        # Keys injected by some document stores (e.g., Cosmos DB) that should not
        # be validated against the application JSON schemas.
        self._validation_metadata_keys: set[str] = {
            "_attachments",
            "_etag",
            "_rid",
            "_self",
            "_ts",
            "collection",
            "id",
        }

    def _strip_store_metadata_for_validation(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of doc with store metadata removed.

        Some backends inject system/envelope fields on read. Our JSON Schemas
        describe the logical document shape and typically set
        additionalProperties=false, so we must exclude these injected fields
        before validation.
        """
        return {k: v for k, v in doc.items() if k not in self._validation_metadata_keys}

    def _collection_to_schema_name(self, collection: str) -> str:
        """Convert collection name to schema name.

        Returns the collection name as-is for document schemas, which use
        lowercase naming (e.g., "messages" -> "messages", "chunks" -> "chunks").

        Args:
            collection: Collection name

        Returns:
            Schema name (same as collection name for documents)
        """
        # Document schemas use lowercase naming matching collection names
        return collection

    def _validate_document(self, collection: str, doc: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate a document against its schema.

        Args:
            collection: Collection name (used to determine schema)
            doc: Document dictionary to validate

        Returns:
            Tuple of (is_valid, errors). is_valid is True if document conforms
            to schema or if no schema provider is configured. errors is a list
            of validation error messages.
        """
        # If no schema provider, skip validation
        if self._schema_provider is None:
            logger.debug("No schema provider configured, skipping validation")
            return True, []

        # Derive schema name from collection
        schema_name = self._collection_to_schema_name(collection)

        # Get schema
        try:
            schema = self._schema_provider.get_schema(schema_name)
            if schema is None:
                logger.debug(
                    "No schema found for collection '%s' (schema: '%s')",
                    collection, schema_name
                )
                # If schema not found, allow document to pass in non-strict mode
                if not self._strict:
                    return True, []
                return False, [f"No schema found for collection '{collection}'"]
        except Exception as exc:
            logger.error(
                "Failed to retrieve schema for collection '%s': %s",
                collection, exc
            )
            return False, [f"Schema retrieval failed: {exc}"]

        # Validate document against schema
        try:
            from copilot_schema_validation import validate_json  # pylint: disable=import-outside-toplevel
            is_valid, errors = validate_json(doc, schema, schema_provider=self._schema_provider)
            return is_valid, errors
        except Exception as exc:
            logger.error("Validation failed with exception: %s", exc)
            return False, [f"Validation exception: {exc}"]

    def _handle_validation_failure(self, collection: str, errors: list[str]) -> None:
        """Handle validation failure based on strict mode.

        Args:
            collection: Collection where validation failed
            errors: List of validation errors

        Raises:
            DocumentValidationError: If strict=True
        """
        if self._strict:
            # In strict mode, raise exception
            raise DocumentValidationError(collection, errors)

        # In non-strict mode, log warning
        logger.warning(
            "Document validation failed for collection '%s' but continuing in non-strict mode: %s",
            collection, errors
        )

    def connect(self) -> None:
        """Connect to the document store.

        Raises:
            DocumentStoreConnectionError: If connection fails
        """
        self._store.connect()

    def disconnect(self) -> None:
        """Disconnect from the document store."""
        self._store.disconnect()

    def insert_document(self, collection: str, doc: dict[str, Any]) -> str:
        """Insert a document after validating it against its schema.

        Args:
            collection: Name of the collection/table
            doc: Document data as dictionary

        Returns:
            Document ID as string

        Raises:
            DocumentValidationError: If strict=True and validation fails
            Exception: If insertion fails
        """
        # Validate document
        is_valid, errors = self._validate_document(collection, doc)

        if not is_valid:
            self._handle_validation_failure(collection, errors)

        # Delegate to underlying store
        return self._store.insert_document(collection, doc)

    def get_document(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        """Retrieve a document by its ID.

        Optionally validates the retrieved document if validate_reads=True.

        Args:
            collection: Name of the collection/table
            doc_id: Document ID

        Returns:
            Document data as dictionary, or None if not found

        Raises:
            DocumentValidationError: If validate_reads=True, strict=True, and validation fails
        """
        # Retrieve document
        doc = self._store.get_document(collection, doc_id)

        # Optionally validate on read
        if doc is not None and self._validate_reads:
            is_valid, errors = self._validate_document(
                collection,
                self._strip_store_metadata_for_validation(doc),
            )
            if not is_valid:
                self._handle_validation_failure(collection, errors)

        return doc

    def set_query_wrapper(self, wrapper_fn: Callable) -> None:
        """Wrap the query_documents method with custom logic.

        Allows tests or extensions to customize query behavior without
        accessing private attributes. The wrapper receives the original
        query method and should return a callable with the same signature.

        Warning:
            This method modifies internal state. Calling it multiple times will
            overwrite the previous wrapper. It should be called at initialization
            time before the store is actively used in production.

        Example:
            >>> from copilot_storage import create_document_store
            >>> from copilot_schema_validation import FileSchemaProvider
            >>>
            >>> # Create and initialize store BEFORE using it
            >>> base_store = create_document_store("inmemory")
            >>> validating_store = ValidatingDocumentStore(
            ...     store=base_store,
            ...     schema_provider=FileSchemaProvider()
            ... )
            >>>
            >>> # Set up wrapper at initialization time, BEFORE any queries
            >>> def custom_query_wrapper(original_query):
            ...     def wrapped_query(collection, filter_dict, limit=100):
            ...         # Custom validation logic here
            ...         return original_query(collection, filter_dict, limit)
            ...     return wrapped_query
            >>>
            >>> store.set_query_wrapper(custom_query_wrapper)
            >>>
            >>> # NOW use the store - wrapper will be active for all queries
            >>> results = validating_store.query_documents("messages", {"status": "active"})

        Warning:
            This method modifies internal state and is **not thread-safe**. It should only
            be called during initialization, before any queries are executed in any thread.
            Calling this method after initialization in a multi-threaded environment may
            cause race conditions or unexpected behavior.

        Args:
            wrapper_fn: Function that takes the original query method and returns
                       a wrapped version with the same signature

        Raises:
            ValueError: If wrapper_fn is not callable.
        """
        if not callable(wrapper_fn):
            raise ValueError("Query wrapper must be callable")
        original_query = self._store.query_documents
        self._store.query_documents = wrapper_fn(original_query)

    def query_documents(
        self, collection: str, filter_dict: dict[str, Any], limit: int = 100
    ) -> list[dict[str, Any]]:
        """Query documents matching the filter criteria.

        Args:
            collection: Name of the collection/table
            filter_dict: Filter criteria as dictionary
            limit: Maximum number of documents to return

        Returns:
            List of matching documents
        """
        # Delegate to underlying store
        return self._store.query_documents(collection, filter_dict, limit)

    def update_document(
        self, collection: str, doc_id: str, patch: dict[str, Any]
    ) -> None:
        """Update a document with the provided patch.

        Validates the merged document (current document + patch) against the schema before updating.

        Args:
            collection: Name of the collection/table
            doc_id: Document ID
            patch: Update data as dictionary

        Raises:
            DocumentValidationError: If strict=True and validation fails
            DocumentNotFoundError: If document does not exist
        """
        # Fetch current document and merge with patch to validate the result.
        # Some backends (e.g., Cosmos DB) may store a different native document id
        # ("id") than the application-level canonical key (often stored in "_id").
        # In that case, get_document(collection, doc_id) can miss even though a
        # document exists with _id == doc_id.
        current_doc = self._store.get_document(collection, doc_id)
        effective_doc_id = doc_id

        if current_doc is None:
            candidates = self._store.query_documents(collection, {"_id": doc_id}, limit=1)
            if candidates:
                current_doc = candidates[0]
                resolved_id = current_doc.get("id")
                if resolved_id is None:
                    resolved_id = current_doc.get("_id")
                if resolved_id is not None:
                    effective_doc_id = str(resolved_id)

        # Raise DocumentNotFoundError if document doesn't exist
        if current_doc is None:
            raise DocumentNotFoundError(f"Document {doc_id} not found in collection {collection}")

        merged_doc = {**current_doc, **patch}
        merged_doc_for_validation = self._strip_store_metadata_for_validation(merged_doc)

        # Validate the merged document
        is_valid, errors = self._validate_document(collection, merged_doc_for_validation)

        if not is_valid:
            self._handle_validation_failure(collection, errors)

        # Delegate to underlying store
        self._store.update_document(collection, effective_doc_id, patch)

    def delete_document(self, collection: str, doc_id: str) -> None:
        """Delete a document by its ID.

        Args:
            collection: Name of the collection/table
            doc_id: Document ID

        Raises:
            DocumentNotFoundError: If document does not exist
        """
        # No validation needed for deletion
        self._store.delete_document(collection, doc_id)

    def aggregate_documents(
        self, collection: str, pipeline: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Execute an aggregation pipeline on a collection.

        This method delegates to the underlying store if it supports aggregation.
        No validation is performed on aggregation results.

        Args:
            collection: Name of the collection
            pipeline: Aggregation pipeline (list of stage dictionaries)

        Returns:
            List of aggregation results

        Raises:
            AttributeError: If underlying store doesn't support aggregation
        """
        # Check if underlying store supports aggregation
        if not isinstance(self._store, _SupportsAggregateDocuments):
            raise AttributeError(
                f"Underlying store {type(self._store).__name__} does not support aggregation"
            )

        # Delegate to underlying store without validation
        # (aggregation results may not match original document schemas)
        store = cast(_SupportsAggregateDocuments, self._store)
        return store.aggregate_documents(collection, pipeline)
