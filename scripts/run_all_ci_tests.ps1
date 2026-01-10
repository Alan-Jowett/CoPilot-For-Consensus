# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#
.SYNOPSIS
    Runs all unit and integration tests for services and adapters in the repository.

.DESCRIPTION
    This script installs all adapter packages in editable mode and then runs the test suites
    for all services and adapters. The tests are run using pytest, and the set of tests to run
    can be filtered using the Marker parameter. By default, only unit tests (not marked as integration)
    are run. This script is intended for use in CI pipelines or for local validation of all code.

.PARAMETER Marker
    A pytest marker expression to filter which tests are run. By default, "not integration" is used,
    which runs only unit tests. To run integration tests, set Marker to "integration". You can use
    any valid pytest -m expression.

.EXAMPLE
    # Run all unit tests (default)
    ./run_all_ci_tests.ps1

.EXAMPLE
    # Run only integration tests
    ./run_all_ci_tests.ps1 -Marker integration

.EXAMPLE
    # Run tests marked as "slow"
    ./run_all_ci_tests.ps1 -Marker slow
#>
Param(
    [string]$Marker = "not integration"
)

$ErrorActionPreference = 'Stop'
# Script lives under /scripts; move one level up to repo root for relative paths
$root = Split-Path -Parent $PSScriptRoot

$services = @(
    @{ Name = 'chunking'; Path = 'chunking' },
    @{ Name = 'embedding'; Path = 'embedding' },
    @{ Name = 'ingestion'; Path = 'ingestion' },
    @{ Name = 'orchestrator'; Path = 'orchestrator' },
    @{ Name = 'parsing'; Path = 'parsing' },
    @{ Name = 'reporting'; Path = 'reporting' },
    @{ Name = 'summarization'; Path = 'summarization' }
)

$adapters = @(
    @{ Name = 'copilot_archive_fetcher'; Path = 'adapters/copilot_archive_fetcher' },
    @{ Name = 'copilot_auth'; Path = 'adapters/copilot_auth' },
    @{ Name = 'copilot_chunking'; Path = 'adapters/copilot_chunking' },
    @{ Name = 'copilot_config'; Path = 'adapters/copilot_config' },
    @{ Name = 'copilot_consensus'; Path = 'adapters/copilot_consensus' },
    @{ Name = 'copilot_draft_diff'; Path = 'adapters/copilot_draft_diff' },
    @{ Name = 'copilot_embedding'; Path = 'adapters/copilot_embedding' },
    @{ Name = 'copilot_message_bus'; Path = 'adapters/copilot_message_bus' },
    @{ Name = 'copilot_logging'; Path = 'adapters/copilot_logging' },
    @{ Name = 'copilot_metrics'; Path = 'adapters/copilot_metrics' },
    @{ Name = 'copilot_error_reporting'; Path = 'adapters/copilot_error_reporting' },
    @{ Name = 'copilot_schema_validation'; Path = 'adapters/copilot_schema_validation' },
    @{ Name = 'copilot_storage'; Path = 'adapters/copilot_storage' },
    @{ Name = 'copilot_summarization'; Path = 'adapters/copilot_summarization' },
    @{ Name = 'copilot_vectorstore'; Path = 'adapters/copilot_vectorstore' }
)

$adapterDeps = @{
    'copilot_vectorstore' = @('faiss-cpu', 'qdrant-client')
}

$installResults = @()

# Install adapter packages in editable mode before running service tests
Write-Host '==> Installing adapter packages (editable)' -ForegroundColor Yellow
foreach ($adapter in $adapters) {
    $pkgPath = Join-Path $root $adapter.Path
    Write-Host "Installing $($adapter.Name) from $pkgPath" -ForegroundColor Cyan
    Push-Location $pkgPath
    try {
        if ($adapterDeps.ContainsKey($adapter.Name)) {
            $deps = $adapterDeps[$adapter.Name]
            Write-Host "Installing extra deps for $($adapter.Name): $($deps -join ', ')" -ForegroundColor DarkCyan
            & python -m pip install $deps
            if ($LASTEXITCODE -ne 0) { throw "Dependency install failed for $($adapter.Name)" }
        }

        & python -m pip install -e .
        & python -m pip install pytest pytest-cov
        & python -m pip install pytest-timeout
        $installExit = $LASTEXITCODE
    } catch {
        Write-Host "Error installing $($adapter.Name): $_" -ForegroundColor Red
        $installExit = 1
    } finally {
        Pop-Location
    }

    $installResults += [pscustomobject]@{
        Name = $adapter.Name
        Path = $adapter.Path
        ExitCode = $installExit
    }

    if ($installExit -ne 0) {
        Write-Host ("Install failed for {0} with exit code {1}." -f $adapter.Name, $installExit) -ForegroundColor Red
        Write-Host "Check pip output above for details or try installing manually with:" -ForegroundColor Yellow
        Write-Host ("    pip install -e ./{0}" -f $adapter.Path) -ForegroundColor Yellow
        Write-Host 'Aborting test run because adapter installation failed.' -ForegroundColor Red
        exit 1
    }
}
Write-Host 'Adapter installation complete.' -ForegroundColor Green
Write-Host ''

$targets = $services + $adapters
$pytestArgs = @()
if ($Marker -and $Marker.Trim().Length -gt 0) {
    $pytestArgs += '-m'
    $pytestArgs += $Marker
}

$results = @()

foreach ($target in $targets) {
    $fullPath = Join-Path $root $target.Path
    Write-Host "==> Running $($target.Name) tests in $fullPath" -ForegroundColor Cyan
    Push-Location $fullPath
    try {
        & python -m pytest @pytestArgs
        $exitCode = $LASTEXITCODE
    } catch {
        Write-Host "Error invoking pytest for $($target.Name): $_" -ForegroundColor Red
        $exitCode = 1
    } finally {
        Pop-Location
    }

    $results += [pscustomobject]@{
        Name = $target.Name
        Path = $target.Path
        ExitCode = $exitCode
    }

    if ($exitCode -ne 0) {
        Write-Host "Tests failed for $($target.Name)" -ForegroundColor Red
    } else {
        Write-Host "Tests passed for $($target.Name)" -ForegroundColor Green
    }

    Write-Host ''
}

Write-Host '==== Summary ====' -ForegroundColor Yellow
$results | ForEach-Object {
    $status = if ($_.ExitCode -eq 0) { 'PASS' } else { 'FAIL' }
    $color = if ($_.ExitCode -eq 0) { 'Green' } else { 'Red' }
    Write-Host ("{0,-28} {1}" -f $_.Name, $status) -ForegroundColor $color
}

$failed = $results | Where-Object { $_.ExitCode -ne 0 }
if ($failed.Count -gt 0) {
    Write-Host "One or more test runs failed." -ForegroundColor Red
    exit 1
} else {
    Write-Host "All test runs passed." -ForegroundColor Green
    exit 0
}
