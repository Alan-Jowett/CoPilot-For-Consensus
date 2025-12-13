# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Retry helper utilities for handling transient failures."""

import logging
import time
from typing import Callable, TypeVar, Optional

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_with_backoff(
    func: Callable[[], T],
    max_attempts: int = 3,
    backoff_seconds: int = 5,
    max_backoff_seconds: int = 60,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
    on_failure: Optional[Callable[[Exception, int], None]] = None,
) -> T:
    """Execute a function with exponential backoff retry logic.
    
    Args:
        func: Function to execute
        max_attempts: Maximum number of retry attempts
        backoff_seconds: Base backoff time in seconds
        max_backoff_seconds: Maximum backoff time (cap)
        on_retry: Callback function called on each retry (exception, attempt_number)
        on_failure: Callback function called when all retries exhausted (exception, attempt_number)
        
    Returns:
        Result of successful function execution
        
    Raises:
        Exception: The last exception if all retries are exhausted
    """
    attempt = 0
    last_exception = None
    
    while attempt < max_attempts:
        try:
            return func()
        except Exception as e:
            attempt += 1
            last_exception = e
            
            if attempt < max_attempts:
                # Calculate exponential backoff with cap
                backoff = min(
                    backoff_seconds * (2 ** (attempt - 1)),
                    max_backoff_seconds
                )
                
                logger.info(f"Retry attempt {attempt}/{max_attempts}, waiting {backoff}s")
                
                if on_retry:
                    on_retry(e, attempt)
                
                time.sleep(backoff)
            else:
                # Max retries exceeded
                logger.error(f"All {max_attempts} retry attempts exhausted")
                
                if on_failure:
                    on_failure(e, attempt)
    
    # This should only be reached if all retries are exhausted
    if last_exception:
        raise last_exception
    else:
        raise RuntimeError("Retry logic failed without exception")
