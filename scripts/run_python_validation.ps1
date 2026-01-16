# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#!
.SYNOPSIS
  Runs the checks from .github/workflows/python-validation.yml on Windows.

.DESCRIPTION
  Mirrors the workflow’s two jobs:
  - static-analysis (ruff, pylint critical set, mypy info, pyright info, pyright gates)
  - import-smoke-tests (pytest tests/test_imports.py)

  Notes:
  - Ruff, MyPy, and the non-gating Pyright runs are informational in CI; this
    script will not fail on them.
  - Pylint critical checks, Pyright gates, and import smoke tests are treated as
    gating (non-zero exit code).
  - Some service requirements include Linux-only packages like uvloop; this
    script filters those lines on Windows for best-effort installs.

.PARAMETER SkipInstalls
  Skip dependency installation steps.

.PARAMETER SkipImportSmoke
  Skip the import smoke test job.

.PARAMETER SkipStatic
  Skip the static-analysis job.
#>

Param(
  [switch]$SkipInstalls,
  [switch]$SkipImportSmoke,
  [switch]$SkipStatic
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot

function Write-Step([string]$msg) {
  Write-Host "`n==> $msg" -ForegroundColor Yellow
}

function Ensure-Command([string]$name, [string]$installHint) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "$name not found. $installHint"
  }
}

function Ensure-Pyright {
  if (Get-Command pyright -ErrorAction SilentlyContinue) {
    return
  }

  Ensure-Command node 'Install Node.js or ensure node is on PATH.'
  Ensure-Command npm 'Install Node.js (includes npm) or ensure npm is on PATH.'

  Write-Step 'Installing pyright via npm (global)'
  npm install -g pyright | Out-Host
}

function Install-RequirementsSafely([string]$requirementsPath, [switch]$BestEffort) {
  if (-not (Test-Path $requirementsPath)) {
    return
  }

  $temp = Join-Path $env:TEMP ("requirements.filtered.{0}.txt" -f ([Guid]::NewGuid().ToString('N')))

  try {
    $lines = Get-Content $requirementsPath -ErrorAction Stop

    # Filter Linux-only deps that break Windows local validation.
    $filtered = $lines | Where-Object {
      $l = $_.Trim()
      if ($l -eq '') { return $true }
      if ($l.StartsWith('#')) { return $true }
      if ($l -match '^(uvloop)(\b|==|>=|<=|~=|\[)') { return $false }
      return $true
    }

    Set-Content -Path $temp -Value $filtered -Encoding utf8

    if ($BestEffort) {
      try {
        pip install -r $temp | Out-Host
      } catch {
        Write-Host "WARNING: pip install failed for $requirementsPath (best-effort): $_" -ForegroundColor DarkYellow
      }
    } else {
      pip install -r $temp | Out-Host
    }
  }
  finally {
    if (Test-Path $temp) { Remove-Item $temp -Force -ErrorAction SilentlyContinue }
  }
}

function Install-Adapters {
  Write-Step 'Installing all adapters (editable)'
  python adapters/scripts/install_adapters.py \
    copilot_auth \
    copilot_chunking \
    copilot_config \
    copilot_consensus \
    copilot_embedding \
    copilot_message_bus \
    copilot_logging \
    copilot_metrics \
    copilot_archive_fetcher \
    copilot_archive_store \
    copilot_error_reporting \
    copilot_schema_validation \
    copilot_secrets \
    copilot_storage \
    copilot_summarization \
    copilot_vectorstore \
    copilot_draft_diff \
    copilot_startup
}

function Run-Ruff {
  if (-not (Get-Command ruff -ErrorAction SilentlyContinue)) {
    Write-Host 'ruff not found; skipping ruff (install via requirements-dev.txt).' -ForegroundColor DarkYellow
    return
  }

  Write-Step 'Ruff - Fast Python Linter (informational)'
  ruff check . --output-format=github
  Write-Host ("Ruff exit code: {0}" -f $LASTEXITCODE) -ForegroundColor Cyan

  Write-Step 'Ruff - Check Import Sorting (informational)'
  ruff check . --select I --output-format=github
  Write-Host ("Ruff import exit code: {0}" -f $LASTEXITCODE) -ForegroundColor Cyan
}

function Run-PylintCritical {
  Ensure-Command pylint 'Install pylint (e.g., pip install -r requirements-dev.txt).'

  Write-Step 'Pylint - Attribute and Member Checking (gating)'
  $pylintErrors = 0

  # Adapters
  Get-ChildItem -Directory -Path 'adapters' -Filter 'copilot_*' | ForEach-Object {
    $adapterDir = $_.FullName
    $adapterName = $_.Name
    $pkgDir = Join-Path $adapterDir $adapterName
    if (Test-Path $pkgDir) {
      Write-Host "Checking $adapterName..." -ForegroundColor Cyan
      pylint $pkgDir \
        --disable=all \
        --enable=E0602,E1101,E0611,E1102,E1120,E1121 \
        --output-format=colorized

      if ($LASTEXITCODE -ne 0) {
        $pylintErrors += 1
        Write-Host "WARNING: Pylint found issues in $adapterName" -ForegroundColor DarkYellow
      }
    }
  }

  # Services
  $services = @('auth','chunking','embedding','ingestion','orchestrator','parsing','reporting','summarization')
  foreach ($service in $services) {
    $targets = @()
    if (Test-Path "$service/app") { $targets += "$service/app" }
    if (Test-Path "$service/main.py") { $targets += "$service/main.py" }

    if ($targets.Count -gt 0) {
      Write-Host "Checking $service..." -ForegroundColor Cyan
      pylint @targets \
        --disable=all \
        --enable=E0602,E1101,E0611,E1102,E1120,E1121 \
        --output-format=colorized

      if ($LASTEXITCODE -ne 0) {
        $pylintErrors += 1
        Write-Host "WARNING: Pylint found issues in $service" -ForegroundColor DarkYellow
      }
    }
  }

  if ($pylintErrors -gt 0) {
    throw "Pylint found critical errors in $pylintErrors module(s)."
  }
}

function Run-MyPy {
  if (-not (Get-Command mypy -ErrorAction SilentlyContinue)) {
    Write-Host 'mypy not found; skipping mypy (install via requirements-dev.txt).' -ForegroundColor DarkYellow
    return
  }

  Write-Step 'MyPy - Static Type Checking (informational)'
  $errors = 0

  Get-ChildItem -Directory -Path 'adapters' -Filter 'copilot_*' | ForEach-Object {
    $adapterDir = $_.FullName
    $adapterName = $_.Name
    $pkgDir = Join-Path $adapterDir $adapterName
    if (Test-Path $pkgDir) {
      Write-Host "Type checking $adapterName..." -ForegroundColor Cyan
      mypy $pkgDir --no-error-summary
      if ($LASTEXITCODE -ne 0) { $errors += 1 }
    }
  }

  $services = @('auth','chunking','embedding','ingestion','orchestrator','parsing','reporting','summarization')
  foreach ($service in $services) {
    $targets = @()
    if (Test-Path "$service/app") { $targets += "$service/app" }
    if (Test-Path "$service/main.py") { $targets += "$service/main.py" }
    if ($targets.Count -gt 0) {
      Write-Host "Type checking $service..." -ForegroundColor Cyan
      mypy @targets --no-error-summary
      if ($LASTEXITCODE -ne 0) { $errors += 1 }
    }
  }

  if ($errors -gt 0) {
    Write-Host "WARNING: MyPy found issues in $errors module(s)." -ForegroundColor DarkYellow
  }
}

function Run-PyrightInformational {
  Ensure-Pyright

  Write-Step 'Pyright - Strict Type Checking (informational)'
  $errors = 0

  Get-ChildItem -Directory -Path 'adapters' -Filter 'copilot_*' | ForEach-Object {
    $adapterDir = $_.FullName
    $adapterName = $_.Name
    $pkgDir = Join-Path $adapterDir $adapterName
    if (Test-Path $pkgDir) {
      Write-Host "Type checking $adapterName..." -ForegroundColor Cyan
      pyright $pkgDir --level error
      if ($LASTEXITCODE -ne 0) { $errors += 1 }
    }
  }

  $services = @('auth','chunking','embedding','ingestion','orchestrator','parsing','reporting','summarization')
  foreach ($service in $services) {
    $targets = @()
    if (Test-Path "$service/app") { $targets += "$service/app" }
    if (Test-Path "$service/main.py") { $targets += "$service/main.py" }
    if ($targets.Count -gt 0) {
      Write-Host "Type checking $service..." -ForegroundColor Cyan
      pyright @targets --level error
      if ($LASTEXITCODE -ne 0) { $errors += 1 }
    }
  }

  if ($errors -gt 0) {
    Write-Host "WARNING: Pyright found issues in $errors module(s)." -ForegroundColor DarkYellow
  }
}

function Run-PyrightGates {
  Ensure-Pyright
  Write-Step 'Pyright (gating) - typed config safety (gating)'
  & "$repoRoot/scripts/run_pyright_gates.ps1"
}

function Run-ImportSmokeTests {
  Write-Step 'Import Smoke Tests (gating)'

  pip install pytest pytest-timeout | Out-Host

  Install-Adapters

  # Minimal service deps (best-effort, like CI)
  $services = @('auth','chunking','embedding','ingestion','orchestrator','parsing','reporting','summarization')
  foreach ($svc in $services) {
    $req = "$svc/requirements.txt"
    if (Test-Path $req) {
      Write-Host "Installing dependencies for $svc (best-effort)..." -ForegroundColor Cyan
      Install-RequirementsSafely -requirementsPath $req -BestEffort
    }
  }

  pytest tests/test_imports.py -v --tb=short --timeout=60 --junit-xml=test-results.xml
}

try {
  if (-not $SkipInstalls) {
    Write-Step 'Installing validation dependencies (requirements-dev.txt)'
    python -m pip install --upgrade pip | Out-Host
    pip install -r requirements-dev.txt | Out-Host

    # CI installs service requirements for pyright; do the same here.
    $servicesForPyright = @('ingestion','auth','chunking','embedding','orchestrator','parsing','reporting','summarization')
    foreach ($svc in $servicesForPyright) {
      $req = "$svc/requirements.txt"
      if (Test-Path $req) {
        Write-Host "Installing dependencies for $svc (for pyright)..." -ForegroundColor Cyan
        Install-RequirementsSafely -requirementsPath $req
      }
    }

    Install-Adapters
  }

  if (-not $SkipStatic) {
    Run-Ruff
    Run-PylintCritical
    Run-MyPy
    Run-PyrightInformational
    Run-PyrightGates
  }

  if (-not $SkipImportSmoke) {
    Run-ImportSmokeTests
  }

  Write-Host "`nAll gating checks passed." -ForegroundColor Green
  exit 0
}
catch {
  Write-Host "`nFAILED: $_" -ForegroundColor Red
  exit 1
}
finally {
  Pop-Location
}
