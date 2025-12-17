<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Contributing to Copilot-for-Consensus

Thank you for your interest in contributing! This project thrives on community collaboration and follows open-source best practices for transparency, inclusivity, and quality.

***

## Project Governance

See [GOVERNANCE.md](./GOVERNANCE.md) for details.

***

## How to Contribute

### Reporting Issues

*   Use the **Issues** tab for:
    *   Bug reports
    *   Feature requests
    *   Documentation improvements
*   Include clear details, steps to reproduce, and expected behavior.

### Submitting Pull Requests

*   Fork the repository and create a feature branch:

    ```sh
    git checkout -b feature/my-new-feature
    ```
*   Follow coding standards:
    *   Python: PEP 8 compliance
    *   Include docstrings and type hints
    *   Pass all static analysis checks (ruff, mypy, pyright, pylint)
*   Add tests for new functionality.
*   Submit a PR with:
    *   A descriptive title
    *   Clear explanation of changes
    *   Reference related issues (if any)

### Code of Conduct

*   All contributors must adhere to the [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md).
*   Be respectful, inclusive, and constructive in all interactions.

### Security

*   Follow the security guidelines in [SECURITY.md](./SECURITY.md).
*   Never commit secrets, credentials, or sensitive data.
*   Report security vulnerabilities privately (see [SECURITY.md](./SECURITY.md)).

***

## Development Guidelines

*   **Architecture:** Microservice-based, containerized design. See [documents/ARCHITECTURE.md](./documents/ARCHITECTURE.md) for system overview.
*   **Language:** Python-first for accessibility.
*   **Testing:** Unit tests for core logic, integration tests for pipeline components.
*   **Documentation:** Update README.md and relevant docs for any new feature.
*   **Forward Progress:** All services must guarantee forward progress through idempotency, retry logic, and proper error handling. See [documents/FORWARD_PROGRESS.md](./documents/FORWARD_PROGRESS.md) for detailed patterns and implementation guidelines.

### Development Environment Setup

To set up your development environment with all validation tools:

```bash
# Clone the repository
git clone https://github.com/Alan-Jowett/CoPilot-For-Consensus.git
cd CoPilot-For-Consensus

# Install development dependencies (includes type checkers and linters)
pip install -r requirements-dev.txt

# Install pre-commit hooks
pip install pre-commit
pre-commit install
```

### Static Analysis and Validation

This project uses comprehensive static analysis to catch attribute errors, missing fields, and type issues before they reach production:

*   **Ruff**: Fast Python linter for syntax and style checks
*   **MyPy**: Static type checker with strict mode enabled
*   **Pyright**: Advanced type checker for catching attribute errors
*   **Pylint**: Additional linting focused on attribute and member access

All pull requests must pass these checks in CI. To run validation locally:

```bash
# Run all linters and type checkers
ruff check .                          # Fast linting
mypy <module_path>                    # Type checking with mypy
npx pyright <module_path>            # Type checking with pyright
pylint <module_path> --disable=all --enable=E1101,E0611,E1102,E1120,E1121

# Run import smoke tests
pytest tests/test_imports.py -v
```

The CI pipeline includes:
- Static type checking (mypy, pyright)
- Linting (ruff, pylint)
- Import smoke tests to ensure all modules load without errors
- Runtime validation for configs and JSON payloads (via Pydantic where applicable)

### Key Patterns for Contributors

When implementing new microservices or modifying existing ones, follow these patterns:

*   **Idempotency:** Process the same input multiple times safely without errors or duplicate data
*   **Status Fields:** Use binary states (pending/completed) rather than intermediate "processing" states
*   **Requeue on Failure:** Re-raise exceptions to trigger message requeue for transient failures
*   **Retry Policies:** Implement exponential backoff with configurable max retries
*   **Observability:** Integrate metrics collection, error reporting, and appropriate logging

For complete details, code examples, and testing patterns, see [documents/FORWARD_PROGRESS.md](./documents/FORWARD_PROGRESS.md).

***

## Review Process

*   PRs reviewed by at least two maintainers.
*   Automated checks (linting, tests) must pass before merging.
*   Significant changes may require design discussions via GitHub Discussions.

***

## Long-Term Vision

Contributors are encouraged to think beyond MVP:

*   Interactive subject matter expert powered by RFCs and mailing list history.
*   Semantic search and Q&A capabilities.
*   Multi-language support and accessibility features.

***

## Licensing

By contributing, you agree that your contributions will be licensed under the MIT License.

***

## Join the Community

*   Participate in GitHub Discussions.
*   Share ideas and feedback.
*   Help us build an open, transparent, and impactful tool for technical collaboration.

***

**Thank you for helping make Copilot-for-Consensus better!**

***
