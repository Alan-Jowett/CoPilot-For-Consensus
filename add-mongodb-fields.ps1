# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#
.SYNOPSIS
Add MongoDB-specific configuration fields alongside Cosmos DB fields.

.DESCRIPTION
Adds mongodb_host, mongodb_port, mongodb_database fields with MONGODB_* env vars
to complement existing cosmos_* fields for DOCUMENT_STORE_TYPE discriminant.
#>

$ErrorActionPreference = "Stop"
$WarningPreference = "SilentlyContinue"

$workspaceRoot = "F:\CoPilot-For-Consensus-Review"
$schemaDir = Join-Path $workspaceRoot "docs\schemas\configs"

$schemaFiles = @(
    "chunking.json"
    "parsing.json"
    "embedding.json"
    "orchestrator.json"
    "reporting.json"
    "summarization.json"
    "ingestion.json"
)

Write-Host "=== Adding MongoDB Configuration Fields ===" -ForegroundColor Cyan

$totalReplacements = 0
$filesUpdated = 0

foreach ($file in $schemaFiles) {
    $filePath = Join-Path $schemaDir $file
    
    Write-Host "Processing $file..."
    
    try {
        $content = Get-Content -Path $filePath -Raw -Encoding UTF8
        $originalContent = $content
        
        # Step 1: Rename existing doc_store fields to cosmos-specific
        $content = $content -replace '"doc_store_host":', '"cosmos_endpoint":'
        $content = $content -replace '"doc_store_port":', '"cosmos_port":'
        $content = $content -replace '"doc_store_name":', '"cosmos_database":'
        
        # Step 2: Update descriptions
        $content = $content -replace '"Document store hostname"', '"Cosmos DB endpoint URL (when DOCUMENT_STORE_TYPE=cosmosdb)"'
        $content = $content -replace '"Document store port"', '"Cosmos DB port (when DOCUMENT_STORE_TYPE=cosmosdb)"'
        $content = $content -replace '"Document store database name"', '"Cosmos DB database name (when DOCUMENT_STORE_TYPE=cosmosdb)"'
        
        # Step 3: Add MongoDB fields after DOCUMENT_STORE_TYPE
        if ($content -notmatch '"mongodb_host"') {
            $pattern = '("doc_store_type": \{[^}]+\}),\s+("cosmos_endpoint":)'
            $replacement = @'
$1,
    "mongodb_host": {
      "type": "string",
      "source": "env",
      "env_var": "MONGODB_HOST",
      "default": "documentdb",
      "description": "MongoDB hostname (when DOCUMENT_STORE_TYPE=mongodb)"
    },
    "mongodb_port": {
      "type": "int",
      "source": "env",
      "env_var": "MONGODB_PORT",
      "default": 27017,
      "description": "MongoDB port (when DOCUMENT_STORE_TYPE=mongodb)"
    },
    "mongodb_database": {
      "type": "string",
      "source": "env",
      "env_var": "MONGODB_DATABASE",
      "default": "copilot",
      "description": "MongoDB database name (when DOCUMENT_STORE_TYPE=mongodb)"
    },
    $2
'@
            $content = $content -replace $pattern, $replacement
            Write-Host "  - Added MongoDB configuration fields"
        }
        
        # Step 4: Update DOCUMENT_STORE_TYPE description
        $content = $content -replace '"Document store type"', '"Document store type (mongodb, cosmosdb)"'
        
        if ($content -ne $originalContent) {
            Set-Content -Path $filePath -Value $content -Encoding UTF8 -NoNewline
            Write-Host "  [OK] Updated: $file" -ForegroundColor Green
            $filesUpdated++
        }
    } catch {
        Write-Host "  [ERROR] Processing $file : $_" -ForegroundColor Red
    }
}

Write-Host "`n=== Summary ===" -ForegroundColor Cyan
Write-Host "Total files updated: $filesUpdated"
Write-Host "`nChanges complete! Review with: git diff"
