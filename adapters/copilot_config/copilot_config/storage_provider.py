# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Configuration provider backed by copilot_storage document stores."""

import logging
import os
import time
from typing import Any

from .providers import DocStoreConfigProvider

logger = logging.getLogger(__name__)

try:
    from copilot_storage import create_document_store
except ImportError:  # pragma: no cover - handled at runtime
    create_document_store = None  # type: ignore


class StorageConfigProvider(DocStoreConfigProvider):
    """Config provider that reads dynamic values from copilot_storage.

    Values are sourced from a DocumentStore (MongoDB, in-memory, etc.) using the
    shared copilot_storage adapter. Documents are expected to have a ``key`` and
    ``value`` field. Results are cached with an optional TTL to limit read
    pressure while still allowing frequent refreshes for dynamic settings.
    """

    def __init__(
        self,
        doc_store: Any | None = None,
        collection: str = "config",
        cache_ttl_seconds: float | None = 30.0,
        auto_connect: bool = True,
        store_type: str | None = None,
        store_kwargs: dict[str, Any] | None = None,
    ):
        self._cache_ttl_seconds = cache_ttl_seconds
        self._last_refresh: float | None = None
        self._auto_connect = auto_connect

        store = doc_store or self._create_store(store_type=store_type, store_kwargs=store_kwargs)

        super().__init__(doc_store=store, collection=collection)

        if self._auto_connect:
            self._connect_if_needed()

    @property
    def doc_store(self) -> Any:
        """Expose the underlying document store for advanced scenarios."""

        return self._doc_store

    def refresh(self, force: bool = False) -> None:
        """Refresh the in-memory cache from the document store."""

        if not force and self._cache_ttl_seconds is None and self._cache is not None:
            return

        now = time.monotonic()
        if (
            not force
            and self._cache is not None
            and self._cache_ttl_seconds is not None
            and self._last_refresh is not None
            and (now - self._last_refresh) < self._cache_ttl_seconds
        ):
            return

        if self._auto_connect:
            self._connect_if_needed()

        try:
            docs = self._doc_store.query_documents(self._collection, {}, limit=1000)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("StorageConfigProvider: failed to query document store: %s", exc)
            if self._cache is None:
                self._cache = {}
            return

        self._cache = {}
        for doc in docs:
            key = doc.get("key")
            if key is None:
                continue
            self._cache[key] = doc.get("value")

        self._last_refresh = time.monotonic()

    def _ensure_cache(self) -> None:
        if self._cache is None:
            self.refresh(force=True)
            return

        if self._cache_ttl_seconds is None:
            return

        if self._last_refresh is None:
            self.refresh(force=True)
            return

        if (time.monotonic() - self._last_refresh) >= self._cache_ttl_seconds:
            self.refresh(force=True)

    def _create_store(
        self,
        store_type: str | None = None,
        store_kwargs: dict[str, Any] | None = None,
    ) -> Any:
        if create_document_store is None:
            raise ImportError(
                "copilot_storage is required for StorageConfigProvider. "
                "Install with: pip install copilot-config[storage]"
            )

        resolved_type = (
            store_type
            or os.environ.get("CONFIG_STORE_TYPE")
            or os.environ.get("CONFIG_DOCUMENT_STORE_TYPE")
            or "mongodb"
        )
        kwargs = self._build_store_kwargs(store_kwargs)
        return create_document_store(store_type=resolved_type, **kwargs)

    def _build_store_kwargs(self, store_kwargs: dict[str, Any] | None) -> dict[str, Any]:
        if store_kwargs is not None:
            return store_kwargs

        kwargs: dict[str, Any] = {}

        host = os.environ.get("CONFIG_STORE_HOST")
        if host:
            kwargs["host"] = host

        port = os.environ.get("CONFIG_STORE_PORT")
        if port:
            try:
                kwargs["port"] = int(port)
            except ValueError:
                logger.warning("StorageConfigProvider: invalid CONFIG_STORE_PORT value '%s'", port)

        username = os.environ.get("CONFIG_STORE_USERNAME")
        password = os.environ.get("CONFIG_STORE_PASSWORD")
        if username:
            kwargs["username"] = username
        if password:
            kwargs["password"] = password

        kwargs["database"] = os.environ.get("CONFIG_STORE_DATABASE", "copilot_config")

        return kwargs

    def _connect_if_needed(self) -> None:
        connect = getattr(self._doc_store, "connect", None)
        if callable(connect):
            try:
                connected = connect()
                if connected is False:
                    logger.warning("StorageConfigProvider: document store connect returned False")
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("StorageConfigProvider: failed to connect to document store: %s", exc)
