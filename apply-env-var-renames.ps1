# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#
.SYNOPSIS
Apply standardized adapter-prefixed environment variable naming across all schema, docker-compose, and bicep files.

.DESCRIPTION
Reads env-var-mapping.csv and applies all old->new environment variable name replacements across the codebase.
#>

$ErrorActionPreference = "Stop"
$WarningPreference = "SilentlyContinue"

# Configuration
$workspaceRoot = "F:\CoPilot-For-Consensus-Review"
$mappingFile = Join-Path $workspaceRoot "env-var-mapping.csv"
$schemaDir = Join-Path $workspaceRoot "docs\schemas\configs"
$dockerComposeDir = $workspaceRoot
$bicepDir = Join-Path $workspaceRoot "infra\azure\modules"

# Read mapping CSV
Write-Host "Loading environment variable mappings from $mappingFile..." -ForegroundColor Cyan
$mappings = @()
if (Test-Path $mappingFile) {
    $mappings = Import-Csv $mappingFile
} else {
    Write-Host "ERROR: Mapping file not found at $mappingFile" -ForegroundColor Red
    exit 1
}

Write-Host "Loaded $($mappings.Count) variable mappings" -ForegroundColor Green

# Track statistics
$totalReplacements = 0
$filesUpdated = @{}
$fileErrors = @()

# Function to apply replacements to a file
function Apply-ReplacementsToFile {
    param(
        [string]$FilePath,
        [array]$Mappings
    )

    if (-not (Test-Path $FilePath)) {
        return 0
    }

    try {
        $content = Get-Content -Path $FilePath -Raw -Encoding UTF8
        $originalContent = $content
        $replacementCount = 0

        # Apply each mapping
        foreach ($mapping in $Mappings) {
            $oldName = $mapping.old_name
            $newName = $mapping.new_name
            
            # Count occurrences before replacement
            $pattern = [regex]::Escape($oldName)
            $matches = [regex]::Matches($content, $pattern)
            
            if ($matches.Count -gt 0) {
                # Replace all occurrences
                $content = $content -replace $pattern, $newName
                $replacementCount += $matches.Count
                Write-Host "  - $oldName -> $newName : $($matches.Count) replacements" -ForegroundColor Yellow
            }
        }

        # Write back if changes were made
        if ($content -ne $originalContent) {
            Set-Content -Path $FilePath -Value $content -Encoding UTF8 -NoNewline
            Write-Host "  [OK] Updated: $FilePath ($replacementCount total replacements)" -ForegroundColor Green
            return $replacementCount
        } else {
            return 0
        }
    } catch {
        Write-Host "  [ERROR] processing $FilePath : $_" -ForegroundColor Red
        $script:fileErrors += $FilePath
        return 0
    }
}

# Process schema files
Write-Host "`n=== Processing Schema Files ===" -ForegroundColor Cyan
$schemaFiles = @(
    "auth.json"
    "parsing.json"
    "chunking.json"
    "embedding.json"
    "orchestrator.json"
    "reporting.json"
    "summarization.json"
    "ingestion.json"
)

foreach ($file in $schemaFiles) {
    $filePath = Join-Path $schemaDir $file
    Write-Host "Processing $file..."
    $count = Apply-ReplacementsToFile -FilePath $filePath -Mappings $mappings
    if ($count -gt 0) {
        $filesUpdated[$filePath] = $count
        $totalReplacements += $count
    }
}

# Process docker-compose files
Write-Host "`n=== Processing Docker Compose Files ===" -ForegroundColor Cyan
$composeFiles = @(
    "docker-compose.yml"
    "docker-compose.services.yml"
    "docker-compose.infra.yml"
)

foreach ($file in $composeFiles) {
    $filePath = Join-Path $dockerComposeDir $file
    if (Test-Path $filePath) {
        Write-Host "Processing $file..."
        $count = Apply-ReplacementsToFile -FilePath $filePath -Mappings $mappings
        if ($count -gt 0) {
            $filesUpdated[$filePath] = $count
            $totalReplacements += $count
        }
    }
}

# Process bicep files
Write-Host "`n=== Processing Bicep Files ===" -ForegroundColor Cyan
$bicepFiles = @(
    "containerapps.bicep"
    "main.bicep"
    "variables.bicep"
)

foreach ($file in $bicepFiles) {
    $filePath = Join-Path $bicepDir $file
    if (Test-Path $filePath) {
        Write-Host "Processing $file..."
        $count = Apply-ReplacementsToFile -FilePath $filePath -Mappings $mappings
        if ($count -gt 0) {
            $filesUpdated[$filePath] = $count
            $totalReplacements += $count
        }
    }
}

# Print summary
Write-Host "`n=== Summary ===" -ForegroundColor Cyan
Write-Host "Total files updated: $($filesUpdated.Count)"
Write-Host "Total replacements made: $totalReplacements"

if ($filesUpdated.Count -gt 0) {
    Write-Host "`nFiles updated:" -ForegroundColor Green
    foreach ($file in $filesUpdated.Keys | Sort-Object) {
        $relPath = $file -replace [regex]::Escape($workspaceRoot), "."
        Write-Host "  $relPath : $($filesUpdated[$file]) replacements"
    }
}

if ($fileErrors.Count -gt 0) {
    Write-Host "`nErrors encountered in:" -ForegroundColor Red
    foreach ($file in $fileErrors) {
        Write-Host "  $file"
    }
}

Write-Host "`nEnvironment variable renaming complete!" -ForegroundColor Green
Write-Host "Review changes with: git diff"
Write-Host "Stage changes with: git add -A"
Write-Host "Commit with: git commit -m 'refactor: add MESSAGE_BUS adapter-specific naming'"
