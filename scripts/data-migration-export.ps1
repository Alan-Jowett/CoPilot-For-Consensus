# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#
.SYNOPSIS
    Export all data from a CoPilot-for-Consensus deployment.

.DESCRIPTION
    Exports all collections from the copilot and auth databases to JSON Lines
    files. Supports Azure Cosmos DB (MongoDB API) and standalone MongoDB
    (Docker Compose) as sources.

    See docs/operations/data-migration.md for full documentation.

.PARAMETER SourceType
    The type of source database: "cosmos" or "mongodb".

.PARAMETER ConnectionString
    MongoDB-compatible connection string. If omitted, the script derives it
    from environment variables or az CLI (for Cosmos).

.PARAMETER ResourceGroup
    Azure resource group (required when SourceType=cosmos and no ConnectionString).

.PARAMETER CosmosAccountName
    Azure Cosmos DB account name (required when SourceType=cosmos and no ConnectionString).

.PARAMETER Collections
    Comma-separated list of collections to export. Defaults to all collections.

.PARAMETER OutputDir
    Output directory. Defaults to "data-export-<timestamp>".

.PARAMETER BatchSize
    Number of documents per mongoexport batch. Default: 1000.

.PARAMETER UseRBAC
    Authenticate to Azure Cosmos DB using Azure AD / RBAC (via az login)
    instead of connection string keys. Requires the logged-in principal to
    have the "Cosmos DB Built-in Data Reader" role (for export) or
    "Cosmos DB Built-in Data Contributor" role (for import).

.EXAMPLE
    .\scripts\data-migration-export.ps1 -SourceType cosmos -ResourceGroup copilot-app-rg -CosmosAccountName copilot-cos-dev-y6f2c

.EXAMPLE
    .\scripts\data-migration-export.ps1 -SourceType cosmos -ResourceGroup copilot-app-rg -CosmosAccountName copilot-cos-dev-y6f2c -UseRBAC

.EXAMPLE
    .\scripts\data-migration-export.ps1 -SourceType mongodb

.EXAMPLE
    .\scripts\data-migration-export.ps1 -SourceType mongodb -Collections sources,archives
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("cosmos", "mongodb")]
    [string]$SourceType,

    [Parameter(Mandatory = $false)]
    [string]$ConnectionString,

    [Parameter(Mandatory = $false)]
    [string]$ResourceGroup,

    [Parameter(Mandatory = $false)]
    [string]$CosmosAccountName,

    [Parameter(Mandatory = $false)]
    [string]$Collections,

    [Parameter(Mandatory = $false)]
    [string]$OutputDir,

    [Parameter(Mandatory = $false)]
    [int]$BatchSize = 1000,

    [switch]$UseRBAC
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Database → collection mapping (mirrors collections.config.json + auth)
$DatabaseCollections = @{
    "copilot" = @("sources", "archives", "messages", "threads", "chunks", "summaries")
    "auth"    = @("user_roles")
}

# Filter collections if user specified a subset
if ($Collections) {
    $requestedCollections = $Collections -split "," | ForEach-Object { $_.Trim() }
    $filteredDbCollections = @{}
    foreach ($db in $DatabaseCollections.Keys) {
        $filtered = $DatabaseCollections[$db] | Where-Object { $_ -in $requestedCollections }
        if ($filtered) {
            $filteredDbCollections[$db] = @($filtered)
        }
    }
    $DatabaseCollections = $filteredDbCollections
}

# Output directory
if (-not $OutputDir) {
    $timestamp = Get-Date -Format "yyyyMMddTHHmmss"
    $OutputDir = "data-export-$timestamp"
}

# ---------------------------------------------------------------------------
# Resolve connection string
# ---------------------------------------------------------------------------

function Get-CosmosConnectionString {
    param([string]$RG, [string]$Account, [bool]$RBAC = $false)

    if ($RBAC) {
        Write-Host "Authenticating to Cosmos DB via Azure AD / RBAC..."
        $tokenJson = az account get-access-token --resource "https://cosmos.azure.com" --output json 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to get Azure AD token. Ensure you are logged in (az login) and have Cosmos DB RBAC roles assigned."
        }
        $token = ($tokenJson | ConvertFrom-Json).accessToken

        # Get the account endpoint to build the MongoDB-compatible URI
        $accountJson = az cosmosdb show --resource-group $RG --name $Account --output json 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to retrieve Cosmos DB account details."
        }
        $accountHost = ($accountJson | ConvertFrom-Json).name

        # Build MongoDB connection string using Azure AD token as password
        $escapedToken = [uri]::EscapeDataString($token)
        return "mongodb://${accountHost}:${escapedToken}@${accountHost}.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000&appName=@${accountHost}@&authMechanism=PLAIN&authSource=%24external"
    }

    Write-Host "Retrieving Cosmos DB connection string via az CLI..."
    $connStrings = az cosmosdb keys list `
        --resource-group $RG `
        --name $Account `
        --type connection-strings `
        --output json 2>&1

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to retrieve Cosmos DB connection strings. Ensure you are logged in (az login) and have access to the account."
    }

    $parsed = $connStrings | ConvertFrom-Json
    # Use the primary MongoDB connection string
    $mongoConn = ($parsed.connectionStrings | Where-Object { $_.description -match "Primary MongoDB" }).connectionString
    if (-not $mongoConn) {
        # Fall back to first available connection string
        $mongoConn = $parsed.connectionStrings[0].connectionString
    }

    return $mongoConn
}

function Get-MongoDBConnectionString {
    if ($env:SRC_MONGO_URI) {
        return $env:SRC_MONGO_URI
    }

    # Build from individual env vars (matching factory.py defaults)
    $host_ = if ($env:MONGODB_HOST) { $env:MONGODB_HOST } else { "localhost" }
    $port = if ($env:MONGODB_PORT) { $env:MONGODB_PORT } else { "27017" }
    $user = if ($env:MONGODB_USER) { $env:MONGODB_USER } else { "" }
    $pass = if ($env:MONGODB_PASSWORD) { $env:MONGODB_PASSWORD } else { "" }

    if ($user -and $pass) {
        return "mongodb://${user}:${pass}@${host_}:${port}/?authSource=admin"
    }
    return "mongodb://${host_}:${port}/"
}

if ($ConnectionString) {
    $connString = $ConnectionString
}
elseif ($SourceType -eq "cosmos") {
    if ($UseRBAC) {
        if (-not $ResourceGroup -or -not $CosmosAccountName) {
            throw "RBAC authentication requires -ResourceGroup and -CosmosAccountName parameters."
        }
        $connString = Get-CosmosConnectionString -RG $ResourceGroup -Account $CosmosAccountName -RBAC $true
    }
    elseif ($env:SRC_COSMOS_ENDPOINT -and $env:SRC_COSMOS_KEY) {
        # Build Cosmos MongoDB-compatible connection string from env vars
        $endpoint = $env:SRC_COSMOS_ENDPOINT -replace "https://", "" -replace ":443/", "" -replace "/$", ""
        $connString = "mongodb://${endpoint}:$([uri]::EscapeDataString($env:SRC_COSMOS_KEY))@${endpoint}:10255/?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000&appName=@${endpoint}@"
    }
    elseif ($ResourceGroup -and $CosmosAccountName) {
        $connString = Get-CosmosConnectionString -RG $ResourceGroup -Account $CosmosAccountName
    }
    else {
        throw "For Cosmos DB export, provide either -ConnectionString, -ResourceGroup/-CosmosAccountName, or set SRC_COSMOS_ENDPOINT/SRC_COSMOS_KEY environment variables."
    }
}
elseif ($SourceType -eq "mongodb") {
    $connString = Get-MongoDBConnectionString
}

# ---------------------------------------------------------------------------
# Verify mongoexport is available
# ---------------------------------------------------------------------------

if (-not (Get-Command "mongoexport" -ErrorAction SilentlyContinue)) {
    throw "mongoexport not found. Install MongoDB Database Tools: https://www.mongodb.com/docs/database-tools/installation/"
}

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "=== CoPilot-for-Consensus Data Export ===" -ForegroundColor Cyan
Write-Host "Source type : $SourceType"
Write-Host "Auth method : $(if ($UseRBAC) { 'Azure AD / RBAC' } elseif ($ConnectionString) { 'Connection string (user-provided)' } else { 'Connection string (auto-detected)' })"
Write-Host "Output dir  : $OutputDir"
Write-Host ""

# Create output directory structure
foreach ($db in $DatabaseCollections.Keys) {
    $dbDir = Join-Path $OutputDir $db
    New-Item -ItemType Directory -Force -Path $dbDir | Out-Null
}

$manifest = @{
    exported_at     = (Get-Date -Format "o")
    source_type     = $SourceType
    databases       = @{}
    document_counts = @{}
}

$totalDocs = 0

foreach ($db in $DatabaseCollections.Keys) {
    $manifest.databases[$db] = @($DatabaseCollections[$db])

    foreach ($collection in $DatabaseCollections[$db]) {
        $outFile = Join-Path $OutputDir $db "$collection.json"

        Write-Host "Exporting $db.$collection ... " -NoNewline

        # Build mongoexport args
        $exportArgs = @(
            "--uri=$connString"
            "--db=$db"
            "--collection=$collection"
            "--out=$outFile"
            "--jsonArray"
            "--quiet"
        )

        # For Cosmos DB, add SSL flag if not already in URI
        if ($SourceType -eq "cosmos" -and $connString -notmatch "ssl=true") {
            $exportArgs += "--ssl"
        }

        try {
            & mongoexport @exportArgs 2>&1 | Out-Null

            if ($LASTEXITCODE -ne 0) {
                Write-Host "WARNING: mongoexport returned non-zero exit code" -ForegroundColor Yellow
            }

            # Count documents
            if (Test-Path $outFile) {
                $content = Get-Content $outFile -Raw
                if ($content -and $content.Trim().StartsWith("[")) {
                    $docCount = ($content | ConvertFrom-Json).Count
                }
                else {
                    $docCount = (Get-Content $outFile).Count
                }
            }
            else {
                $docCount = 0
            }

            $manifest.document_counts["$db.$collection"] = $docCount
            $totalDocs += $docCount
            Write-Host "$docCount documents" -ForegroundColor Green
        }
        catch {
            Write-Host "FAILED: $_" -ForegroundColor Red
            $manifest.document_counts["$db.$collection"] = -1
        }
    }
}

# Convert JSON array files to NDJSON for mongoimport compatibility
Write-Host ""
Write-Host "Converting to NDJSON format for import compatibility..."
foreach ($db in $DatabaseCollections.Keys) {
    foreach ($collection in $DatabaseCollections[$db]) {
        $file = Join-Path $OutputDir $db "$collection.json"
        if (Test-Path $file) {
            $content = Get-Content $file -Raw
            if ($content -and $content.Trim().StartsWith("[")) {
                $docs = $content | ConvertFrom-Json
                $ndjson = ($docs | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 20 }) -join "`n"
                Set-Content -Path $file -Value $ndjson -Encoding UTF8
            }
        }
    }
}

# Write manifest
$manifestPath = Join-Path $OutputDir "manifest.json"
$manifest | ConvertTo-Json -Depth 5 | Set-Content -Path $manifestPath -Encoding UTF8

Write-Host ""
Write-Host "=== Export Complete ===" -ForegroundColor Cyan
Write-Host "Total documents : $totalDocs"
Write-Host "Output directory: $OutputDir"
Write-Host "Manifest        : $manifestPath"
Write-Host ""
Write-Host "To import this data into another deployment:" -ForegroundColor Yellow
Write-Host "  .\scripts\data-migration-import.ps1 -DestType <cosmos|mongodb> -ExportDir `"$OutputDir`""
