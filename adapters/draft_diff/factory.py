# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating draft diff providers."""

import os
from typing import Optional, Dict, Any
from .provider import DraftDiffProvider
from .datatracker_provider import DatatrackerDiffProvider
from .mock_provider import MockDiffProvider


class DiffProviderFactory:
    """Factory for creating and managing draft diff providers.
    
    This factory supports creating providers based on configuration
    or environment variables, making it easy to switch between different
    backends (e.g., for testing vs production).
    """
    
    # Registry of available provider types
    _providers = {
        "datatracker": DatatrackerDiffProvider,
        "mock": MockDiffProvider,
    }
    
    @classmethod
    def create(cls, provider_type: str, config: Optional[Dict[str, Any]] = None) -> DraftDiffProvider:
        """Create a draft diff provider instance.
        
        Args:
            provider_type: Type of provider to create (e.g., "datatracker", "mock")
            config: Optional configuration dictionary for the provider
            
        Returns:
            Instance of the requested DraftDiffProvider
            
        Raises:
            ValueError: If provider_type is not supported
        """
        if provider_type not in cls._providers:
            raise ValueError(
                f"Unknown provider type: {provider_type}. "
                f"Available providers: {', '.join(cls._providers.keys())}"
            )
        
        provider_class = cls._providers[provider_type]
        config = config or {}
        
        # Create provider with config
        return provider_class(**config)
    
    @classmethod
    def create_from_env(cls) -> DraftDiffProvider:
        """Create a draft diff provider from environment variables.
        
        Reads configuration from environment variables:
        - DRAFT_DIFF_PROVIDER: Provider type (default: "datatracker")
        - DRAFT_DIFF_BASE_URL: Base URL for datatracker provider
        - DRAFT_DIFF_FORMAT: Default format for diffs
        
        Returns:
            Configured DraftDiffProvider instance
        """
        provider_type = os.getenv("DRAFT_DIFF_PROVIDER", "datatracker")
        
        # Build config from environment
        config = {}
        
        if provider_type == "datatracker":
            base_url = os.getenv("DRAFT_DIFF_BASE_URL")
            if base_url:
                config["base_url"] = base_url
            
            format = os.getenv("DRAFT_DIFF_FORMAT")
            if format:
                config["format"] = format
        
        elif provider_type == "mock":
            format = os.getenv("DRAFT_DIFF_FORMAT")
            if format:
                config["default_format"] = format
        
        return cls.create(provider_type, config)
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type) -> None:
        """Register a new provider type.
        
        This allows external code to register custom provider implementations.
        
        Args:
            name: Name for the provider type
            provider_class: Class that implements DraftDiffProvider
            
        Raises:
            TypeError: If provider_class doesn't inherit from DraftDiffProvider
        """
        if not issubclass(provider_class, DraftDiffProvider):
            raise TypeError(
                f"Provider class must inherit from DraftDiffProvider, "
                f"got {provider_class.__name__}"
            )
        
        cls._providers[name] = provider_class


def create_diff_provider(provider_type: Optional[str] = None, 
                        config: Optional[Dict[str, Any]] = None) -> DraftDiffProvider:
    """Convenience function to create a draft diff provider.
    
    Args:
        provider_type: Optional provider type. If None, reads from environment
        config: Optional configuration dictionary
        
    Returns:
        Configured DraftDiffProvider instance
    """
    if provider_type is None:
        return DiffProviderFactory.create_from_env()
    
    return DiffProviderFactory.create(provider_type, config)
