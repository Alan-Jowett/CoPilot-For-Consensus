# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for StorageConfigProvider using copilot_storage backends."""

import pytest

copilot_storage = pytest.importorskip("copilot_storage")

from copilot_config import StorageConfigProvider  # noqa: E402  pylint: disable=wrong-import-position


def _make_store():
    store = copilot_storage.InMemoryDocumentStore()
    store.connect()
    return store


def test_storage_provider_reads_and_converts_values():
    store = _make_store()
    store.insert_document("config", {"key": "PROMPT", "value": "welcome"})
    store.insert_document("config", {"key": "ENABLED", "value": "true"})
    store.insert_document("config", {"key": "MAX_ITEMS", "value": "5"})

    provider = StorageConfigProvider(doc_store=store, cache_ttl_seconds=None, auto_connect=False)

    assert provider.get("PROMPT") == "welcome"
    assert provider.get_bool("ENABLED") is True
    assert provider.get_int("MAX_ITEMS") == 5


def test_storage_provider_refreshes_from_store():
    store = _make_store()
    doc_id = store.insert_document("config", {"key": "PROMPT", "value": "v1"})

    provider = StorageConfigProvider(doc_store=store, cache_ttl_seconds=999, auto_connect=False)

    assert provider.get("PROMPT") == "v1"

    store.update_document("config", doc_id, {"value": "v2"})

    # Cached value remains until refresh is invoked explicitly
    assert provider.get("PROMPT") == "v1"

    provider.refresh(force=True)

    assert provider.get("PROMPT") == "v2"


def test_storage_provider_auto_refresh_with_short_ttl():
    store = _make_store()
    doc_id = store.insert_document("config", {"key": "PROMPT", "value": "v1"})

    provider = StorageConfigProvider(doc_store=store, cache_ttl_seconds=0.0, auto_connect=False)

    assert provider.get("PROMPT") == "v1"

    store.update_document("config", doc_id, {"value": "v3"})

    assert provider.get("PROMPT") == "v3"
