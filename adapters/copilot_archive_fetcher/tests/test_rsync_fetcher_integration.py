# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for rsync fetcher."""

import os

import pytest

from copilot_archive_fetcher import RsyncFetcher, SourceConfig


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RSYNC_INTEGRATION_ENABLED") != "true" and os.getenv("RSYNC_INTEGRATION_ENABLED") != "1",
                    reason="Rsync integration not enabled")
def test_rsync_fetcher_syncs_fixture(tmp_path):
    host = os.getenv("RSYNC_HOST", "localhost")
    port = os.getenv("RSYNC_PORT", "8730")
    module = os.getenv("RSYNC_MODULE", "data")

    url = f"rsync://{host}:{port}/{module}/"
    config = SourceConfig(name="rsync-fixture", source_type="rsync", url=url)
    fetcher = RsyncFetcher(config)

    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    success, files, error = fetcher.fetch(str(output_dir))

    assert success is True, f"rsync fetch failed: {error}"
    assert files is not None and len(files) >= 2

    expected_root = output_dir / "rsync-fixture"
    expected_sample = expected_root / "sample.txt"
    expected_nested = expected_root / "nested" / "inner.txt"

    assert expected_sample.exists(), "sample fixture was not synced"
    assert expected_nested.exists(), "nested fixture was not synced"

    with expected_sample.open("r", encoding="utf-8") as fh:
        assert fh.read().strip() == "sample fixture content"

    with expected_nested.open("r", encoding="utf-8") as fh:
        assert fh.read().strip() == "nested fixture content"
