# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#!
.SYNOPSIS
Exports Azure Container Apps logs from Blob Storage (Diagnostic Settings) for RCA.

.DESCRIPTION
This repo's Azure templates archive Container Apps logs to Blob Storage via Diagnostic Settings
(NDJSON, typically one JSON object per line).

By default, Azure Monitor writes to the `insights-logs-containerappconsolelogs` container.
Use `-ContainerName insights-logs-containerappsystemlogs` for system logs.

This script:
- Lists blobs in the logs container (optionally filtered by prefix)
- Filters by lookback window (ISO 8601 duration like PT6H / P1D)
- Downloads matching blobs to a local folder
- Optionally runs the Drain3-based miner to produce an RCA-friendly report:
  - JSON report (templates + samples)
  - Markdown summary focused on WARNING/ERROR

Prereqs:
- Azure CLI installed (`az`)
- Logged in (`az login`) and subscription set if needed
- RBAC to read blobs (e.g., Storage Blob Data Reader)

.EXAMPLE
./scripts/export_blob_logs_rca.ps1 -StorageAccountName mystorage -Timespan PT6H

.EXAMPLE
./scripts/export_blob_logs_rca.ps1 -StorageAccountName mystorage -Timespan P1D -Prefix "resourceId=/SUBSCRIPTIONS/.../MICROSOFT.APP/containerapps/" -OutDir logs/azure/mystorage/rca

.EXAMPLE
# Download only (skip mining)
./scripts/export_blob_logs_rca.ps1 -StorageAccountName mystorage -Timespan PT12H -SkipMining
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$StorageAccountName,

    [Parameter(Mandatory = $false)]
    [string]$ContainerName = "insights-logs-containerappconsolelogs",

    [Parameter(Mandatory = $false)]
    [string]$Prefix = "",

    [Parameter(Mandatory = $false)]
    [string]$Timespan = "PT6H",

    [Parameter(Mandatory = $false)]
    [string]$OutDir,

    [Parameter(Mandatory = $false)]
    [int]$MaxBlobs = 2000,

    [Parameter(Mandatory = $false)]
    [switch]$SkipDownload,

    [Parameter(Mandatory = $false)]
    [switch]$SkipMining,

    [Parameter(Mandatory = $false)]
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

function Get-RequiredCommand([string]$Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "Required command not found: $Name"
    }
    return $cmd
}

function ConvertTo-TimeSpan([string]$Value) {
    try {
        return [System.Xml.XmlConvert]::ToTimeSpan($Value)
    } catch {
        throw "Invalid -Timespan '$Value'. Expected ISO 8601 duration like PT6H, P1D."
    }
}

function Resolve-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot ".."))
}

function Resolve-PythonExe {
    param(
        [string]$Explicit,
        [string]$RepoRoot
    )

    if ($Explicit -and $Explicit.Trim()) {
        return $Explicit
    }

    $venvPython = Join-Path $RepoRoot ".venv/Scripts/python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }

    return "python"
}

if (-not $PSBoundParameters.ContainsKey('OutDir')) {
    $OutDir = "logs/azure/$StorageAccountName/rca"
}

Get-RequiredCommand "az" | Out-Null

$repoRoot = (Resolve-RepoRoot).Path
$python = Resolve-PythonExe -Explicit $PythonExe -RepoRoot $repoRoot

$duration = ConvertTo-TimeSpan $Timespan
$cutoffUtc = (Get-Date).ToUniversalTime().Add(-$duration)

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$rawDir = Join-Path $OutDir "raw"

$manifestPath = Join-Path $OutDir "blobs.json"

Write-Host "Blob RCA export" -ForegroundColor Cyan
Write-Host "  Storage account: $StorageAccountName" -ForegroundColor DarkGray
Write-Host "  Container:       $ContainerName" -ForegroundColor DarkGray
Write-Host "  Prefix:          $Prefix" -ForegroundColor DarkGray
Write-Host "  Lookback:        $Timespan (cutoff UTC: $cutoffUtc)" -ForegroundColor DarkGray
Write-Host "  Output dir:      $OutDir" -ForegroundColor DarkGray

# 1) List blobs
$listArgs = @(
    "storage", "blob", "list",
    "--account-name", $StorageAccountName,
    "--container-name", $ContainerName,
    "--auth-mode", "login",
    "-o", "json"
)
if ($Prefix -and $Prefix.Trim()) {
    $listArgs += @("--prefix", $Prefix)
}

Write-Host "Listing blobs..." -ForegroundColor Cyan
$blobsJson = az @listArgs 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Failed to list blobs. Azure CLI output:`n$blobsJson"
}

$blobs = @()
if ($blobsJson -and $blobsJson.Trim()) {
    $blobs = $blobsJson | ConvertFrom-Json
}

# 2) Filter blobs by lastModified
$selected = @(
    $blobs |
        Where-Object { $_.properties -and $_.properties.lastModified } |
        ForEach-Object {
            $lm = [DateTime]::Parse($_.properties.lastModified).ToUniversalTime()
            $_ | Add-Member -NotePropertyName lastModifiedUtc -NotePropertyValue $lm -PassThru
        } |
        Where-Object { $_.lastModifiedUtc -ge $cutoffUtc } |
        Sort-Object lastModifiedUtc -Descending
)

if (-not $selected -or $selected.Count -eq 0) {
    Write-Host "No blobs found newer than cutoff. Nothing to do." -ForegroundColor Yellow
    $blobsJson | Out-File -Encoding utf8 $manifestPath
    exit 0
}

if ($selected.Count -gt $MaxBlobs) {
    Write-Host "Found $($selected.Count) blobs; truncating to MaxBlobs=$MaxBlobs." -ForegroundColor Yellow
    $selected = $selected | Select-Object -First $MaxBlobs
}

$selected | ConvertTo-Json -Depth 6 | Out-File -Encoding utf8 $manifestPath
Write-Host "Selected $($selected.Count) blob(s). Manifest: $manifestPath" -ForegroundColor DarkGray

# 3) Download
if (-not $SkipDownload) {
    # Clean previous raw data to avoid mixing stale logs from previous runs
    if (Test-Path $rawDir) {
        Write-Host "Cleaning previous raw data: $rawDir" -ForegroundColor Yellow
        Remove-Item -Recurse -Force $rawDir
    }
    New-Item -ItemType Directory -Force -Path $rawDir | Out-Null

    Write-Host "Downloading blobs..." -ForegroundColor Cyan

    foreach ($blob in $selected) {
        $blobName = [string]$blob.name
        if (-not $blobName) {
            continue
        }

        $relativePath = $blobName -replace "/", "\\"
        $localPath = Join-Path $rawDir $relativePath

        $localDir = Split-Path -Parent $localPath
        if ($localDir) {
            New-Item -ItemType Directory -Force -Path $localDir | Out-Null
        }

        $downloadArgs = @(
            "storage", "blob", "download",
            "--account-name", $StorageAccountName,
            "--container-name", $ContainerName,
            "--name", $blobName,
            "--file", $localPath,
            "--auth-mode", "login",
            "--overwrite", "true",
            "--only-show-errors",
            "-o", "none"
        )

        az @downloadArgs 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to download blob: $blobName"
        }
    }
}

# 4) Optional mining
if (-not $SkipMining) {
    $reportPath = Join-Path $OutDir "rca_mined.json"
    $markdownPath = Join-Path $OutDir "rca_mined_errors_warnings.md"

    if (-not (Test-Path $rawDir)) {
        throw "Raw directory not found: $rawDir. Use without -SkipDownload to download files first."
    }

    $downloadedFiles = Get-ChildItem -Path $rawDir -File -Recurse
    if (-not $downloadedFiles -or $downloadedFiles.Count -eq 0) {
        throw "No downloaded files found under: $rawDir"
    }

    Write-Host "Mining downloaded logs (Drain3)..." -ForegroundColor Cyan
    Write-Host "  Python:  $python" -ForegroundColor DarkGray
    Write-Host "  Files:   $($downloadedFiles.Count)" -ForegroundColor DarkGray
    Write-Host "  Output:  $reportPath" -ForegroundColor DarkGray
    Write-Host "  MD:      $markdownPath" -ForegroundColor DarkGray

    # Stream all lines to the miner (stdin mode).
    # NOTE: --input is intentionally omitted; the tool reads from stdin.
    Push-Location $repoRoot
    try {
        Get-Content -Path $downloadedFiles.FullName | & $python -m scripts.log_mining --format azure-diagnostics --group-by service --output $reportPath --output-markdown $markdownPath
    } finally {
        Pop-Location
    }

    if ($LASTEXITCODE -ne 0) {
        throw "log_mining failed with exit code $LASTEXITCODE"
    }

    Write-Host "Mining complete." -ForegroundColor Green
}

Write-Host "Done." -ForegroundColor Green
Write-Host "Raw logs:  $rawDir" -ForegroundColor DarkGray
Write-Host "Manifest:  $manifestPath" -ForegroundColor DarkGray
