# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import datetime as dt

from copilot_schema_validation.identifier_generator import (
    generate_archive_id_from_bytes,
    generate_message_doc_id,
    generate_chunk_id,
    generate_thread_id,
    generate_summary_id,
)


def test_generate_archive_id_from_bytes_is_deterministic_and_length():
    data = b"dummy mbox content for testing"
    a1 = generate_archive_id_from_bytes(data)
    a2 = generate_archive_id_from_bytes(data)
    assert a1 == a2
    assert isinstance(a1, str)
    assert len(a1) == 16


def test_generate_message_doc_id_is_deterministic_and_changes_with_fields():
    mid = "<abc@example.com>"
    archive_id = "abcdef0123456789"
    m1 = generate_message_doc_id(
        archive_id=archive_id,
        message_id=mid,
        date="2023-10-15T12:34:56Z",
        sender_email="alice@example.com",
        subject="Hello",
    )
    m2 = generate_message_doc_id(
        archive_id=archive_id,
        message_id=mid,
        date="2023-10-15T12:34:56Z",
        sender_email="alice@example.com",
        subject="Hello",
    )
    assert m1 == m2
    assert len(m1) == 16

    # Changing a field should change the id
    m3 = generate_message_doc_id(
        archive_id=archive_id,
        message_id=mid,
        date="2023-10-15T12:34:56Z",
        sender_email="alice@example.com",
        subject="Hello again",
    )
    assert m3 != m1


def test_generate_chunk_id_is_deterministic_and_changes_with_index():
    message_doc_id = "abcdef0123456789"
    cid1 = generate_chunk_id(message_doc_id, 0)
    cid2 = generate_chunk_id(message_doc_id, 0)
    cid3 = generate_chunk_id(message_doc_id, 1)
    assert cid1 == cid2
    assert cid1 != cid3
    assert len(cid1) == 16


def test_generate_thread_id_scoped_by_source_and_subject():
    root_mid = "<20231015120000.XYZ789@example.com>"
    tid1 = generate_thread_id("ietf-quic", root_mid, "Re: Transport Topics")
    tid2 = generate_thread_id("ietf-quic", root_mid, "Re: Transport Topics")
    assert tid1 == tid2
    assert len(tid1) == 16

    # Different source → different thread id
    tid_other_list = generate_thread_id("ietf-http", root_mid, "Re: Transport Topics")
    assert tid_other_list != tid1

    # Different subject normalization → different thread id
    tid_other_subject = generate_thread_id("ietf-quic", root_mid, "Re: Different Subject")
    assert tid_other_subject != tid1


def test_generate_summary_id_is_deterministic_and_length():
    thread_id = "<20231015120000.XYZ789@example.com>"
    content = "# Hello\nThis is a test summary."
    ts = dt.datetime(2023, 10, 15, 12, 34, 56, tzinfo=dt.timezone.utc).isoformat()
    s1 = generate_summary_id(thread_id, content, ts)
    s2 = generate_summary_id(thread_id, content, ts)
    assert s1 == s2
    assert len(s1) == 16
