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

### Platform-Aware Command Suggestions

**IMPORTANT**: When suggesting shell commands, **always consider the user's operating system**. The following guidelines apply:

- **On Windows**: Suggest PowerShell commands or `cmd.exe` equivalents, NOT Linux-only utilities like `head`, `tail`, `sed`, `awk`, `grep`, `cut`, etc.
  - Use PowerShell cmdlets (e.g., `Get-Content`, `Select-Object`, `Where-Object`, `ConvertTo-Json`) instead of Linux utilities.
  - Use Windows path separators (`\`) or generic patterns that work cross-platform (`/` also works in PowerShell).
  - Examples: `type filename.txt` instead of `cat`, `findstr` instead of `grep`, `Invoke-WebRequest` instead of `curl` (though curl may be available on newer Windows).

- **On Linux/macOS**: You may use standard Unix utilities.

- **For cross-platform scripts**: Prefer Python scripts or Node.js over shell scripts. When shell is necessary, use POSIX-compatible syntax that works on both platforms, and provide platform-specific variants (bash/PowerShell) as shown in the testing examples below.

- **Docker & Docker Compose**: These are typically cross-platform; however, always test commands on both Windows PowerShell and bash shells if contributors use either.

**Examples of what NOT to suggest on Windows**:
- ❌ `head -n 5 file.txt` → Use `Get-Content file.txt -Head 5` instead
- ❌ `tail -f log.txt` → Use `Get-Content log.txt -Wait` instead
- ❌ `grep "pattern" file.txt` → Use `Select-String -Pattern "pattern" file.txt` instead
- ❌ `sed 's/old/new/g' file.txt` → Use PowerShell string replacement or a Python script instead
- ❌ `awk '{print $1}' file.txt` → Use `Select-String` with regex and `ForEach-Object` instead

### Maintainers

Repository maintainers are responsible for reviewing Copilot-generated code and ensuring compliance with project standards.

---

For more information, see [CONTRIBUTING.md](documents/CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](documents/CODE_OF_CONDUCT.md).

### Natural Language Intents (Copilot Shortcuts)

The following phrases map to concrete, platform-aware actions. Copilot should run the appropriate commands for the user's OS (PowerShell on Windows; bash on Linux/macOS).

#### "startup the project"

Meaning: build fresh images, start all services in the background, and verify health.

Linux/macOS (bash):

```bash
docker compose build --no-cache --parallel
docker compose up -d
# Quick status summary
docker compose ps

# Optional: wait for key services to be healthy (mirrors CI strategy)
for s in documentdb messagebus vectorstore ollama monitoring pushgateway grafana promtail parsing chunking embedding orchestrator summarization reporting ui gateway; do
  echo "Waiting for $s ..."
  # Loki has no healthcheck; treat any "Up" as ready
  if [ "$s" = "loki" ]; then
    until docker compose ps loki --format '{{.Status}}' | grep -q "Up"; do sleep 3; done
  else
    until docker compose ps "$s" --format '{{.Status}}' | grep -q "(healthy)"; do sleep 3; done
  fi
done
```

Windows (PowerShell):

```powershell
docker compose build --no-cache --parallel
docker compose up -d
# Quick status summary
docker compose ps

# Optional: wait for key services to be healthy (mirrors CI strategy)
$services = @('documentdb','messagebus','vectorstore','ollama','monitoring','pushgateway','grafana','promtail','parsing','chunking','embedding','orchestrator','summarization','reporting','ui','gateway')
foreach ($s in $services) {
  Write-Host "Waiting for $s ..."
  if ($s -eq 'loki') {
    while (-not ((docker compose ps loki --format '{{.Status}}') -match 'Up')) { Start-Sleep -Seconds 3 }
  } else {
    while (-not ((docker compose ps $s --format '{{.Status}}') -match '\(healthy\)')) { Start-Sleep -Seconds 3 }
  }
}
```

#### "ingest test data"

Meaning: start the continuous ingestion service, copy the sample mailbox into the running container, create the source via the ingestion REST API, then trigger ingestion. Use the REST API instead of `upload_ingestion_sources.py`.

Linux/macOS (bash):

```bash
# 1) Start ingestion service (proxied via API Gateway on localhost:8080/ingestion)
docker compose up -d ingestion gateway

# 2) Copy the sample mailbox into the running container
INGESTION_CONTAINER=$(docker compose ps -q ingestion)
docker exec "$INGESTION_CONTAINER" mkdir -p /tmp/test-mailbox
docker cp tests/fixtures/mailbox_sample/test-archive.mbox "$INGESTION_CONTAINER":/tmp/test-mailbox/test-archive.mbox

# 3) Create the source via REST API (through gateway)
curl -f -X POST http://localhost:8080/ingestion/api/sources \
  -H "Content-Type: application/json" \
  -d '{"name":"test-mailbox","source_type":"local","url":"/tmp/test-mailbox/test-archive.mbox","enabled":true}'

# 4) Trigger ingestion via REST API
curl -f -X POST http://localhost:8080/ingestion/api/sources/test-mailbox/trigger
```

Windows (PowerShell):

```powershell
# 1) Start ingestion service (through gateway)
docker compose up -d ingestion gateway

# 2) Copy the sample mailbox into the running container
$ingestion = docker compose ps -q ingestion
docker exec $ingestion mkdir -p /tmp/test-mailbox
docker cp tests/fixtures/mailbox_sample/test-archive.mbox "$ingestion`:/tmp/test-mailbox/test-archive.mbox"

# 3) Create the source via REST API (through gateway)
$payload = '{"name":"test-mailbox","source_type":"local","url":"/tmp/test-mailbox/test-archive.mbox","enabled":true}'
curl -f -X POST http://localhost:8080/ingestion/api/sources -H "Content-Type: application/json" -d $payload

# 4) Trigger ingestion via REST API
curl -f -X POST http://localhost:8080/ingestion/api/sources/test-mailbox/trigger
```

Quick verification (optional):

```powershell
# Reporting API should return a non-zero count (via gateway /reporting prefix)
($r = Invoke-WebRequest -UseBasicParsing http://localhost:8080/reporting/api/reports).Content | ConvertFrom-Json | Select-Object -ExpandProperty count
```

#### "cleanup the project"

Meaning: stop all Docker Compose services and remove associated volumes (data loss for services using named volumes).

Linux/macOS (bash):

```bash
docker compose down -v
```

Windows (PowerShell):

```powershell
docker compose down -v
```

#### "ingest live data from ietf-<topic>"

Meaning: create an IETF mailing list source via the ingestion REST API (no upload script), then trigger ingestion. Example: "ingest live data from ietf-ipsec" creates a source named "ietf-ipsec" with URL "rsync.ietf.org::mailman-archive/ipsec/".

Linux/macOS (bash):

```bash
# 1) Start ingestion service (if not already running) and gateway
docker compose up -d ingestion gateway

# 2) Create the source via REST API
TOPIC="ipsec"  # change to desired topic, e.g. "dnsop"
curl -f -X POST http://localhost:8080/ingestion/api/sources \
  -H "Content-Type: application/json" \
  -d '{"name":"ietf-'"${TOPIC}"'","source_type":"rsync","url":"rsync.ietf.org::mailman-archive/'"${TOPIC}"'/","enabled":true}'

# 3) Trigger ingestion via REST API
curl -f -X POST http://localhost:8080/ingestion/api/sources/ietf-${TOPIC}/trigger
```

Windows (PowerShell):

```powershell
# 1) Start ingestion service and gateway
docker compose up -d ingestion gateway

# 2) Create the source via REST API
$topic = "ipsec"  # Change this to your desired topic
$payload = "{`"name`":`"ietf-$topic`",`"source_type`":`"rsync`",`"url`":`"rsync.ietf.org::mailman-archive/$topic/`",`"enabled`":true}"
curl -f -X POST http://localhost:8080/ingestion/api/sources -H "Content-Type: application/json" -d $payload

# 3) Trigger ingestion via REST API
curl -f -X POST "http://localhost:8080/ingestion/api/sources/ietf-$topic/trigger"
```

Example usage:
- `"ingest live data from ietf-ipsec"` → ingests from `rsync.ietf.org::mailman-archive/ipsec/`
- `"ingest live data from ietf-quic"` → ingests from `rsync.ietf.org::mailman-archive/quic/`
- `"ingest live data from ietf-http"` → ingests from `rsync.ietf.org::mailman-archive/http/`

#### "test the current change"

Meaning: examine the current branch relative to main, identify which adapter or microservice was modified, and run the appropriate test suite. For adapters (e.g., `adapters/copilot_events`), run unit tests excluding integration. For services (e.g., `orchestrator`, `chunking`), run both unit and integration tests. Coverage and JUnit artifacts are generated.

Linux/macOS (bash):

```bash
# 1) Find changed files relative to main
CHANGED_FILES=$(git diff origin/main --name-only)

# 2) Determine if it's an adapter or service change
if echo "$CHANGED_FILES" | grep -q "^adapters/"; then
  # Adapter change: extract adapter name and run unit tests (excluding integration)
  ADAPTER=$(echo "$CHANGED_FILES" | grep "^adapters/" | head -1 | cut -d/ -f2)
  ADAPTER_PATH="adapters/$ADAPTER"
  
  echo "Running unit tests for adapter: $ADAPTER"
  cd "$ADAPTER_PATH"
  python -m pip install --upgrade pip
  pip install -r requirements.txt 2>/dev/null || true
  pip install pytest pytest-cov
  pytest tests/ -v --tb=short -m "not integration" \
    --junit-xml=test-results.xml \
    --cov=$(basename "$ADAPTER_PATH") --cov-report=lcov --cov-report=html --cov-report=term
  
elif echo "$CHANGED_FILES" | grep -qE "^(chunking|embedding|parsing|orchestrator|summarization|reporting|ingestion)/"; then
  # Service change: extract service name and run all tests (unit + integration)
  SERVICE=$(echo "$CHANGED_FILES" | grep -oE "^(chunking|embedding|parsing|orchestrator|summarization|reporting|ingestion)" | head -1)
  
  echo "Running tests for service: $SERVICE"
  cd "$SERVICE"
  python -m pip install --upgrade pip
  pip install -r requirements.txt 2>/dev/null || true
  pip install pytest pytest-cov
  pytest tests/ -v --tb=short \
    --junit-xml=test-results.xml \
    --cov=app --cov-report=lcov --cov-report=html --cov-report=term
else
  echo "No adapter or service changes detected."
  exit 1
fi
```

Windows (PowerShell):

```powershell
# 1) Find changed files relative to main
$changedFiles = git diff origin/main --name-only

# 2) Determine if it's an adapter or service change
$adapterMatch = $changedFiles | Where-Object { $_ -match "^adapters/" } | Select-Object -First 1
$serviceMatch = $changedFiles | Where-Object { $_ -match "^(chunking|embedding|parsing|orchestrator|summarization|reporting|ingestion)/" } | Select-Object -First 1

if ($adapterMatch) {
  # Adapter change: extract adapter name and run unit tests (excluding integration)
  $adapter = $adapterMatch -replace "^adapters/", "" -replace "/.*", ""
  $adapterPath = "adapters/$adapter"
  
  Write-Host "Running unit tests for adapter: $adapter"
  Push-Location $adapterPath
  python -m pip install --upgrade pip
  if (Test-Path requirements.txt) { pip install -r requirements.txt } else { Write-Host "No requirements.txt" }
  pip install pytest pytest-cov
  pytest tests/ -v --tb=short -m "not integration" `
    --junit-xml=test-results.xml `
    --cov=$adapter --cov-report=lcov --cov-report=html --cov-report=term
  Pop-Location
  
} elseif ($serviceMatch) {
  # Service change: extract service name and run all tests (unit + integration)
  $service = $serviceMatch -replace "/.*", ""
  
  Write-Host "Running tests for service: $service"
  Push-Location $service
  python -m pip install --upgrade pip
  if (Test-Path requirements.txt) { pip install -r requirements.txt } else { Write-Host "No requirements.txt" }
  pip install pytest pytest-cov
  pytest tests/ -v --tb=short `
    --junit-xml=test-results.xml `
    --cov=app --cov-report=lcov --cov-report=html --cov-report=term
  Pop-Location
  
} else {
  Write-Host "No adapter or service changes detected."
  exit 1
}
```

Example usage:
- `"test the current change"` (on a branch modifying `adapters/copilot_events`) → runs `adapters/copilot_events/tests/` unit tests
- `"test the current change"` (on a branch modifying `chunking`) → runs `chunking/tests/` all tests (unit + integration)

#### "run the docker compose workflow"

Meaning: execute the Docker Compose end-to-end validation workflow locally, mirroring the steps in [docker-compose-ci.yml](.github/workflows/docker-compose-ci.yml). The workflow builds all services, starts infrastructure and application services with health checks, runs test ingestion, validates end-to-end message flow, tests all service endpoints, and stops services cleanly. Stops immediately on first error for quick feedback.

Linux/macOS (bash):

```bash
set -e  # Stop on first error
trap 'echo "Workflow failed at step $LINENO"; exit 1' ERR

echo "=== Docker Compose Workflow (Local) ==="

# Clean up
echo "Cleaning up existing containers and volumes..."
docker compose down -v || true
docker container prune -f || true

# Validate config
echo "Validating docker-compose configuration..."
docker compose config > /dev/null

# Build
echo "Building all services in parallel..."
docker compose build --parallel

# Infrastructure Services
echo "Starting infrastructure services..."
for svc in documentdb messagebus vectorstore ollama monitoring pushgateway loki grafana promtail; do
  echo "  Starting $svc..."
  docker compose up -d $svc
  if [ "$svc" = "loki" ]; then
    timeout 60s bash -c "until docker compose ps loki --format '{{.Status}}' | grep -q 'Up'; do sleep 3; done" || { echo "❌ $svc failed"; docker compose logs $svc --tail=50; exit 1; }
  else
    timeout 60s bash -c "until docker compose ps $svc --format '{{.Status}}' | grep -q '(healthy)'; do sleep 3; done" || { echo "❌ $svc failed"; docker compose logs $svc --tail=50; exit 1; }
  fi
done
echo "✓ Infrastructure services healthy"

# Validators
echo "Running validators..."
for validator in db-init db-validate vectorstore-validate ollama-validate; do
  echo "  Running $validator..."
  docker compose run --rm $validator || { echo "❌ $validator failed"; exit 1; }
done
echo "✓ Validators passed"

# Application Services
echo "Starting application services..."
for svc in parsing chunking embedding orchestrator summarization reporting ui; do
  echo "  Starting $svc..."
  docker compose up -d $svc
  timeout 120s bash -c "until docker compose ps $svc --format '{{.Status}}' | grep -q '(healthy)'; do sleep 3; done" || { echo "❌ $svc failed"; docker compose logs $svc --tail=50; exit 1; }
done
echo "✓ Application services healthy"

# Ingestion
echo "Starting ingestion service..."
docker compose up -d ingestion
(timeout 120s bash -c "until docker compose ps ingestion --format '{{.Status}}' | grep -q '(healthy)'; do echo 'Waiting for ingestion service...'; sleep 3; done" && echo "✓ Ingestion service healthy") || { docker compose logs ingestion --tail=50; exit 1; }

echo "Copying test mailbox into ingestion container..."
INGESTION_CONTAINER=$(docker compose ps -q ingestion)
[ -n "$INGESTION_CONTAINER" ] || { echo "❌ Ingestion container not running"; exit 1; }
docker exec "$INGESTION_CONTAINER" mkdir -p /tmp/test-mailbox
docker cp tests/fixtures/mailbox_sample/test-archive.mbox "$INGESTION_CONTAINER":/tmp/test-mailbox/test-archive.mbox
echo "✓ Test mailbox copied"

echo "Creating ingestion source via REST API..."
payload='{"name":"test-mailbox","source_type":"local","url":"/tmp/test-mailbox/test-archive.mbox","enabled":true}'
max_attempts=5
attempt=1
while [ $attempt -le $max_attempts ]; do
  if curl -f -X POST http://localhost:8080/ingestion/api/sources \
    -H "Content-Type: application/json" \
    -d "$payload"; then
    echo "✓ Ingestion source created (attempt $attempt/$max_attempts)"
    break
  fi
  echo "Attempt $attempt/$max_attempts: Failed to create source, retrying..."
  sleep 2
  attempt=$((attempt + 1))
done

if [ $attempt -gt $max_attempts ]; then
  echo "❌ Failed to create ingestion source after $max_attempts attempts"
  docker compose logs ingestion --tail=50
  exit 1
fi

echo "Triggering ingestion via REST API..."
max_attempts=5
attempt=1
while [ $attempt -le $max_attempts ]; do
  if curl -f -X POST http://localhost:8080/ingestion/api/sources/test-mailbox/trigger; then
    echo "✓ Ingestion triggered successfully (attempt $attempt/$max_attempts)"
    break
  fi
  echo "Attempt $attempt/$max_attempts: Failed to trigger ingestion, retrying..."
  sleep 2
  attempt=$((attempt + 1))
done

if [ $attempt -gt $max_attempts ]; then
  echo "❌ Failed to trigger ingestion after $max_attempts attempts"
  docker compose logs ingestion --tail=50
  exit 1
fi

echo "Waiting for ingestion to complete..."
sleep 10
status=$(curl -s http://localhost:8080/ingestion/api/sources/test-mailbox/status)
echo "Ingestion status: $status"

# End-to-end validation
echo "Validating end-to-end message flow..."
docker compose run --rm \
  -v "$PWD/tests:/app/tests:ro" \
  -e QDRANT_HOST=vectorstore \
  -e QDRANT_PORT=6333 \
  -e QDRANT_COLLECTION=embeddings \
  --entrypoint "" \
  embedding \
  bash -c "python /app/tests/validate_e2e_flow.py" || { echo "❌ E2E validation failed"; exit 1; }
echo "✓ End-to-end validation passed"

# Health checks
echo "Testing service endpoints..."
for endpoint in "http://localhost:8080/health" "http://localhost:8080/reporting/health" "http://localhost:8080/ui/" "http://localhost:8080/grafana/" "http://localhost:9090/-/healthy" "http://localhost:3100/ready"; do
  echo "  Testing $endpoint..."
  curl -f "$endpoint" > /dev/null 2>&1 || { echo "❌ $endpoint failed"; exit 1; }
done
echo "✓ All endpoints healthy"

# Cleanup
echo "Cleaning up services..."
docker compose down || true

echo "✅ Docker Compose Workflow completed successfully"
```

Windows (PowerShell):

```powershell
$ErrorActionPreference = "Stop"
$WarningPreference = "SilentlyContinue"

trap {
  Write-Host "❌ Workflow failed at line $($_.InvocationInfo.ScriptLineNumber)"
  exit 1
}

Write-Host "=== Docker Compose Workflow (Local) ===" -ForegroundColor Cyan

# Clean up
Write-Host "Cleaning up existing containers and volumes..."
docker compose down -v 2>$null || $true
docker container prune -f 2>$null || $true

# Validate config
Write-Host "Validating docker-compose configuration..."
docker compose config > $null

# Build
Write-Host "Building all services in parallel..."
docker compose build --parallel

# Infrastructure Services
Write-Host "Starting infrastructure services..."
$infra = @('documentdb','messagebus','vectorstore','ollama','monitoring','pushgateway','loki','grafana','promtail')
foreach ($svc in $infra) {
  Write-Host "  Starting $svc..."
  docker compose up -d $svc
  $maxWait = 60
  $elapsed = 0
  while ($elapsed -lt $maxWait) {
    if ($svc -eq 'loki') {
      $status = docker compose ps loki --format '{{.Status}}'
      if ($status -match 'Up') { break }
    } else {
      $status = docker compose ps $svc --format '{{.Status}}'
      if ($status -match '\(healthy\)') { break }
    }
    Start-Sleep -Seconds 3
    $elapsed += 3
  }
  if ($elapsed -ge $maxWait) {
    Write-Host "❌ $svc failed to become healthy" -ForegroundColor Red
    docker compose logs $svc --tail=50
    exit 1
  }
}
Write-Host "✓ Infrastructure services healthy" -ForegroundColor Green

# Validators
Write-Host "Running validators..."
$validators = @('db-init','db-validate','vectorstore-validate','ollama-validate')
foreach ($validator in $validators) {
  Write-Host "  Running $validator..."
  docker compose run --rm $validator
}
Write-Host "✓ Validators passed" -ForegroundColor Green

# Application Services
Write-Host "Starting application services..."
$services = @('parsing','chunking','embedding','orchestrator','summarization','reporting','ui')
foreach ($svc in $services) {
  Write-Host "  Starting $svc..."
  docker compose up -d $svc
  $maxWait = 120
  $elapsed = 0
  while ($elapsed -lt $maxWait) {
    $status = docker compose ps $svc --format '{{.Status}}'
    if ($status -match '\(healthy\)') { break }
    Start-Sleep -Seconds 3
    $elapsed += 3
  }
  if ($elapsed -ge $maxWait) {
    Write-Host "❌ $svc failed to become healthy" -ForegroundColor Red
    docker compose logs $svc --tail=50
    exit 1
  }
}
Write-Host "✓ Application services healthy" -ForegroundColor Green

# Ingestion
Write-Host "Starting ingestion service..."
docker compose up -d ingestion
$maxWait = 120
$elapsed = 0
while ($elapsed -lt $maxWait) {
  $status = docker compose ps ingestion --format '{{.Status}}'
  if ($status -match '\(healthy\)') { break }
  Write-Host "Waiting for ingestion service..."
  Start-Sleep -Seconds 3
  $elapsed += 3
}
if ($elapsed -ge $maxWait) {
  Write-Host "❌ ingestion failed to become healthy" -ForegroundColor Red
  docker compose logs ingestion --tail=50
  exit 1
}
Write-Host "✓ Ingestion service healthy" -ForegroundColor Green

Write-Host "Copying test mailbox into ingestion container..."
$ingestion = docker compose ps -q ingestion
if (-not $ingestion) { Write-Host "❌ ingestion container not running" -ForegroundColor Red; exit 1 }
docker exec $ingestion mkdir -p /tmp/test-mailbox
docker cp tests/fixtures/mailbox_sample/test-archive.mbox "$ingestion`:/tmp/test-mailbox/test-archive.mbox"
Write-Host "✓ Test mailbox copied" -ForegroundColor Green

Write-Host "Creating ingestion source via REST API..."
$payload = '{"name":"test-mailbox","source_type":"local","url":"/tmp/test-mailbox/test-archive.mbox","enabled":true}'
$maxAttempts = 5
$attempt = 1
while ($attempt -le $maxAttempts) {
  curl -f -X POST http://localhost:8080/ingestion/api/sources -H "Content-Type: application/json" -d $payload
  if ($LASTEXITCODE -eq 0) { Write-Host "✓ Ingestion source created (attempt $attempt/$maxAttempts)" -ForegroundColor Green; break }
  Write-Host "Attempt $attempt/$maxAttempts: Failed to create source, retrying..." -ForegroundColor Yellow
  Start-Sleep -Seconds 2
  $attempt += 1
}
if ($attempt -gt $maxAttempts) {
  Write-Host "❌ Failed to create ingestion source after $maxAttempts attempts" -ForegroundColor Red
  docker compose logs ingestion --tail=50
  exit 1
}

Write-Host "Triggering ingestion via REST API..."
$attempt = 1
while ($attempt -le $maxAttempts) {
  curl -f -X POST http://localhost:8080/ingestion/api/sources/test-mailbox/trigger
  if ($LASTEXITCODE -eq 0) { Write-Host "✓ Ingestion triggered successfully (attempt $attempt/$maxAttempts)" -ForegroundColor Green; break }
  Write-Host "Attempt $attempt/$maxAttempts: Failed to trigger ingestion, retrying..." -ForegroundColor Yellow
  Start-Sleep -Seconds 2
  $attempt += 1
}
if ($attempt -gt $maxAttempts) {
  Write-Host "❌ Failed to trigger ingestion after $maxAttempts attempts" -ForegroundColor Red
  docker compose logs ingestion --tail=50
  exit 1
}

Write-Host "Waiting for ingestion to complete..."
Start-Sleep -Seconds 10
$status = curl -s http://localhost:8080/ingestion/api/sources/test-mailbox/status
Write-Host "Ingestion status: $status"

# End-to-end validation
Write-Host "Validating end-to-end message flow..."
$mount = (Get-Location).Path + "/tests:/app/tests:ro"
docker compose run --rm -v $mount `
  -e QDRANT_HOST=vectorstore `
  -e QDRANT_PORT=6333 `
  -e QDRANT_COLLECTION=embeddings `
  --entrypoint "" `
  embedding `
  bash -c "python /app/tests/validate_e2e_flow.py"
Write-Host "✓ End-to-end validation passed" -ForegroundColor Green

# Health checks
Write-Host "Testing service endpoints..."
$endpoints = @(
  "http://localhost:8080/health",
  "http://localhost:8080/reporting/health",
  "http://localhost:8080/ui/",
  "http://localhost:8080/grafana/",
  "http://localhost:9090/-/healthy",
  "http://localhost:3100/ready"
)
foreach ($endpoint in $endpoints) {
  Write-Host "  Testing $endpoint..."
  try {
    Invoke-WebRequest -UseBasicParsing -Uri $endpoint > $null
  } catch {
    Write-Host "❌ $endpoint failed" -ForegroundColor Red
    exit 1
  }
}
Write-Host "✓ All endpoints healthy" -ForegroundColor Green

# Cleanup
Write-Host "Cleaning up services..."
docker compose down 2>$null || $true

Write-Host "✅ Docker Compose Workflow completed successfully" -ForegroundColor Green
```

Example usage:
- `"run the docker compose workflow"` → executes full end-to-end workflow locally, stops on first error

#### "review PR <number>"

Meaning: Review an open pull request without changing code. Summarize what the PR does, list any issues found, and highlight actionable suggestions. Do not push commits.

Process:
- Fetch PR details and diffs using GitHub MCP.
- Read review comments and CI status.
- Provide a concise review summary: scope, risk, correctness, style, docs/tests.
- Add non-blocking/blocking comments as needed via PR review comment, but avoid code changes.

Example usage:
- "review PR 310" → returns a summary of changes, potential issues, and suggestions, but makes no commits.

#### "review and respond to PR <number>"

Meaning: Actively address review feedback on the specified PR. Apply straightforward documentation or configuration updates, push changes to the PR branch, and reply inline to review comments explaining the fixes. Ask for clarification if a comment is ambiguous.

Process:
1) Retrieve PR review comments and files using GitHub MCP.
2) For each actionable comment:
  - Update the relevant files (docs/config/scripts), keeping changes minimal and scoped.
  - Commit with a descriptive message referencing the change.
  - Push to the PR branch.
  - Reply to the specific review thread describing what changed.
3) If a comment is unclear or requires design input, reply asking for clarification rather than guessing.

Notes:
- Prefer not to modify application logic unless explicitly requested.
- Keep edits surgical and reference exact lines/sections fixed.
- Do not mark threads resolved unless requested by a maintainer.

Example usage:
- "review and respond to PR 310" → fetches comments, applies agreed doc fixes, pushes, and posts replies.

#### "file an issue for this"

Meaning: Create a GitHub issue for a problem or task discussed in the current conversation. Examine the recent conversation context to determine what the user is referring to. If the issue is ambiguous or unclear, ask the user for clarification before filing.

**Process:**

1. **Analyze recent conversation** to identify:
   - What problem or task the user is describing
   - Key details: error messages, reproduction steps, affected components
   - Suggested labels or assignees (if mentioned)

2. **Ask for clarification if needed**:
   - If multiple issues are discussed, ask which one to file
   - If details are missing (title, description), ask the user to provide them
   - If the problem is vague, ask for more specifics

3. **Create the issue using GitHub MCP** with:
   - Clear, descriptive title
   - Detailed description including context from the conversation
   - Relevant labels (e.g., `bug`, `enhancement`, `documentation`, `testing`)
   - Optional: assign to specific team members if applicable

**Examples:**

- User: "file an issue for this" (after discussing a failing test)
  → Ask: "Should I file this as a bug for the failing test in the orchestrator service?"
  → Create issue titled: "orchestrator: test_message_handling fails intermittently"

- User: "file an issue for the summarization API mismatch"
  → Recognized from context: `EventPublisher.publish(..., message=...)` vs expected `event=...`
  → Create issue titled: "summarization: Fix API mismatch in publish() method call"

- User: "file an issue for this" (without clear context)
  → Ask: "What issue would you like me to file? Please provide a title and description."

## CI & Testing Overview

- **PRs Required**: Direct pushes to `main` are blocked. Open a PR; required check includes the `Test Docker Compose` job.
- **Unified CI**: [unified-ci.yml](.github/workflows/unified-ci.yml) orchestrates unit and integration tests for **all services and adapters** using reusable workflows.
  - **Service Tests**: Via [service-reusable-unit-test-ci.yml](.github/workflows/service-reusable-unit-test-ci.yml)
    - Runs `pytest` for unit and integration together, generates coverage and JUnit, and reports via `dorny/test-reporter`.
    - `flake8`, `pylint`, and `bandit` checks run per service.
    - Builds each service Dockerfile using Buildx (no push); summarized with a gated `summary` job.
  - **Adapter Unit Tests**: Via [adapter-reusable-unit-test-ci.yml](.github/workflows/adapter-reusable-unit-test-ci.yml)
    - Runs `pytest` with `-m "not integration"`, uploads JUnit and coverage (`lcov`, `html`), and reports via `dorny/test-reporter`.
  - **Adapter Integration Tests**: Via [adapter-reusable-integration-ci.yml](.github/workflows/adapter-reusable-integration-ci.yml)
    - Spins services (MongoDB, RabbitMQ) and optional rsync fixtures; runs `pytest -m integration` with coverage and artifacts.
  - **Vectorstore Integration**: Via [adapter-reusable-vectorstore-integration-ci.yml](.github/workflows/adapter-reusable-vectorstore-integration-ci.yml)
    - Provisions Qdrant and runs `pytest -m integration` for vectorstore adapters.
  - **Coverage**: Coveralls uploads per job with `parallel: true`; a **single** `coverage-summary` job finalizes all coverage on `main` with `parallel-finished: true`.
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
docker compose up -d parsing chunking embedding orchestrator summarization reporting ui
docker compose run --rm ingestion
# quick health checks
curl -f http://localhost:8080/      # reporting
curl -f http://localhost:8084/      # web ui
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
docker compose up -d parsing chunking embedding orchestrator summarization reporting ui
docker compose run --rm ingestion
# quick health checks
Invoke-WebRequest -UseBasicParsing http://localhost:8080/ | Out-Null
Invoke-WebRequest -UseBasicParsing http://localhost:8084/ | Out-Null
Invoke-WebRequest -UseBasicParsing http://localhost:3000/api/health | Out-Null
Invoke-WebRequest -UseBasicParsing http://localhost:9090/-/healthy | Out-Null
Invoke-WebRequest -UseBasicParsing http://localhost:3100/ready | Out-Null
docker compose down
```

Notes:
- Prefer running per-adapter/service tests before system tests for faster feedback.
- Match `pytest -m integration` for integration-only runs; use `-m "not integration"` for unit.
- Coverage artifacts are written to `coverage.lcov` and `htmlcov/` by convention.
