# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#
.SYNOPSIS
    Upload ingestion sources from JSON config to document store

.DESCRIPTION
    Reads ingestion/config.test.json and uploads sources to the MongoDB document store
    via the ingestion service container.

.EXAMPLE
    .\upload_ingestion_config.ps1
#>

Write-Host "`nUploading ingestion sources to document store..." -ForegroundColor Cyan

# Upload sources to document store from JSON
$jsonPath = Join-Path (Get-Location) "ingestion/config.test.json"
if (-not (Test-Path $jsonPath)) {
    Write-Host "✗ JSON config not found at $jsonPath" -ForegroundColor Red
    exit 1
}

Write-Host "  Using JSON config: $jsonPath" -ForegroundColor Cyan

# Prepare volume mount for JSON into container path
# Mount to /app/config.test.json since upload script expects this path
$mountArg = "${jsonPath}:/app/config.test.json:ro"

# Run the uploader inside the ingestion container so it uses adapters/env
Write-Host "  Running upload_ingestion_sources.py..." -ForegroundColor Yellow
docker compose run --rm -v "$mountArg" ingestion python upload_ingestion_sources.py /app/config.test.json

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Failed to upload sources to document store" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Sources uploaded to document store" -ForegroundColor Green
