# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for environment variable backward compatibility."""

import warnings

from copilot_storage import create_document_store


class TestEnvVarBackwardCompatibility:
    """Test backward compatibility for MONGO_* to DOC_DB_* migration."""

    def test_doc_db_vars_take_precedence(self, monkeypatch):
        """Test that DOC_DB_* variables take precedence over MONGO_* variables."""
        # Set both old and new env vars
        monkeypatch.setenv("DOC_DB_HOST", "new-host")
        monkeypatch.setenv("MONGO_HOST", "old-host")
        monkeypatch.setenv("DOC_DB_PORT", "27018")
        monkeypatch.setenv("MONGO_PORT", "27019")
        monkeypatch.setenv("DOC_DB_NAME", "new-db")
        monkeypatch.setenv("MONGO_DB", "old-db")
        monkeypatch.setenv("DOC_DB_USER", "new-user")
        monkeypatch.setenv("MONGO_USER", "old-user")
        monkeypatch.setenv("DOC_DB_PASSWORD", "new-pass")
        monkeypatch.setenv("MONGO_PASSWORD", "old-pass")

        store = create_document_store(store_type="mongodb")

        # DOC_DB_* values should be used
        assert store.host == "new-host"
        assert store.port == 27018
        assert store.database_name == "new-db"
        assert store.username == "new-user"
        assert store.password == "new-pass"

    def test_mongo_vars_fallback_with_warning(self, monkeypatch):
        """Test that MONGO_* variables work as fallback with deprecation warning."""
        # Only set old MONGO_* vars
        monkeypatch.setenv("MONGO_HOST", "legacy-host")
        monkeypatch.setenv("MONGO_PORT", "27020")
        monkeypatch.setenv("MONGO_DB", "legacy-db")
        monkeypatch.setenv("MONGO_USER", "legacy-user")
        monkeypatch.setenv("MONGO_PASSWORD", "legacy-pass")

        # Remove DOC_DB_* vars if they exist
        for var in ["DOC_DB_HOST", "DOC_DB_PORT", "DOC_DB_NAME", "DOC_DB_USER", "DOC_DB_PASSWORD"]:
            monkeypatch.delenv(var, raising=False)

        # Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            store = create_document_store(store_type="mongodb")

            # Should have warnings for deprecated env vars
            assert len(w) >= 1
            assert any("deprecated" in str(warning.message).lower() for warning in w)
            assert any("MONGO_HOST" in str(warning.message) for warning in w)

        # MONGO_* values should be used as fallback
        assert store.host == "legacy-host"
        assert store.port == 27020
        assert store.database_name == "legacy-db"
        assert store.username == "legacy-user"
        assert store.password == "legacy-pass"

    def test_defaults_when_no_env_vars(self, monkeypatch):
        """Test that defaults are used when neither DOC_DB_* nor MONGO_* vars are set."""
        # Remove all relevant env vars
        for var in ["DOC_DB_HOST", "DOC_DB_PORT", "DOC_DB_NAME", "DOC_DB_USER", "DOC_DB_PASSWORD",
                    "MONGO_HOST", "MONGO_PORT", "MONGO_DB", "MONGO_USER", "MONGO_PASSWORD"]:
            monkeypatch.delenv(var, raising=False)

        store = create_document_store(store_type="mongodb")

        # Default values should be used
        assert store.host == "localhost"
        assert store.port == 27017
        assert store.database_name == "copilot"
        assert store.username is None
        assert store.password is None

    def test_explicit_params_override_env_vars(self, monkeypatch):
        """Test that explicit parameters override environment variables."""
        # Set env vars
        monkeypatch.setenv("DOC_DB_HOST", "env-host")
        monkeypatch.setenv("MONGO_HOST", "old-host")

        # Create store with explicit parameters
        store = create_document_store(
            store_type="mongodb",
            host="explicit-host",
            port=27099,
            database="explicit-db",
            username="explicit-user",
            password="explicit-pass"
        )

        # Explicit parameters should take precedence
        assert store.host == "explicit-host"
        assert store.port == 27099
        assert store.database_name == "explicit-db"
        assert store.username == "explicit-user"
        assert store.password == "explicit-pass"

    def test_mixed_env_vars(self, monkeypatch):
        """Test mixed scenario with some DOC_DB_* and some MONGO_* vars."""
        # Set only some DOC_DB_* vars
        monkeypatch.setenv("DOC_DB_HOST", "new-host")
        monkeypatch.setenv("DOC_DB_PORT", "27018")
        
        # Set MONGO_* vars for the rest
        monkeypatch.setenv("MONGO_DB", "legacy-db")
        monkeypatch.setenv("MONGO_USER", "legacy-user")
        
        # Remove other vars
        monkeypatch.delenv("DOC_DB_NAME", raising=False)
        monkeypatch.delenv("DOC_DB_USER", raising=False)
        monkeypatch.delenv("DOC_DB_PASSWORD", raising=False)
        monkeypatch.delenv("MONGO_HOST", raising=False)
        monkeypatch.delenv("MONGO_PORT", raising=False)
        monkeypatch.delenv("MONGO_PASSWORD", raising=False)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            store = create_document_store(store_type="mongodb")

            # Should have warnings for MONGO_DB and MONGO_USER
            assert any("MONGO_DB" in str(warning.message) for warning in w)
            assert any("MONGO_USER" in str(warning.message) for warning in w)

        # Should use DOC_DB_* where available, MONGO_* as fallback
        assert store.host == "new-host"
        assert store.port == 27018
        assert store.database_name == "legacy-db"
        assert store.username == "legacy-user"
        assert store.password is None

    def test_empty_string_values(self, monkeypatch):
        """Test that empty string values for user/password work correctly."""
        monkeypatch.setenv("DOC_DB_HOST", "test-host")
        monkeypatch.setenv("DOC_DB_USER", "")
        monkeypatch.setenv("DOC_DB_PASSWORD", "")

        store = create_document_store(store_type="mongodb")

        # Empty strings should be preserved for user/password
        assert store.host == "test-host"
        assert store.username == ""
        assert store.password == ""
