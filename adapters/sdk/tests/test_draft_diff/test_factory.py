# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for draft diff provider factory."""

import os
import pytest
from draft_diff.factory import DiffProviderFactory, create_diff_provider
from draft_diff.provider import DraftDiffProvider
from draft_diff.datatracker_provider import DatatrackerDiffProvider
from draft_diff.mock_provider import MockDiffProvider


class TestDiffProviderFactory:
    """Tests for DiffProviderFactory."""
    
    def test_create_datatracker_provider(self):
        """Test creating datatracker provider."""
        provider = DiffProviderFactory.create("datatracker")
        
        assert isinstance(provider, DatatrackerDiffProvider)
        assert provider.base_url == "https://datatracker.ietf.org"
    
    def test_create_datatracker_provider_with_config(self):
        """Test creating datatracker provider with custom config."""
        config = {
            "base_url": "https://custom.example.com",
            "format": "text"
        }
        provider = DiffProviderFactory.create("datatracker", config)
        
        assert isinstance(provider, DatatrackerDiffProvider)
        assert provider.base_url == "https://custom.example.com"
        assert provider.format == "text"
    
    def test_create_mock_provider(self):
        """Test creating mock provider."""
        provider = DiffProviderFactory.create("mock")
        
        assert isinstance(provider, MockDiffProvider)
        assert provider.default_format == "text"
    
    def test_create_mock_provider_with_config(self):
        """Test creating mock provider with custom config."""
        config = {"default_format": "html"}
        provider = DiffProviderFactory.create("mock", config)
        
        assert isinstance(provider, MockDiffProvider)
        assert provider.default_format == "html"
    
    def test_create_unknown_provider(self):
        """Test that creating unknown provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown provider type: unknown"):
            DiffProviderFactory.create("unknown")
    
    def test_create_from_env_default(self):
        """Test creating provider from environment with defaults."""
        # Clear any existing env vars
        for key in ["DRAFT_DIFF_PROVIDER", "DRAFT_DIFF_BASE_URL", "DRAFT_DIFF_FORMAT"]:
            os.environ.pop(key, None)
        
        provider = DiffProviderFactory.create_from_env()
        
        assert isinstance(provider, DatatrackerDiffProvider)
        assert provider.base_url == "https://datatracker.ietf.org"
    
    def test_create_from_env_mock_provider(self):
        """Test creating mock provider from environment."""
        os.environ["DRAFT_DIFF_PROVIDER"] = "mock"
        
        try:
            provider = DiffProviderFactory.create_from_env()
            
            assert isinstance(provider, MockDiffProvider)
        finally:
            os.environ.pop("DRAFT_DIFF_PROVIDER", None)
    
    def test_create_from_env_with_config(self):
        """Test creating provider from environment with custom config."""
        os.environ["DRAFT_DIFF_PROVIDER"] = "datatracker"
        os.environ["DRAFT_DIFF_BASE_URL"] = "https://test.example.com"
        os.environ["DRAFT_DIFF_FORMAT"] = "text"
        
        try:
            provider = DiffProviderFactory.create_from_env()
            
            assert isinstance(provider, DatatrackerDiffProvider)
            assert provider.base_url == "https://test.example.com"
            assert provider.format == "text"
        finally:
            for key in ["DRAFT_DIFF_PROVIDER", "DRAFT_DIFF_BASE_URL", "DRAFT_DIFF_FORMAT"]:
                os.environ.pop(key, None)
    
    def test_create_from_env_mock_with_format(self):
        """Test creating mock provider from environment with format."""
        os.environ["DRAFT_DIFF_PROVIDER"] = "mock"
        os.environ["DRAFT_DIFF_FORMAT"] = "markdown"
        
        try:
            provider = DiffProviderFactory.create_from_env()
            
            assert isinstance(provider, MockDiffProvider)
            assert provider.default_format == "markdown"
        finally:
            for key in ["DRAFT_DIFF_PROVIDER", "DRAFT_DIFF_FORMAT"]:
                os.environ.pop(key, None)
    
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
        provider = create_diff_provider("mock")
        
        assert isinstance(provider, MockDiffProvider)
    
    def test_create_with_type_and_config(self):
        """Test creating provider with type and config."""
        config = {"default_format": "html"}
        provider = create_diff_provider("mock", config)
        
        assert isinstance(provider, MockDiffProvider)
        assert provider.default_format == "html"
    
    def test_create_from_env(self):
        """Test creating provider from environment."""
        os.environ["DRAFT_DIFF_PROVIDER"] = "mock"
        
        try:
            provider = create_diff_provider()
            
            assert isinstance(provider, MockDiffProvider)
        finally:
            os.environ.pop("DRAFT_DIFF_PROVIDER", None)
