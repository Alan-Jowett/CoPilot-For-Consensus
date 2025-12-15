<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# .github/copilot-instructions.md

## GitHub Copilot for Consensus

This repository uses GitHub Copilot to assist with code suggestions, documentation, and issue resolution. Copilot is configured to follow Open Source Software (OSS) norms for Python-based projects.

### Guidelines for Copilot Contributions

- **Code Quality**: All code suggestions must adhere to PEP 8 and PEP 257 standards.
- **Licensing**: Contributions must comply with the repository's LICENSE and respect third-party licenses.
- **Documentation**: All new features and changes should be documented in code comments and, where appropriate, in the `README.md` or relevant documentation files.
- **Testing**: Suggested code should include or update relevant unit tests.
- **Security**: Avoid introducing security vulnerabilities. Follow best practices for handling secrets, dependencies, and user input.
- **Community Standards**: Respect the CODE_OF_CONDUCT.md and contribute constructively.

### How to Use Copilot

- Use Copilot for code completion, documentation, and refactoring.
- Review Copilot suggestions before committing.
- When committing changes, use `git commit -sm "<message>"` to include the sign-off.
- Report issues or unexpected behavior in the issues section.

### Maintainers

Repository maintainers are responsible for reviewing Copilot-generated code and ensuring compliance with project standards.

---

For more information, see [CONTRIBUTING.md](documents/CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](documents/CODE_OF_CONDUCT.md).

## CI & Testing Overview

- **PRs Required**: Direct pushes to `main` are blocked. Open a PR; required check includes the `Test Docker Compose` job.
- **Adapters CI**: [adapters-ci.yml](.github/workflows/adapters-ci.yml) orchestrates unit and integration tests per adapter using reusable workflows.
  - **Unit**: [adapter-reusable-unit-test-ci.yml](.github/workflows/adapter-reusable-unit-test-ci.yml) runs `pytest` with `-m "not integration"`, uploads JUnit and coverage (`lcov`, `html`), and reports via `dorny/test-reporter`.
  - **Integrations**: [adapter-reusable-integration-ci.yml](.github/workflows/adapter-reusable-integration-ci.yml) spins services (MongoDB, RabbitMQ) and optional rsync fixtures; runs `pytest -m integration` with coverage and artifacts.
  - **Vectorstore**: [adapter-reusable-vectorstore-integration-ci.yml](.github/workflows/adapter-reusable-vectorstore-integration-ci.yml) provisions Qdrant and runs `pytest -m integration` for vectorstore adapters.
  - **Coverage**: Coveralls uploads per job; a carryforward summary finalizes on `main`.
- **Services CI**: [services-ci.yml](.github/workflows/services-ci.yml) triggers service tests via [service-reusable-unit-test-ci.yml](.github/workflows/service-reusable-unit-test-ci.yml).
  - **Tests**: Runs `pytest` for unit and integration together, generates coverage and JUnit, and reports via `dorny/test-reporter`.
  - **Lint/Security**: `flake8`, `pylint`, and `bandit` checks run per service.
  - **Docker Build**: Builds each service Dockerfile using Buildx (no push); summarized with a gated `summary` job.
  - **Coverage**: Coveralls uploads per service with a parallel-finished step on `main`.
- **System Integration**: [docker-compose-ci.yml](.github/workflows/docker-compose-ci.yml) builds all images, brings up infra (MongoDB, RabbitMQ, Qdrant, Prometheus, Pushgateway, Loki, Grafana, Promtail), starts services, runs ingestion, and health-checks HTTP endpoints. This job is the required status check.
- **Policy Checks**:
  - **License Headers**: [license-header-check.yml](.github/workflows/license-header-check.yml) runs `scripts/check_license_headers.py`.
  - **Mutable Defaults**: [mutable-defaults-check.yml](.github/workflows/mutable-defaults-check.yml) runs `scripts/check_mutable_defaults.py`.
  - **Dependabot Config**: [check-dependabot.yml](.github/workflows/check-dependabot.yml) validates `.github/dependabot.yml`, opening/closing issues automatically.

### What Copilot Should Do

- Prefer PRs over direct pushes and ensure CI passes, especially `Test Docker Compose`.
- When changing an adapter or service, run the corresponding CI-equivalent test suite locally; if uncertain which one applies, run all adapter and service CI test suites locally.
- Include tests and coverage for changes in adapters/services; use `-m integration` marks appropriately.
- Respect lint (`flake8`, `pylint`) and security (`bandit`) standards.
- Update or add Dockerfiles and compose services cautiously; CI will validate health endpoints.
- Always include the repository license header on new files: add the SPDX line `SPDX-License-Identifier: MIT` at the top and maintain existing header format used across this repo.

### License Header Examples

- Python:

```python
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Module description."""
```

- YAML (GitHub Actions, Compose):

```yaml
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

name: Example Workflow
```

- Markdown:

```markdown
<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Document Title
```

## How To Run Tests Locally

### Adapter Unit Tests

- Purpose: fast tests excluding integration (`-m "not integration"`).
- From adapter folder (example `adapters/copilot_storage`):

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt || true
pip install pytest pytest-cov
pytest tests/ -v --tb=short -m "not integration" \
  --junit-xml=test-results.xml \
  --cov=copilot_storage --cov-report=lcov --cov-report=html --cov-report=term
```

Windows (PowerShell):

```powershell
python -m pip install --upgrade pip
if (Test-Path requirements.txt) { pip install -r requirements.txt } else { Write-Host "No requirements.txt" }
pip install pytest pytest-cov
pytest tests/ -v --tb=short -m "not integration" `
  --junit-xml=test-results.xml `
  --cov=copilot_storage --cov-report=lcov --cov-report=html --cov-report=term
```

### Adapter Integration Tests (MongoDB/RabbitMQ)

- Purpose: exercises external dependencies and message bus.
- Prereqs: running MongoDB and RabbitMQ locally, or via Docker.
- Start infra with Docker (recommended):

```bash
docker run -d --name ci-mongo -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=testuser -e MONGO_INITDB_ROOT_PASSWORD=testpass mongo:7.0
docker run -d --name ci-rabbit -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=guest -e RABBITMQ_DEFAULT_PASS=guest rabbitmq:3-management
```

Windows (PowerShell):

```powershell
docker run -d --name ci-mongo -p 27017:27017 `
  -e MONGO_INITDB_ROOT_USERNAME=testuser -e MONGO_INITDB_ROOT_PASSWORD=testpass mongo:7.0
docker run -d --name ci-rabbit -p 5672:5672 -p 15672:15672 `
  -e RABBITMQ_DEFAULT_USER=guest -e RABBITMQ_DEFAULT_PASS=guest rabbitmq:3-management
```

- Run tests from the adapter folder (set env expected by workflows):

```bash
export MONGODB_HOST=localhost
export MONGODB_PORT=27017
export MONGODB_USERNAME=testuser
export MONGODB_PASSWORD=testpass
export MONGODB_DATABASE=test_copilot
export RABBITMQ_HOST=localhost
export RABBITMQ_PORT=5672
export RABBITMQ_USERNAME=guest
export RABBITMQ_PASSWORD=guest

python -m pip install --upgrade pip
pip install pytest pytest-cov pymongo pika
pytest tests -v -m integration --tb=short \
  --junit-xml=integration-test-results.xml \
  --cov=copilot_storage --cov-report=lcov:integration-coverage.lcov \
  --cov-report=html:integration-htmlcov --cov-report=term
```

Windows (PowerShell):

```powershell
$env:MONGODB_HOST = "localhost"
$env:MONGODB_PORT = "27017"
$env:MONGODB_USERNAME = "testuser"
$env:MONGODB_PASSWORD = "testpass"
$env:MONGODB_DATABASE = "test_copilot"
$env:RABBITMQ_HOST = "localhost"
$env:RABBITMQ_PORT = "5672"
$env:RABBITMQ_USERNAME = "guest"
$env:RABBITMQ_PASSWORD = "guest"

python -m pip install --upgrade pip
pip install pytest pytest-cov pymongo pika
pytest tests -v -m integration --tb=short `
  --junit-xml=integration-test-results.xml `
  --cov=copilot_storage --cov-report=lcov:integration-coverage.lcov `
  --cov-report=html:integration-htmlcov --cov-report=term
```

### Vectorstore Adapter Integration Tests (Qdrant)

- Purpose: tests vectorstore integration using Qdrant.
- Start Qdrant:

```bash
docker run -d --name ci-qdrant -p 6333:6333 qdrant/qdrant:latest
```

Windows (PowerShell):

```powershell
docker run -d --name ci-qdrant -p 6333:6333 qdrant/qdrant:latest
```

- Run tests from `adapters/copilot_vectorstore`:

```bash
export QDRANT_HOST=localhost
export QDRANT_PORT=6333
export QDRANT_COLLECTION=test_embeddings

python -m pip install --upgrade pip
pip install pytest pytest-cov qdrant-client
pytest tests -v -m integration --tb=short \
  --junit-xml=integration-test-results.xml \
  --cov=copilot_vectorstore --cov-report=lcov:integration-coverage.lcov \
  --cov-report=html:integration-htmlcov --cov-report=term
```

Windows (PowerShell):

```powershell
$env:QDRANT_HOST = "localhost"
$env:QDRANT_PORT = "6333"
$env:QDRANT_COLLECTION = "test_embeddings"

python -m pip install --upgrade pip
pip install pytest pytest-cov qdrant-client
pytest tests -v -m integration --tb=short `
  --junit-xml=integration-test-results.xml `
  --cov=copilot_vectorstore --cov-report=lcov:integration-coverage.lcov `
  --cov-report=html:integration-htmlcov --cov-report=term
```

### Service Tests (Unit + Integration)

- Purpose: run service test suite and coverage locally.
- Example for `chunking` service (repeat for others):

```bash
cd chunking
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest pytest-cov
pytest tests/ -v --tb=short \
  --junit-xml=test-results.xml \
  --cov=app --cov-report=lcov --cov-report=html --cov-report=term
```

Windows (PowerShell):

```powershell
Set-Location chunking
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest pytest-cov
pytest tests/ -v --tb=short `
  --junit-xml=test-results.xml `
  --cov=app --cov-report=lcov --cov-report=html --cov-report=term
```

### Full System Integration (Docker Compose)

- Purpose: validate entire stack with infra and services.
- Commands (from repo root):

```bash
docker compose build --parallel
docker compose up -d documentdb messagebus vectorstore ollama monitoring pushgateway loki grafana promtail
docker compose run --rm db-init
docker compose run --rm db-validate
docker compose run --rm vectorstore-validate
docker compose run --rm ollama-validate
docker compose up -d parsing chunking embedding orchestrator summarization reporting error-reporting
docker compose run --rm ingestion
# quick health checks
curl -f http://localhost:8080/      # reporting
curl -f http://localhost:8081/      # error-reporting
curl -f http://localhost:3000/api/health  # grafana
curl -f http://localhost:9090/-/healthy   # prometheus
curl -f http://localhost:3100/ready       # loki
docker compose down
```

Windows (PowerShell):

```powershell
docker compose build --parallel
docker compose up -d documentdb messagebus vectorstore ollama monitoring pushgateway loki grafana promtail
docker compose run --rm db-init
docker compose run --rm db-validate
docker compose run --rm vectorstore-validate
docker compose run --rm ollama-validate
docker compose up -d parsing chunking embedding orchestrator summarization reporting error-reporting
docker compose run --rm ingestion
# quick health checks
Invoke-WebRequest -UseBasicParsing http://localhost:8080/ | Out-Null
Invoke-WebRequest -UseBasicParsing http://localhost:8081/ | Out-Null
Invoke-WebRequest -UseBasicParsing http://localhost:3000/api/health | Out-Null
Invoke-WebRequest -UseBasicParsing http://localhost:9090/-/healthy | Out-Null
Invoke-WebRequest -UseBasicParsing http://localhost:3100/ready | Out-Null
docker compose down
```

Notes:
- Prefer running per-adapter/service tests before system tests for faster feedback.
- Match `pytest -m integration` for integration-only runs; use `-m "not integration"` for unit.
- Coverage artifacts are written to `coverage.lcov` and `htmlcov/` by convention.
