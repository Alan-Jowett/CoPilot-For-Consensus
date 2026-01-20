# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#
.SYNOPSIS
Exports Azure Log Analytics (Container Apps) logs needed for RCA.

.DESCRIPTION
Queries the Log Analytics workspace (by name) and exports compact JSON files with:
- table inventory
- schema validation failures
- missing source_type failures
- RabbitMQ heartbeat failures
- startup requeue failures

This is designed to keep output small and reviewable (uses summarize/take).

Prereqs:
- Azure CLI installed (`az`)
- Logged in (`az login`) and subscription set (`az account set ...`) if needed
- Permission to query the workspace

.EXAMPLE
./scripts/export_log_analytics_rca.ps1 -WorkspaceName copilot-law-dev-y6f2c -Timespan P1D

.EXAMPLE
./scripts/export_log_analytics_rca.ps1 -WorkspaceName copilot-law-dev-y6f2c -Timespan PT6H -OutDir logs/azure/copilot-law-dev-y6f2c/rca
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$WorkspaceName = "copilot-law-dev-y6f2c",

    [Parameter(Mandatory = $false)]
    [string]$Timespan = "P1D",

    [Parameter(Mandatory = $false)]
    [string]$OutDir,

    [Parameter(Mandatory = $false)]
    [int]$SampleSize = 100
)

$ErrorActionPreference = "Stop"

function Test-CommandAvailable([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

if (-not $PSBoundParameters.ContainsKey('OutDir')) {
    $OutDir = "logs/azure/$WorkspaceName/rca"
}

$TopSize = 50
$ErrorMessageTruncationLength = 200

Test-CommandAvailable "az"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "Resolving Log Analytics workspace: $WorkspaceName" -ForegroundColor Cyan

$wsJson = az monitor log-analytics workspace list --query "[?name=='$WorkspaceName'] | [0]" -o json
if (-not $wsJson -or $wsJson -eq "null") {
    throw "Workspace not found in current subscription: $WorkspaceName"
}

$ws = $wsJson | ConvertFrom-Json
$workspaceId = $ws.customerId

if (-not $workspaceId) {
    throw "Workspace customerId missing; cannot query. Raw: $wsJson"
}

Write-Host "Workspace resourceGroup: $($ws.resourceGroup)" -ForegroundColor DarkGray
Write-Host "Workspace customerId:   $workspaceId" -ForegroundColor DarkGray

function Invoke-LawQuery {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$Kql
    )

    $outPath = Join-Path $OutDir "$Name.json"

    # Azure CLI on Windows does not reliably pass multi-line arguments.
    # Flatten the KQL to a single line so the entire query is preserved.
    $kqlOneLine = ($Kql -replace "(`r`n|`n|`r)", " ")
    $kqlOneLine = ($kqlOneLine -replace "\s+", " ").Trim()

    # Keep output compact by using KQL summarize/take.
    # Capture both stdout and stderr so failures don't silently emit empty/malformed JSON.
    $queryOutput = az monitor log-analytics query `
        --workspace $workspaceId `
        --analytics-query $kqlOneLine `
        --timespan $Timespan `
        -o json 2>&1

    if ($LASTEXITCODE -ne 0) {
        $errorMessage = "Azure CLI log-analytics query '$Name' failed with exit code $LASTEXITCODE.`nAzure CLI output:`n$queryOutput"
        throw $errorMessage
    }

    $queryOutput | Out-File -Encoding utf8 $outPath

    return $outPath
}

# 1) Table inventory (helps adapt RCA queries if tables differ)
$tableInventoryKql = @"
search *
| summarize count() by `$table
| top $TopSize by count_ desc
"@

# 2) Validation failures (schema enforcement)
$validationCountKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend msg=tostring(l.message)
| where msg has 'Validation failed for event type'
| summarize cnt=count()
"@

$validationByAppKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend msg=tostring(l.message)
| where msg has 'Validation failed for event type'
| summarize cnt=count() by ContainerAppName_s
| top $TopSize by cnt desc
"@

$validationSampleKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend msg=tostring(l.message), level=tostring(l.level), logger=tostring(l.logger)
| where msg has 'Validation failed for event type'
| project TimeGenerated, ContainerAppName_s, level, logger, msg
| order by TimeGenerated desc
| take $SampleSize
"@

# 3) Missing source_type (parsing startup requeue / legacy data)
$missingSourceTypeCountKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend msg=tostring(l.message)
| where msg has 'missing required field' and msg has 'source_type'
| summarize cnt=count()
"@

$missingSourceTypeByAppKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend msg=tostring(l.message)
| where msg has 'missing required field' and msg has 'source_type'
| summarize cnt=count() by ContainerAppName_s
| top $TopSize by cnt desc
"@

$missingSourceTypeSampleKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend msg=tostring(l.message), level=tostring(l.level), logger=tostring(l.logger)
| where msg has 'missing required field' and msg has 'source_type'
| project TimeGenerated, ContainerAppName_s, level, logger, msg
| order by TimeGenerated desc
| take $SampleSize
"@

# 4) RabbitMQ heartbeat failures
$rabbitHeartbeatCountKql = @"
ContainerAppConsoleLogs_CL
| where Log_s has 'missed heartbeats from client'
| summarize cnt=count()
"@

$rabbitHeartbeatByAppKql = @"
ContainerAppConsoleLogs_CL
| where Log_s has 'missed heartbeats from client'
| summarize cnt=count() by ContainerAppName_s
| top $TopSize by cnt desc
"@

$rabbitHeartbeatSampleKql = @"
ContainerAppConsoleLogs_CL
| where Log_s has 'missed heartbeats from client'
| project TimeGenerated, ContainerAppName_s, ContainerName_s, Stream_s, Log_s
| order by TimeGenerated desc
| take $SampleSize
"@

# 5) Startup requeue failures
$startupRequeueCountKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend msg=tostring(l.message)
| where msg has 'Startup requeue' and (msg has 'failed' or msg has 'Failed')
| summarize cnt=count()
"@

$startupRequeueByAppKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend msg=tostring(l.message)
| where msg has 'Startup requeue' and (msg has 'failed' or msg has 'Failed')
| summarize cnt=count() by ContainerAppName_s
| top $TopSize by cnt desc
"@

$startupRequeueSampleKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend msg=tostring(l.message), level=tostring(l.level), logger=tostring(l.logger)
| where msg has 'Startup requeue' and (msg has 'failed' or msg has 'Failed')
| project TimeGenerated, ContainerAppName_s, level, logger, msg
| order by TimeGenerated desc
| take $SampleSize
"@

# 6) Azure OpenAI / LLM rate limiting (commonly surfaces as 429)
$aoaiRateLimitCountKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend level=tostring(l.level), msg=tostring(l.message)
| where isnotempty(level)
| where level == 'ERROR' and (msg has 'Error code: 429' or msg has 'RateLimitReached')
| summarize cnt=count()
"@

$aoaiRateLimitByAppKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend level=tostring(l.level), msg=tostring(l.message)
| where isnotempty(level)
| where level == 'ERROR' and (msg has 'Error code: 429' or msg has 'RateLimitReached')
| summarize cnt=count() by ContainerAppName_s
| top $TopSize by cnt desc
"@

$aoaiRateLimitSampleKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend level=tostring(l.level), logger=tostring(l.logger), msg=tostring(l.message)
| where isnotempty(level)
| where level == 'ERROR' and (msg has 'Error code: 429' or msg has 'RateLimitReached')
| project TimeGenerated, ContainerAppName_s, level, logger, msg
| order by TimeGenerated desc
| take $SampleSize
"@

# 7) Parsing can't resolve ArchiveStore documents referenced by events
$archiveNotFoundCountKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend level=tostring(l.level), msg=tostring(l.message)
| where isnotempty(level)
| where msg has 'not found in ArchiveStore'
| summarize cnt=count()
"@

$archiveNotFoundByAppKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend level=tostring(l.level), msg=tostring(l.message)
| where isnotempty(level)
| where msg has 'not found in ArchiveStore'
| summarize cnt=count() by ContainerAppName_s
| top $TopSize by cnt desc
"@

$archiveNotFoundSampleKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend level=tostring(l.level), logger=tostring(l.logger), msg=tostring(l.message)
| where isnotempty(level)
| where msg has 'not found in ArchiveStore'
| project TimeGenerated, ContainerAppName_s, level, logger, msg
| order by TimeGenerated desc
| take $SampleSize
"@

# 8) Generic retry exhaustion (useful for spotting downstream instability)
$retryExhaustedCountKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend level=tostring(l.level), msg=tostring(l.message)
| where isnotempty(level)
| where level == 'ERROR' and msg has 'Retry exhausted'
| summarize cnt=count()
"@

$retryExhaustedByAppKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend level=tostring(l.level), msg=tostring(l.message)
| where isnotempty(level)
| where level == 'ERROR' and msg has 'Retry exhausted'
| summarize cnt=count() by ContainerAppName_s
| top $TopSize by cnt desc
"@

$retryExhaustedSampleKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend level=tostring(l.level), logger=tostring(l.logger), msg=tostring(l.message)
| where isnotempty(level)
| where level == 'ERROR' and msg has 'Retry exhausted'
| project TimeGenerated, ContainerAppName_s, level, logger, msg
| order by TimeGenerated desc
| take $SampleSize
"@

# 9) Auth JWKS issues (often shows up during cold starts / dependency ordering)
$jwksConnectionRefusedCountKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend msg=tostring(l.message)
| where msg has 'JWKS fetch attempt' and msg has 'Connection refused'
| summarize cnt=count()
"@

$jwksConnectionRefusedByAppKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend msg=tostring(l.message)
| where msg has 'JWKS fetch attempt' and msg has 'Connection refused'
| summarize cnt=count() by ContainerAppName_s
| top $TopSize by cnt desc
"@

$jwksConnectionRefusedSampleKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend level=tostring(l.level), logger=tostring(l.logger), msg=tostring(l.message)
| where msg has 'JWKS fetch attempt' and msg has 'Connection refused'
| project TimeGenerated, ContainerAppName_s, level, logger, msg
| order by TimeGenerated desc
| take $SampleSize
"@

# 10) Quick leaderboard of ERROR messages (truncated) to find Azure-specific failures not covered above
$topErrorMessagesKql = @"
ContainerAppConsoleLogs_CL
| extend l=parse_json(Log_s)
| extend level=tostring(l.level), msg=tostring(l.message)
| where isnotempty(level)
| where level == 'ERROR'
| extend msg200=substring(msg, 0, $ErrorMessageTruncationLength)
| summarize cnt=count() by ContainerAppName_s, msg200
| top $TopSize by cnt desc
"@

Write-Host "Running Log Analytics exports (timespan=$Timespan)..." -ForegroundColor Cyan

$exportQueries = @(
    @{ Name = 'tables'; Kql = $tableInventoryKql; Key = 'table_inventory' },
    @{ Name = 'validation_errors_count'; Kql = $validationCountKql; Key = 'validation_count' },
    @{ Name = 'validation_errors_by_app'; Kql = $validationByAppKql; Key = 'validation_by_app' },
    @{ Name = 'validation_errors_sample'; Kql = $validationSampleKql; Key = 'validation_sample' },
    @{ Name = 'missing_source_type_count'; Kql = $missingSourceTypeCountKql; Key = 'missing_source_type_count' },
    @{ Name = 'missing_source_type_by_app'; Kql = $missingSourceTypeByAppKql; Key = 'missing_source_type_by_app' },
    @{ Name = 'missing_source_type_sample'; Kql = $missingSourceTypeSampleKql; Key = 'missing_source_type_sample' },
    @{ Name = 'rabbitmq_heartbeat_count'; Kql = $rabbitHeartbeatCountKql; Key = 'rabbitmq_heartbeat_count' },
    @{ Name = 'rabbitmq_heartbeat_by_app'; Kql = $rabbitHeartbeatByAppKql; Key = 'rabbitmq_heartbeat_by_app' },
    @{ Name = 'rabbitmq_heartbeat_sample'; Kql = $rabbitHeartbeatSampleKql; Key = 'rabbitmq_heartbeat_sample' },
    @{ Name = 'startup_requeue_count'; Kql = $startupRequeueCountKql; Key = 'startup_requeue_count' },
    @{ Name = 'startup_requeue_by_app'; Kql = $startupRequeueByAppKql; Key = 'startup_requeue_by_app' },
    @{ Name = 'startup_requeue_sample'; Kql = $startupRequeueSampleKql; Key = 'startup_requeue_sample' },
    @{ Name = 'aoai_rate_limit_count'; Kql = $aoaiRateLimitCountKql; Key = 'aoai_rate_limit_count' },
    @{ Name = 'aoai_rate_limit_by_app'; Kql = $aoaiRateLimitByAppKql; Key = 'aoai_rate_limit_by_app' },
    @{ Name = 'aoai_rate_limit_sample'; Kql = $aoaiRateLimitSampleKql; Key = 'aoai_rate_limit_sample' },
    @{ Name = 'archive_not_found_count'; Kql = $archiveNotFoundCountKql; Key = 'archive_not_found_count' },
    @{ Name = 'archive_not_found_by_app'; Kql = $archiveNotFoundByAppKql; Key = 'archive_not_found_by_app' },
    @{ Name = 'archive_not_found_sample'; Kql = $archiveNotFoundSampleKql; Key = 'archive_not_found_sample' },
    @{ Name = 'retry_exhausted_count'; Kql = $retryExhaustedCountKql; Key = 'retry_exhausted_count' },
    @{ Name = 'retry_exhausted_by_app'; Kql = $retryExhaustedByAppKql; Key = 'retry_exhausted_by_app' },
    @{ Name = 'retry_exhausted_sample'; Kql = $retryExhaustedSampleKql; Key = 'retry_exhausted_sample' },
    @{ Name = 'jwks_connection_refused_count'; Kql = $jwksConnectionRefusedCountKql; Key = 'jwks_connection_refused_count' },
    @{ Name = 'jwks_connection_refused_by_app'; Kql = $jwksConnectionRefusedByAppKql; Key = 'jwks_connection_refused_by_app' },
    @{ Name = 'jwks_connection_refused_sample'; Kql = $jwksConnectionRefusedSampleKql; Key = 'jwks_connection_refused_sample' },
    @{ Name = 'top_error_messages'; Kql = $topErrorMessagesKql; Key = 'top_error_messages' }
)

$exports = @{}
foreach ($q in $exportQueries) {
    $exports[$q.Key] = Invoke-LawQuery -Name $q.Name -Kql $q.Kql
}

$manifestPath = Join-Path $OutDir 'manifest.json'
$exports | ConvertTo-Json -Depth 3 | Out-File -Encoding utf8 $manifestPath

Write-Host "Done. Wrote exports to: $OutDir" -ForegroundColor Green
Write-Host "Manifest: $manifestPath" -ForegroundColor DarkGray
