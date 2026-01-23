# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for parsing service error handling in message and thread storage."""

import logging

import pytest
from app.service import ParsingService
from copilot_storage.validating_document_store import DocumentValidationError


class DummyPublisher:
    def publish(self, *args, **kwargs):
        pass


class DummySubscriber:
    def subscribe(self, *args, **kwargs):
        pass


class DummyMetrics:
    def increment(self, *args, **kwargs):
        pass

    def observe(self, *args, **kwargs):
        pass


class DummyErrorReporter:
    def report(self, *args, **kwargs):
        pass

    def capture_exception(self, *args, **kwargs):
        pass


class FakeDocumentStore:
    """A controllable fake for `DocumentStore` insert behavior."""

    def __init__(self, behavior_map):
        # behavior_map: {collection_name: [None | Exception, ...]}
        self.behavior_map = behavior_map
        self.calls = {"messages": 0, "threads": 0}

    def insert_document(self, collection, doc):
        idx = self.calls[collection]
        self.calls[collection] += 1
        behavior_list = self.behavior_map.get(collection, [])
        if idx < len(behavior_list):
            outcome = behavior_list[idx]
            if outcome is None:
                return
            raise outcome
        # default: succeed
        return


def make_service_with_store(store):
    import tempfile

    from copilot_archive_store import create_archive_store
    from copilot_config.generated.adapters.archive_store import (
        AdapterConfig_ArchiveStore,
        DriverConfig_ArchiveStore_Local,
    )

    # Create a temp directory-based archive store to avoid /data permission issues.
    # Use TemporaryDirectory to ensure automatic cleanup.
    tmpdir = tempfile.TemporaryDirectory()
    archive_store = create_archive_store(
        AdapterConfig_ArchiveStore(
            archive_store_type="local",
            driver=DriverConfig_ArchiveStore_Local(archive_base_path=tmpdir.name),
        )
    )
    # Attach the TemporaryDirectory to the store so it stays alive for the
    # lifetime of the archive_store and is cleaned up automatically afterwards.
    archive_store._tmpdir = tmpdir
    return ParsingService(
        document_store=store,
        publisher=DummyPublisher(),
        subscriber=DummySubscriber(),
        metrics_collector=DummyMetrics(),
        error_reporter=DummyErrorReporter(),
        archive_store=archive_store,
    )


def test_store_messages_skips_duplicate_and_continues(caplog):
    """Test that DocumentAlreadyExistsError from any adapter is handled as a duplicate.
    
    This test verifies the standardized duplicate handling across all document store adapters.
    """
    from copilot_storage import DocumentAlreadyExistsError

    caplog.set_level(logging.DEBUG)
    msgs = [
        {"message_id": "m1"},
        {"message_id": "m2"},
        {"message_id": "m3"},
    ]
    store = FakeDocumentStore(
        {
            "messages": [
                None,  # m1 -> success
                DocumentAlreadyExistsError("Document already exists"),  # m2 -> skip
                None,  # m3 -> success continues
            ]
        }
    )
    service = make_service_with_store(store)

    service._store_messages(msgs)

    # Verify calls progressed through all messages
    assert store.calls["messages"] == 3

    # Verify skip was logged
    duplicate_logs = [r for r in caplog.records if "Skipping message m2" in r.message]
    assert duplicate_logs, "Expected a log indicating message m2 was skipped"

    # Verify summary info log includes skipped count
    info_summaries = [r for r in caplog.records if r.levelno == logging.INFO and "skipped" in r.message]
    assert any("skipped 1" in r.message for r in info_summaries)


def test_store_messages_skips_validation_and_continues(caplog):
    caplog.set_level(logging.DEBUG)
    msgs = [
        {"message_id": "m1"},
        {"message_id": "m2"},
    ]
    store = FakeDocumentStore(
        {
            "messages": [
                DocumentValidationError("messages", ["schema validation failed"]),  # m1 -> skip
                None,  # m2 -> success continues
            ]
        }
    )
    service = make_service_with_store(store)

    service._store_messages(msgs)

    assert store.calls["messages"] == 2
    validation_logs = [r for r in caplog.records if "Skipping message m1" in r.message]
    assert validation_logs, "Expected a log indicating message m1 was skipped"
    info_summaries = [r for r in caplog.records if r.levelno == logging.INFO and "skipped" in r.message]
    assert any("skipped 1" in r.message for r in info_summaries)


def test_store_messages_transient_errors_are_reraised(caplog):
    caplog.set_level(logging.ERROR)
    msgs = [{"message_id": "m1"}]

    class TransientError(Exception):
        pass

    store = FakeDocumentStore({"messages": [TransientError("database temporarily unavailable")]})
    service = make_service_with_store(store)

    with pytest.raises(TransientError):
        service._store_messages(msgs)

    # Ensure an error log occurred
    error_logs = [r for r in caplog.records if "Error storing message" in r.message]
    assert error_logs


def test_store_threads_skips_duplicate_and_validation_and_continues(caplog):
    """Test that DocumentAlreadyExistsError and DocumentValidationError are handled for threads.
    
    This test verifies standardized error handling for both duplicate and validation errors.
    """
    from copilot_storage import DocumentAlreadyExistsError

    caplog.set_level(logging.DEBUG)
    threads = [
        {"thread_id": "t1"},
        {"thread_id": "t2"},
        {"thread_id": "t3"},
    ]
    store = FakeDocumentStore(
        {
            "threads": [
                None,  # t1 -> success
                DocumentAlreadyExistsError("duplicate thread"),  # t2 -> skip
                DocumentValidationError("threads", ["bad thread schema"]),  # t3 -> skip
            ]
        }
    )
    service = make_service_with_store(store)

    service._store_threads(threads)

    assert store.calls["threads"] == 3
    dup_logs = [r for r in caplog.records if "Skipping thread t2" in r.message]
    val_logs = [r for r in caplog.records if "Skipping thread t3" in r.message]
    assert dup_logs and val_logs
    info_summaries = [r for r in caplog.records if r.levelno == logging.INFO and "skipped" in r.message]
    # 2 skips in total
    assert any("skipped 2" in r.message for r in info_summaries)


def test_store_threads_transient_errors_are_reraised(caplog):
    caplog.set_level(logging.ERROR)
    threads = [{"thread_id": "t1"}]

    class TransientError(Exception):
        pass

    store = FakeDocumentStore({"threads": [TransientError("db down")]})
    service = make_service_with_store(store)

    with pytest.raises(TransientError):
        service._store_threads(threads)

    error_logs = [r for r in caplog.records if "Error storing thread" in r.message]
    assert error_logs


def test_store_messages_handles_none_from_field():
    """Test that messages with None 'from' field are handled gracefully.

    This tests the fix for AttributeError when message["from"] is None.
    Previously, message.get("from", {}).get("email") would fail because
    .get(key, default) only returns default when key is missing, not when
    value is None. The fix uses (message.get("from") or {}).get("email").
    """
    msgs = [
        {
            "message_id": "m1",
            "from": None,  # This used to cause AttributeError
            "archive_id": "test-archive",
            "date": "2023-10-15T12:00:00Z",
            "subject": "Test message",
        },
        {
            "message_id": "m2",
            "from": {"email": "sender@example.com", "name": "Sender"},
            "archive_id": "test-archive",
            "date": "2023-10-15T13:00:00Z",
            "subject": "Test message 2",
        },
    ]
    store = FakeDocumentStore(
        {
            "messages": [None, None]  # Both succeed
        }
    )
    service = make_service_with_store(store)

    # Should not raise AttributeError
    service._store_messages(msgs)

    # Both messages should have been processed
    assert store.calls["messages"] == 2


def test_store_messages_skips_document_already_exists_and_continues(caplog):
    """Test that DocumentAlreadyExistsError from CosmosDB is handled as a duplicate.

    This tests the fix for CosmosDB conflicts where documents with the same ID
    already exist. The error should be caught and handled gracefully like
    MongoDB's DuplicateKeyError.
    """
    from copilot_storage import DocumentAlreadyExistsError

    caplog.set_level(logging.DEBUG)
    msgs = [
        {"message_id": "m1"},
        {"message_id": "m2"},
        {"message_id": "m3"},
    ]
    store = FakeDocumentStore(
        {
            "messages": [
                None,  # m1 -> success
                DocumentAlreadyExistsError("Document with id abc123 already exists in collection messages"),  # m2 -> skip
                None,  # m3 -> success continues
            ]
        }
    )
    service = make_service_with_store(store)

    service._store_messages(msgs)

    # Verify calls progressed through all messages
    assert store.calls["messages"] == 3

    # Verify skip was logged
    duplicate_logs = [r for r in caplog.records if "Skipping message m2" in r.message and "DocumentAlreadyExistsError" in r.message]
    assert duplicate_logs, "Expected a log indicating message m2 was skipped due to DocumentAlreadyExistsError"

    # Verify summary info log includes skipped count
    info_summaries = [r for r in caplog.records if r.levelno == logging.INFO and "skipped" in r.message]
    assert any("skipped 1" in r.message for r in info_summaries)


def test_store_threads_skips_document_already_exists_and_continues(caplog):
    """Test that DocumentAlreadyExistsError from CosmosDB is handled for threads too."""
    from copilot_storage import DocumentAlreadyExistsError

    caplog.set_level(logging.DEBUG)
    threads = [
        {"thread_id": "t1"},
        {"thread_id": "t2"},
        {"thread_id": "t3"},
    ]
    store = FakeDocumentStore(
        {
            "threads": [
                None,  # t1 -> success
                DocumentAlreadyExistsError("Document with id thread123 already exists in collection threads"),  # t2 -> skip
                None,  # t3 -> success continues
            ]
        }
    )
    service = make_service_with_store(store)

    service._store_threads(threads)

    # Verify calls progressed through all threads
    assert store.calls["threads"] == 3

    # Verify skip was logged
    duplicate_logs = [r for r in caplog.records if "Skipping thread t2" in r.message and "DocumentAlreadyExistsError" in r.message]
    assert duplicate_logs, "Expected a log indicating thread t2 was skipped due to DocumentAlreadyExistsError"

    # Verify summary info log includes skipped count
    info_summaries = [r for r in caplog.records if r.levelno == logging.INFO and "skipped" in r.message]
    assert any("skipped 1" in r.message for r in info_summaries)
