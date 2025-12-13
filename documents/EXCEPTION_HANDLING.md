# Exception Handling Best Practices

## Overview

This document outlines best practices for exception handling in the Copilot-for-Consensus project to ensure robust error handling while avoiding suppression of system-level signals.

## Guiding Principles

### 1. Never Catch BaseException

**❌ NEVER DO THIS:**
```python
try:
    do_something()
except BaseException as e:
    logger.error(f"Error: {e}")
```

**Why?** `BaseException` is the root of the exception hierarchy and includes system-level exceptions that should NOT be caught in normal application logic:
- `SystemExit` - Raised by `sys.exit()`, prevents graceful shutdown
- `KeyboardInterrupt` - Raised when user presses Ctrl+C, prevents interruption
- `GeneratorExit` - Raised when a generator is closed, breaks generator cleanup

### 2. Handle System Signals Explicitly

**✅ CORRECT PATTERN:**
```python
try:
    service.start()
    service.subscriber.start_consuming()
except KeyboardInterrupt:
    logger.info("Service interrupted by user")
    # Perform graceful shutdown
    service.stop()
except Exception as e:
    logger.error(f"Service error: {e}", exc_info=True)
    raise
```

**Key Points:**
- Always handle `KeyboardInterrupt` separately and explicitly
- Place `KeyboardInterrupt` handler BEFORE broad `Exception` handler
- Log interruptions at appropriate level (usually INFO)
- Perform cleanup in the handler or use a `finally` block

### 3. Use Specific Exception Types

**✅ PREFERRED:**
```python
try:
    response = http_client.get(url)
except (ConnectionError, TimeoutError) as e:
    logger.error(f"Network error: {e}")
    retry()
except ValueError as e:
    logger.error(f"Invalid response: {e}")
    raise
```

**✅ ACCEPTABLE (when you can't predict specific types):**
```python
try:
    process_user_input(data)
except KeyboardInterrupt:
    raise  # Always re-raise system signals
except Exception as e:
    logger.error(f"Processing failed: {e}", exc_info=True)
    # Handle or re-raise based on context
```

### 4. Never Use Bare `except:`

**❌ NEVER DO THIS:**
```python
try:
    do_something()
except:  # Catches everything, including KeyboardInterrupt!
    logger.error("Something went wrong")
```

**✅ DO THIS INSTEAD:**
```python
try:
    do_something()
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
```

### 5. Re-raise When Appropriate

When catching exceptions for logging or cleanup, re-raise them if they can't be fully handled:

```python
try:
    critical_operation()
except Exception as e:
    logger.error(f"Critical operation failed: {e}", exc_info=True)
    # Cleanup
    cleanup_resources()
    # Re-raise to propagate the error
    raise
```

### 6. Use `finally` for Cleanup

Prefer `finally` blocks for cleanup operations that must execute regardless of success or failure:

```python
resource = acquire_resource()
try:
    use_resource(resource)
except KeyboardInterrupt:
    logger.info("Operation interrupted")
    raise
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    raise
finally:
    # Always executes, even if KeyboardInterrupt is raised
    release_resource(resource)
```

## Common Patterns in This Project

### Main Entry Points

All service main entry points follow this pattern:

```python
def run_subscriber(service):
    """Run the subscriber loop with proper signal handling."""
    try:
        service.start()
        service.subscriber.start_consuming()
    except KeyboardInterrupt:
        logger.info("Subscriber interrupted")
    except Exception as e:
        logger.error(f"Subscriber error: {e}", exc_info=True)
        raise

def main():
    """Main entry point."""
    try:
        # Initialize service
        service = create_service()
        
        # Run in thread
        subscriber_thread = threading.Thread(target=run_subscriber, args=(service,))
        subscriber_thread.start()
        
        # Start HTTP server
        uvicorn.run(app, host="0.0.0.0", port=config.http_port)
    except Exception as e:
        logger.error(f"Failed to start service: {e}", exc_info=True)
        sys.exit(1)
```

### Event Callbacks

Event processing callbacks should catch specific exceptions but allow system signals through:

```python
def handle_event(self, event: dict):
    """Process an event with proper error handling."""
    try:
        # Validate event
        self.validate_event(event)
        
        # Process event
        result = self.process_event(event)
        
        # Publish result
        self.publish_result(result)
        
    except (ValidationError, ValueError) as e:
        logger.error(f"Invalid event: {e}")
        # Send to failed queue
        self.send_to_failed_queue(event, str(e))
    except (ConnectionError, TimeoutError) as e:
        logger.error(f"Communication error: {e}")
        # Retry or fail
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing event: {e}", exc_info=True)
        # Send to failed queue
        self.send_to_failed_queue(event, str(e))
```

### Graceful Fallbacks

For optional dependencies or features, use specific exception handling:

```python
try:
    metrics = create_metrics_collector(backend=config.metrics_backend)
except (ImportError, ConnectionError) as e:
    logger.warning(f"Metrics backend unavailable: {e}")
    metrics = NoOpMetricsCollector()
```

## Testing

We have comprehensive tests to verify exception handling:

- `tests/test_exception_handling.py` - Validates that system signals are not suppressed
- Tests verify:
  - No bare `except:` clauses in code
  - No `except BaseException` in code
  - `KeyboardInterrupt` is handled before `Exception`
  - System signals propagate correctly

Run these tests before committing changes:

```bash
pytest tests/test_exception_handling.py -v
```

## Quick Reference

| Exception Type | When to Catch | Notes |
|---------------|---------------|-------|
| `BaseException` | ❌ NEVER | Includes system signals |
| `KeyboardInterrupt` | ✅ Always explicit | Handle before `Exception` |
| `SystemExit` | ❌ Rarely | Only in process supervisors |
| `GeneratorExit` | ❌ Never in apps | Generator cleanup only |
| `Exception` | ✅ Application errors | Safe for app-level handling |
| `ValueError`, `TypeError`, etc. | ✅ Preferred | Most specific is best |

## See Also

- [Python Exception Hierarchy](https://docs.python.org/3/library/exceptions.html#exception-hierarchy)
- [PEP 3134 - Exception Chaining](https://www.python.org/dev/peps/pep-3134/)
- `tests/test_exception_handling.py` - Our exception handling tests
