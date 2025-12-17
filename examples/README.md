# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Validation Examples

This directory contains examples demonstrating the validation tools and patterns used in the Copilot-for-Consensus project.

## Contents

### Runtime Validation with Pydantic

**File:** `runtime_validation_pydantic.py`

Demonstrates how to use Pydantic for runtime validation of:
- Message bus event payloads
- API request/response bodies  
- Configuration files
- External API responses

**Run the examples:**

```bash
# Install Pydantic
pip install pydantic

# Run the examples
python examples/runtime_validation_pydantic.py
```

**Key benefits:**
- ✅ Catches missing required fields at runtime
- ✅ Validates field types and constraints
- ✅ Provides clear error messages
- ✅ Enables static type checking with mypy/pyright
- ✅ Auto-generates JSON schemas for documentation

## Static Analysis

For static type checking and linting examples, see the main project documentation:

- [CONTRIBUTING.md](../CONTRIBUTING.md) - Development setup and validation requirements
- [README.md](../README.md) - Code quality section

**Run static analysis:**

```bash
# Install validation tools
pip install -r requirements-dev.txt

# Run all validation checks
python scripts/validate_python.py

# Run specific checks
python scripts/validate_python.py --tool ruff      # Fast linting
python scripts/validate_python.py --tool mypy      # Type checking
python scripts/validate_python.py --tool pyright   # Advanced type checking
python scripts/validate_python.py --tool import-tests  # Import smoke tests
```

## Best Practices

1. **Always use type hints** - Enables static type checking
2. **Validate external data** - Use Pydantic for API responses and config files
3. **Run validation locally** - Use `scripts/validate_python.py` before committing
4. **Fix issues early** - Don't wait for CI to catch problems
5. **Document schemas** - Use Pydantic models as living documentation

## Additional Resources

- [Pydantic Documentation](https://docs.pydantic.dev/)
- [MyPy Documentation](https://mypy.readthedocs.io/)
- [Pyright Documentation](https://github.com/microsoft/pyright)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
