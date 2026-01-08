# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#
.SYNOPSIS
Fix MESSAGE_BUS schema field names and add Azure Service Bus configuration fields.

.DESCRIPTION
1. Fixes field names from uppercase (RABBITMQ_HOST) to lowercase (rabbitmq_host)
2. Renames message_bus_user/password to rabbitmq_username/password
3. Adds Azure Service Bus specific configuration fields
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

Write-Host "=== Fixing MESSAGE_BUS Schema Fields ===" -ForegroundColor Cyan

$totalReplacements = 0
$filesUpdated = 0

foreach ($file in $schemaFiles) {
    $filePath = Join-Path $schemaDir $file
    
    Write-Host "Processing $file..."
    
    try {
        $content = Get-Content -Path $filePath -Raw -Encoding UTF8
        $originalContent = $content
        $localReplacements = 0
        
        # Fix field names: RABBITMQ_HOST -> rabbitmq_host
        if ($content -match '"RABBITMQ_HOST"') {
            $content = $content -replace '"RABBITMQ_HOST"', '"rabbitmq_host"'
            Write-Host "  - Fixed RABBITMQ_HOST field name"
            $localReplacements++
        }
        
        # Fix field names: RABBITMQ_PORT -> rabbitmq_port
        if ($content -match '"RABBITMQ_PORT"') {
            $content = $content -replace '"RABBITMQ_PORT"', '"rabbitmq_port"'
            Write-Host "  - Fixed RABBITMQ_PORT field name"
            $localReplacements++
        }
        
        # Rename message_bus_user to rabbitmq_username with env var RABBITMQ_USERNAME
        if ($content -match '"message_bus_user"') {
            $content = $content -replace '"message_bus_user": \{', '"rabbitmq_username": {'
            $content = $content -replace '"secret_name": "message_bus_user"', '"secret_name": "rabbitmq_username"'
            $content = $content -replace '"message bus username', '"RabbitMQ username'
            Write-Host "  - Renamed message_bus_user to rabbitmq_username"
            $localReplacements++
        }
        
        # Rename message_bus_password to rabbitmq_password with env var RABBITMQ_PASSWORD
        if ($content -match '"message_bus_password"') {
            $content = $content -replace '"message_bus_password": \{', '"rabbitmq_password": {'
            $content = $content -replace '"secret_name": "message_bus_password"', '"secret_name": "rabbitmq_password"'
            $content = $content -replace '"message bus password', '"RabbitMQ password'
            Write-Host "  - Renamed message_bus_password to rabbitmq_password"
            $localReplacements++
        }
        
        # Add Service Bus fields after MESSAGE_BUS_TYPE
        if ($content -match '"message_bus_type": \{[^}]+\}' -and $content -notmatch '"servicebus_use_managed_identity"') {
            $replacement = @'
    "message_bus_type": {
      "type": "string",
      "source": "env",
      "env_var": "MESSAGE_BUS_TYPE",
      "required": true,
      "description": "Message bus type (rabbitmq, servicebus)"
    },
    "servicebus_use_managed_identity": {
      "type": "bool",
      "source": "env",
      "env_var": "SERVICEBUS_USE_MANAGED_IDENTITY",
      "default": true,
      "required": false,
      "description": "Use Azure managed identity for Service Bus authentication (when MESSAGE_BUS_TYPE=servicebus)"
    },
    "servicebus_fully_qualified_namespace": {
      "type": "string",
      "source": "env",
      "env_var": "SERVICEBUS_FULLY_QUALIFIED_NAMESPACE",
      "required": false,
      "description": "Azure Service Bus fully qualified namespace (when MESSAGE_BUS_TYPE=servicebus, e.g., mybus.servicebus.windows.net)"
    }
'@
            
            $pattern = '    "message_bus_type": \{[^}]*"description": "[^"]*"\s*\}'
            if ($content -match $pattern) {
                $content = $content -replace $pattern, $replacement
                Write-Host "  - Added Service Bus configuration fields"
                $localReplacements++
            }
        }
        
        if ($content -ne $originalContent) {
            Set-Content -Path $filePath -Value $content -Encoding UTF8 -NoNewline
            Write-Host "  [OK] Updated: $file ($localReplacements changes)" -ForegroundColor Green
            $filesUpdated++
            $totalReplacements += $localReplacements
        }
    } catch {
        Write-Host "  [ERROR] Processing $file : $_" -ForegroundColor Red
    }
}

Write-Host "`n=== Summary ===" -ForegroundColor Cyan
Write-Host "Total files updated: $filesUpdated"
Write-Host "Total changes made: $totalReplacements"
Write-Host "`nChanges complete! Review with: git diff"
