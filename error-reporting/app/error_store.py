# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Error store for managing error events."""

from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class ErrorEvent:
    """Represents a single error event."""
    
    id: str
    timestamp: str
    service: str
    level: str
    message: str
    error_type: Optional[str] = None
    stack_trace: Optional[str] = None
    context: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


class ErrorStore:
    """In-memory error store with optional persistence."""
    
    def __init__(self, max_errors: int = 10000):
        """
        Initialize error store.
        
        Args:
            max_errors: Maximum number of errors to keep in memory
        """
        self.max_errors = max_errors
        self.errors: List[ErrorEvent] = []
    
    def add_error(self, error_event: ErrorEvent) -> str:
        """
        Add an error to the store.
        
        Args:
            error_event: The error event to add
            
        Returns:
            The ID of the added error
        """
        # Add error to the beginning of the list (most recent first)
        self.errors.insert(0, error_event)
        
        # Trim if we exceed max_errors
        if len(self.errors) > self.max_errors:
            self.errors = self.errors[:self.max_errors]
        
        return error_event.id
    
    def get_errors(
        self,
        service: Optional[str] = None,
        level: Optional[str] = None,
        error_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ErrorEvent]:
        """
        Get errors with optional filtering.
        
        Args:
            service: Filter by service name
            level: Filter by error level
            error_type: Filter by error type
            limit: Maximum number of errors to return
            offset: Number of errors to skip
            
        Returns:
            List of error events matching the filters
        """
        filtered = self.errors
        
        if service:
            filtered = [e for e in filtered if e.service == service]
        
        if level:
            filtered = [e for e in filtered if e.level == level]
        
        if error_type:
            filtered = [e for e in filtered if e.error_type == error_type]
        
        return filtered[offset:offset + limit]
    
    def get_error_by_id(self, error_id: str) -> Optional[ErrorEvent]:
        """
        Get a specific error by ID.
        
        Args:
            error_id: The error ID
            
        Returns:
            The error event if found, None otherwise
        """
        for error in self.errors:
            if error.id == error_id:
                return error
        return None
    
    def get_stats(self) -> Dict:
        """
        Get error statistics.
        
        Returns:
            Dictionary with error statistics
        """
        total_errors = len(self.errors)
        
        # Count by service
        by_service = {}
        for error in self.errors:
            by_service[error.service] = by_service.get(error.service, 0) + 1
        
        # Count by level
        by_level = {}
        for error in self.errors:
            by_level[error.level] = by_level.get(error.level, 0) + 1
        
        # Count by error type
        by_type = {}
        for error in self.errors:
            if error.error_type:
                by_type[error.error_type] = by_type.get(error.error_type, 0) + 1
        
        return {
            "total_errors": total_errors,
            "by_service": by_service,
            "by_level": by_level,
            "by_type": by_type
        }
    
    def clear(self):
        """Clear all errors from the store."""
        self.errors = []
