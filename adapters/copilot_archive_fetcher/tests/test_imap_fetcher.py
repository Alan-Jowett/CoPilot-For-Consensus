# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for IMAP fetcher failure handling."""

import sys
import types

from copilot_archive_fetcher import IMAPFetcher, SourceConfig


class _FakeIMAPClient:
    def __init__(self, host, port=993, ssl=True):
        self.host = host
        self.port = port
        self.ssl = ssl

    def login(self, username, password):
        self.username = username
        self.password = password

    def select_folder(self, folder):
        self.folder = folder

    def search(self):
        return [1, 2]

    def fetch(self, msg_ids, fields):
        # Simulate failure fetching any message
        raise Exception("boom")

    def logout(self):
        pass


def test_imap_fetcher_fails_on_partial_fetch(monkeypatch, tmp_path):
    fake_module = types.SimpleNamespace(IMAPClient=_FakeIMAPClient)
    monkeypatch.setitem(sys.modules, "imapclient", fake_module)

    source = SourceConfig(
        name="imap-test",
        source_type="imap",
        url="imap.example.com",
        username="user",
        password="pass",
    )

    fetcher = IMAPFetcher(source)
    success, files, error = fetcher.fetch(str(tmp_path))

    assert success is False
    assert files is None
    assert error is not None
    assert "Failed to fetch" in error

    # Partial mbox should not be left behind
    assert not any(tmp_path.iterdir())
