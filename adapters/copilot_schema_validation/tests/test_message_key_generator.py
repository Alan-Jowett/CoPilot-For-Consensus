"""
SPDX-License-Identifier: MIT
Copyright (c) 2025 Copilot-for-Consensus contributors

Legacy tests for message_key/chunk_key have been retired.

This file intentionally skips to acknowledge the breaking change that removed
message_key/chunk_key in favor of canonical _id fields and the centralized
identifier generator. See tests in test_identifier_generator.py.
"""

import pytest


def test_legacy_message_key_tests_retired():
    pytest.skip("Legacy message_key/chunk_key tests retired; using _id now.")
