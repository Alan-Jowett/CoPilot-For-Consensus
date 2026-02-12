# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#
.SYNOPSIS
    Import data into a CoPilot-for-Consensus deployment.

.DESCRIPTION
    Imports collections from a data export directory (created by
    data-migration-export.ps1) into Azure Cosmos DB or MongoDB.

    See docs/operations/data-migration.md for full documentation.

.PARAMETER DestType
    The type of destination database: "cosmos" or "mongodb".

.PARAMETER ConnectionString
    MongoDB-compatible connection string. If omitted, the script derives it
    from environment variables or az CLI (for Cosmos).

.PARAMETER ResourceGroup
    Azure resource group (required when DestType=cosmos and no ConnectionString).

.PARAMETER CosmosAccountName
    Azure Cosmos DB account name (required when DestType=cosmos and no ConnectionString).

.PARAMETER ExportDir
    Path to the export directory (created by data-migration-export.ps1).

.PARAMETER Collections
    Comma-separated list of collections to import. Defaults to all collections
    found in the export directory.

.PARAMETER Mode
    Import mode: "upsert" (default, overwrites existing docs) or "merge"
    (skip existing documents with duplicate _id).

.PARAMETER NumWorkers
    Number of parallel insertion workers for mongoimport. Default: 1.

.PARAMETER Drop
    If specified, drops existing collections before importing.

.PARAMETER UseRBAC
    Authenticate to Azure Cosmos DB using Azure AD / RBAC (via az login)
    instead of connection string keys. Requires the logged-in principal to
    have the "Cosmos DB Built-in Data Contributor" role.

.EXAMPLE
    .\scripts\data-migration-import.ps1 -DestType cosmos -ResourceGroup copilot-app-rg -CosmosAccountName copilot-cos-dev-y6f2c -ExportDir data-export-20260212T170000

.EXAMPLE
    .\scripts\data-migration-import.ps1 -DestType cosmos -ResourceGroup copilot-app-rg -CosmosAccountName copilot-cos-dev-y6f2c -ExportDir data-export-20260212T170000 -UseRBAC

.EXAMPLE
    .\scripts\data-migration-import.ps1 -DestType mongodb -ExportDir data-export-20260212T170000

.EXAMPLE
    .\scripts\data-migration-import.ps1 -DestType mongodb -ExportDir data-export-20260212T170000 -Collections summaries -Drop
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("cosmos", "mongodb")]
    [string]$DestType,

    [Parameter(Mandatory = $false)]
    [string]$ConnectionString,

    [Parameter(Mandatory = $false)]
    [string]$ResourceGroup,

    [Parameter(Mandatory = $false)]
    [string]$CosmosAccountName,

    [Parameter(Mandatory = $true)]
    [string]$ExportDir,

    [Parameter(Mandatory = $false)]
    [string]$Collections,

    [Parameter(Mandatory = $false)]
    [ValidateSet("upsert", "merge")]
    [string]$Mode = "upsert",

    [Parameter(Mandatory = $false)]
    [int]$NumWorkers = 1,

    [switch]$Drop,

    [switch]$UseRBAC
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Validate export directory
# ---------------------------------------------------------------------------

if (-not (Test-Path $ExportDir)) {
    throw "Export directory not found: $ExportDir"
}

$manifestPath = Join-Path $ExportDir "manifest.json"
if (Test-Path $manifestPath) {
    $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
    Write-Host "Loading export from $($manifest.exported_at) (source: $($manifest.source_type))" -ForegroundColor Cyan
}

# ---------------------------------------------------------------------------
# Discover databases and collections from export directory
# ---------------------------------------------------------------------------

$DatabaseCollections = @{}
$dbDirs = Get-ChildItem -Path $ExportDir -Directory
foreach ($dbDir in $dbDirs) {
    $jsonFiles = Get-ChildItem -Path $dbDir.FullName -Filter "*.json"
    if ($jsonFiles) {
        $collNames = $jsonFiles | ForEach-Object { $_.BaseName }
        $DatabaseCollections[$dbDir.Name] = @($collNames)
    }
}

if ($DatabaseCollections.Count -eq 0) {
    throw "No collections found in export directory: $ExportDir"
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

        $accountJson = az cosmosdb show --resource-group $RG --name $Account --output json 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to retrieve Cosmos DB account details."
        }
        $accountHost = ($accountJson | ConvertFrom-Json).name

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
    $mongoConn = ($parsed.connectionStrings | Where-Object { $_.description -match "Primary MongoDB" }).connectionString
    if (-not $mongoConn) {
        $mongoConn = $parsed.connectionStrings[0].connectionString
    }

    return $mongoConn
}

function Get-MongoDBConnectionString {
    if ($env:DST_MONGO_URI) {
        return $env:DST_MONGO_URI
    }

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
elseif ($DestType -eq "cosmos") {
    if ($UseRBAC) {
        if (-not $ResourceGroup -or -not $CosmosAccountName) {
            throw "RBAC authentication requires -ResourceGroup and -CosmosAccountName parameters."
        }
        $connString = Get-CosmosConnectionString -RG $ResourceGroup -Account $CosmosAccountName -RBAC $true
    }
    elseif ($env:DST_COSMOS_ENDPOINT -and $env:DST_COSMOS_KEY) {
        $endpoint = $env:DST_COSMOS_ENDPOINT -replace "https://", "" -replace ":443/", "" -replace "/$", ""
        $connString = "mongodb://${endpoint}:$([uri]::EscapeDataString($env:DST_COSMOS_KEY))@${endpoint}:10255/?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000&appName=@${endpoint}@"
    }
    elseif ($ResourceGroup -and $CosmosAccountName) {
        $connString = Get-CosmosConnectionString -RG $ResourceGroup -Account $CosmosAccountName
    }
    else {
        throw "For Cosmos DB import, provide either -ConnectionString, -ResourceGroup/-CosmosAccountName, or set DST_COSMOS_ENDPOINT/DST_COSMOS_KEY environment variables."
    }
}
elseif ($DestType -eq "mongodb") {
    $connString = Get-MongoDBConnectionString
}

# ---------------------------------------------------------------------------
# Verify mongoimport is available
# ---------------------------------------------------------------------------

if (-not (Get-Command "mongoimport" -ErrorAction SilentlyContinue)) {
    throw "mongoimport not found. Install MongoDB Database Tools: https://www.mongodb.com/docs/database-tools/installation/"
}

# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "=== CoPilot-for-Consensus Data Import ===" -ForegroundColor Cyan
Write-Host "Destination : $DestType"
Write-Host "Auth method : $(if ($UseRBAC) { 'Azure AD / RBAC' } elseif ($ConnectionString) { 'Connection string (user-provided)' } else { 'Connection string (auto-detected)' })"
Write-Host "Export dir  : $ExportDir"
Write-Host "Mode        : $Mode"
Write-Host "Workers     : $NumWorkers"
if ($Drop) { Write-Host "Drop        : YES (existing data will be removed)" -ForegroundColor Yellow }
Write-Host ""

# Import order matters: sources first, then archives, messages, threads, chunks, summaries
$importOrder = @("sources", "archives", "messages", "threads", "chunks", "summaries", "reports", "user_roles")

$totalImported = 0
$errors = @()

foreach ($db in $DatabaseCollections.Keys) {
    # Sort collections by import order
    $orderedCollections = $DatabaseCollections[$db] | Sort-Object {
        $idx = $importOrder.IndexOf($_)
        if ($idx -eq -1) { 999 } else { $idx }
    }

    foreach ($collection in $orderedCollections) {
        $inFile = Join-Path $ExportDir $db "$collection.json"

        if (-not (Test-Path $inFile)) {
            Write-Host "SKIP $db.$collection (file not found)" -ForegroundColor Yellow
            continue
        }

        # Check if file has content
        $fileSize = (Get-Item $inFile).Length
        if ($fileSize -eq 0) {
            Write-Host "SKIP $db.$collection (empty file)" -ForegroundColor Yellow
            continue
        }

        Write-Host "Importing $db.$collection ... " -NoNewline

        # Build mongoimport args
        $importArgs = @(
            "--uri=$connString"
            "--db=$db"
            "--collection=$collection"
            "--file=$inFile"
            "--numInsertionWorkers=$NumWorkers"
        )

        if ($Drop) {
            $importArgs += "--drop"
        }

        if ($Mode -eq "upsert") {
            $importArgs += "--mode=upsert"
            $importArgs += "--upsertFields=_id"
        }
        elseif ($Mode -eq "merge") {
            # Use insert mode so duplicates fail silently rather than being merged/updated
            $importArgs += "--mode=insert"
        }

        # For Cosmos DB, add SSL flag if not already in URI
        if ($DestType -eq "cosmos" -and $connString -notmatch "ssl=true") {
            $importArgs += "--ssl"
        }

        try {
            $output = & mongoimport @importArgs 2>&1
            $outputStr = $output -join "`n"

            if ($LASTEXITCODE -ne 0) {
                Write-Host "WARNING" -ForegroundColor Yellow
                Write-Host "  $outputStr" -ForegroundColor Yellow
                $errors += "${db}.${collection}: $outputStr"
            }
            else {
                # Parse imported count from mongoimport output
                if ($outputStr -match "(\d+) document\(s\) imported successfully") {
                    $count = [int]$Matches[1]
                }
                elseif ($outputStr -match "imported (\d+)") {
                    $count = [int]$Matches[1]
                }
                else {
                    # Count lines in file as fallback
                    $count = (Get-Content $inFile).Count
                }
                $totalImported += $count
                Write-Host "$count documents" -ForegroundColor Green
            }
        }
        catch {
            Write-Host "FAILED: $_" -ForegroundColor Red
            $errors += "${db}.${collection}: $_"
        }
    }
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "=== Import Complete ===" -ForegroundColor Cyan
Write-Host "Total imported: $totalImported documents"

if ($errors.Count -gt 0) {
    Write-Host ""
    Write-Host "Errors ($($errors.Count)):" -ForegroundColor Red
    foreach ($err in $errors) {
        Write-Host "  - $err" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "Some collections had errors. Review the output above and retry if needed." -ForegroundColor Yellow
}
else {
    Write-Host "All collections imported successfully." -ForegroundColor Green
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Verify data counts: python scripts/get_data_counts.py"
Write-Host "  2. If importing into a fresh deployment, restart services to pick up the data"
Write-Host "  3. Delete the export directory when no longer needed (may contain PII)"
