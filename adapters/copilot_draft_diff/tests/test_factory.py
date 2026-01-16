# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for draft diff provider factory."""

import pytest
from copilot_config.generated.adapters.draft_diff_provider import (
    AdapterConfig_DraftDiffProvider,
    DriverConfig_DraftDiffProvider_Datatracker,
    DriverConfig_DraftDiffProvider_Mock,
)
from copilot_draft_diff.datatracker_provider import DatatrackerDiffProvider
from copilot_draft_diff.factory import DiffProviderFactory, create_diff_provider, create_draft_diff_provider
from copilot_draft_diff.mock_provider import MockDiffProvider
from copilot_draft_diff.provider import DraftDiffProvider


class SimpleConfig:
    """Simple config object for testing custom providers."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestDiffProviderFactory:
    """Tests for DiffProviderFactory."""

    def test_create_datatracker_provider(self):
        """Test creating datatracker provider."""
        config = DriverConfig_DraftDiffProvider_Datatracker(
            base_url="https://datatracker.ietf.org",
            diff_format="html",
        )
        provider = DiffProviderFactory.create("datatracker", config)

        assert isinstance(provider, DatatrackerDiffProvider)
        assert provider.base_url == "https://datatracker.ietf.org"

    def test_create_datatracker_provider_with_config(self):
        """Test creating datatracker provider with custom config."""
        config = DriverConfig_DraftDiffProvider_Datatracker(
            base_url="https://custom.example.com",
            diff_format="text"
        )
        provider = DiffProviderFactory.create("datatracker", config)

        assert isinstance(provider, DatatrackerDiffProvider)
        assert provider.base_url == "https://custom.example.com"
        assert provider.diff_format == "text"

    def test_create_mock_provider(self):
        """Test creating mock provider."""
        config = DriverConfig_DraftDiffProvider_Mock(default_format="text")
        provider = DiffProviderFactory.create("mock", config)

        assert isinstance(provider, MockDiffProvider)
        assert provider.default_format == "text"

    def test_create_mock_provider_with_config(self):
        """Test creating mock provider with custom config."""
        config = DriverConfig_DraftDiffProvider_Mock(default_format="html")
        provider = DiffProviderFactory.create("mock", config)

        assert isinstance(provider, MockDiffProvider)
        assert provider.default_format == "html"

    def test_create_unknown_provider(self):
        """Test that creating unknown provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown provider driver: unknown"):
            DiffProviderFactory.create("unknown")

    def test_create_requires_provider_type(self):
        """Test that creating provider requires provider_type parameter."""
        with pytest.raises(ValueError, match="driver_name parameter is required"):
            DiffProviderFactory.create(None)

    def test_create_empty_provider_type(self):
        """Test that empty provider_type raises error."""
        with pytest.raises(ValueError, match="driver_name parameter is required"):
            DiffProviderFactory.create("")

    def test_register_custom_provider(self):
        """Test registering a custom provider."""
        # Create a custom provider class
        class CustomProvider(DraftDiffProvider):
            def getdiff(self, draft_name, version_a, version_b):
                pass

        # Register it
        DiffProviderFactory.register_provider("custom", CustomProvider)

        # Create instance
        provider = DiffProviderFactory.create("custom")

        assert isinstance(provider, CustomProvider)

    def test_register_invalid_provider(self):
        """Test that registering invalid provider raises TypeError."""
        # Try to register a class that doesn't inherit from DraftDiffProvider
        class InvalidProvider:
            pass

        with pytest.raises(TypeError, match="must inherit from DraftDiffProvider"):
            DiffProviderFactory.register_provider("invalid", InvalidProvider)


class TestCreateDiffProvider:
    """Tests for create_diff_provider convenience function."""

    def test_create_with_type(self):
        """Test creating provider with explicit type."""
        config = DriverConfig_DraftDiffProvider_Mock(default_format="text")
        provider = create_diff_provider("mock", config)

        assert isinstance(provider, MockDiffProvider)

    def test_create_with_type_and_config(self):
        """Test creating provider with type and config."""
        config = DriverConfig_DraftDiffProvider_Mock(default_format="html")
        provider = create_diff_provider("mock", config)

        assert isinstance(provider, MockDiffProvider)
        assert provider.default_format == "html"

    def test_create_requires_provider_type(self):
        """Test that creating provider requires provider_type parameter."""
        with pytest.raises(ValueError, match="driver_name parameter is required"):
            create_diff_provider(None)


class TestCreateDraftDiffProvider:
    """Tests for create_draft_diff_provider typed entrypoint."""

    def test_create_typed_mock(self):
        config = AdapterConfig_DraftDiffProvider(
            draft_diff_provider_type="mock",
            driver=DriverConfig_DraftDiffProvider_Mock(default_format="text"),
        )
        provider = create_draft_diff_provider(config)
        assert isinstance(provider, MockDiffProvider)
