# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#!
.SYNOPSIS
Creates actionable GitHub issues from a mined log report (scripts/log_mining).

.DESCRIPTION
Takes a JSON report produced by `python -m scripts.log_mining` and creates a set
of pre-defined issues based on high-signal templates (errors/warnings) found in
the report. Each issue includes the template count and one or more sample raw
lines to make the issue actionable.

Requires:
- GitHub CLI (`gh`) installed and authenticated for the current repo.

.PARAMETER ReportPath
Path to the mined report JSON (e.g., logs/.../rca_mined.json).

.PARAMETER StorageAccountName
Storage account name used to archive logs (for context only).

.PARAMETER ContainerName
Container name used to archive logs (for context only).

.PARAMETER Lookback
Lookback window used (for context only, e.g. PT6H).

.PARAMETER OutputDir
Directory to write the issue body markdown files before creating issues.

.PARAMETER DryRun
If set, does not create issues; only writes the issue body files.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ReportPath,

    [Parameter(Mandatory = $false)]
    [string]$StorageAccountName = '',

    [Parameter(Mandatory = $false)]
    [string]$ContainerName = '',

    [Parameter(Mandatory = $false)]
    [string]$Lookback = '',

    [Parameter(Mandatory = $true)]
    [string]$OutputDir,

    [Parameter(Mandatory = $false)]
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

function Get-RequiredCommand([string]$Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "Required command not found: $Name"
    }
    return $cmd
}

function Get-TopMatch {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Templates,

        [Parameter(Mandatory = $true)]
        [string]$Needle
    )

    return $Templates |
        Where-Object { $_.template -and ([string]$_.template).Contains($Needle) } |
        Sort-Object count -Descending |
        Select-Object -First 1
}

function Format-TemplateSection {
    param(
        [Parameter(Mandatory = $false)]
        $Template,

        [Parameter(Mandatory = $false)]
        [int]$MaxSamples = 2
    )

    if (-not $Template) {
        return '(no matching template found)'
    }

    $svc = [string]$Template.service
    $cnt = $Template.count
    $id = [string]$Template.template_id
    $tmpl = [string]$Template.template

    $out = New-Object System.Collections.Generic.List[string]
    $out.Add("- service: $svc")
    $out.Add("- count: $cnt")
    $out.Add("- template_id: $id")
    $out.Add("- template: $tmpl")

    $samples = @($Template.samples | Select-Object -First $MaxSamples)
    if ($samples.Count -gt 0) {
        $out.Add('')
        $i = 1
        foreach ($s in $samples) {
            $out.Add("Sample ${i}:")
            $out.Add('```json')
            $out.Add([string]$s)
            $out.Add('```')
            $out.Add('')
            $i += 1
        }
    }

    return ($out -join "`n")
}

Get-RequiredCommand 'gh' | Out-Null

if (-not (Test-Path $ReportPath)) {
    throw "Report not found: $ReportPath"
}

$report = Get-Content -Raw -Path $ReportPath | ConvertFrom-Json
$templates = @($report.templates)

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$contextLines = New-Object System.Collections.Generic.List[string]
$contextLines.Add('Context')
$contextLines.Add('- Source: Blob-archived ACA console logs (Azure Monitor Diagnostic Settings)')
if ($StorageAccountName) { $contextLines.Add("- Storage account: $StorageAccountName") }
if ($ContainerName) { $contextLines.Add("- Container: $ContainerName") }
if ($Lookback) { $contextLines.Add("- Lookback window: $Lookback") }
$contextLines.Add("- Mined report: $ReportPath")
$contextLines.Add("- meta.created_utc: $($report.meta.created_utc)")
$contextLines.Add("- meta.lines_total: $($report.meta.lines_total)")
$contextLines.Add("- meta.templates_total: $($report.meta.templates_total)")
$contextText = ($contextLines -join "`n")

$issues = @(
    @{ key = 'orchestrator-data-inconsistency'
       title = 'orchestrator: repeated "Data inconsistency" warnings (missing chunk_ids / mismatch selected vs retrieved)'
       labels = @('bug','orchestrator','consistency','high')
       intro = @(
           'We are repeatedly logging data consistency warnings indicating the orchestrator selected N chunks but retrieved fewer (often 0), with explicit missing chunk_ids.',
           'This suggests a race/consistency issue between chunk selection and chunk persistence/retrieval, or an eventual-consistency/partitioning bug.',
           'These warnings are high volume and likely correlate with degraded summarization quality or downstream failures.'
       )
       needle = 'Data inconsistency for thread'
       rca = @(
           '- Add/propagate correlation IDs across chunking->vectorstore->orchestrator retrieval paths.',
           '- For one affected thread_id, log selected chunk_ids, the query used to retrieve them, and which store returned 0.',
           '- Confirm whether retrieval is eventually consistent and whether orchestrator retries later succeed.'
       )
    },
    @{ key = 'embedding-invalid-chunksprepared-schema'
       title = 'embedding: ChunksPrepared events failing schema validation (missing required data fields)'
       labels = @('bug','embedding','schema-validation','message-bus','high')
       intro = @(
           "Embedding service logs show repeated schema validation failures for event type 'ChunksPrepared'.",
           "The validator reports required properties missing under 'data' (chunk_count, chunks_ready, chunking_strategy, avg_chunk_size_tokens).",
           'This indicates a publisher is emitting malformed events or using an outdated schema version; it can stall the pipeline.'
       )
       needle = "Validation failed for event type 'ChunksPrepared'"
       rca = @(
           "- Identify publisher of 'ChunksPrepared' and compare payload to schema; block publish if invalid.",
           '- Add unit/integration test that validates event payload at publish-time.'
       )
    },
    @{ key = 'chunking-cosmos-conflict-chunks'
       title = 'chunking: CosmosDB conflicts "Document with id already exists" when storing chunks (idempotency/duplicate processing)'
       labels = @('bug','chunking','database','cosmosdb','high')
       intro = @(
           'Chunking service logs show CosmosDB Conflict errors when storing chunks (document id already exists).',
           'This is likely duplicate processing / missing idempotency guard, or retries re-inserting the same chunk id.',
           'We should ensure chunk writes are idempotent (upsert/replace) or detect duplicates cleanly without throwing and cascading failures.'
       )
       needle = 'already exists in collection chunks'
       rca = @(
           '- Verify chunk ID determinism and whether retries/requeues can double-insert.',
           '- Decide desired semantics: upsert/replace, or skip if exists.',
           '- Add metrics: conflict rate + affected document ids.'
       )
    },
    @{ key = 'parsing-cosmos-conflict-messages'
       title = 'parsing: CosmosDB conflicts "Document with id already exists" when storing messages'
       labels = @('bug','parsing','database','cosmosdb','high')
       intro = @(
           'Parsing service logs show CosmosDB Conflict errors when storing messages (document id already exists).',
           'This can lead to ingestion/parsing failures and repeated retries.',
           'We should confirm the message id generation strategy and apply idempotent writes or dedupe semantics.'
       )
       needle = 'already exists in collection messages'
       rca = @(
           '- Verify message ID determinism and ingestion retry behavior (at-least-once).',
           '- Implement idempotent write or dedupe at store layer.'
       )
    },
    @{ key = 'auth-keyvault-permissions-for-keys'
       title = 'auth: Key Vault key permission errors cause JWKS/signing failures (Forbidden: keys get/sign)'
       labels = @('bug','auth','security','azure','rbac','high')
       intro = @(
           'Auth logs contain Forbidden errors for Key Vault key operations (keys get/sign).',
           'When this occurs, /keys (JWKS) can return 500 and dependent services fail auth.',
           'Track to ensure this cannot regress (post-deploy validation + CI checks).' 
       )
       needle = 'does not have keys get permission'
       rca = @(
           '- Ensure IaC grants key permissions consistently (access-policy mode) and add post-deploy validation.',
           '- Consider a health check that fails if JWKS cannot be served.'
       )
       extraNeedles = @('does not have keys sign permission')
    },
    @{ key = 'jwks-fetch-failures-cross-services'
       title = 'platform: repeated JWKS fetch failures across services (timeouts/connection refused/500)'
       labels = @('bug','authentication','networking','deployment','high')
       intro = @(
           'Multiple services log JWKS fetch failures (ReadTimeout, ConnectError/connection refused, and HTTP 500).',
           'This indicates auth/JWKS instability or startup ordering/readiness problems, or transient networking issues.',
           'We should improve readiness checks, dependency startup sequencing, and/or cache JWKS to avoid widespread auth outages.'
       )
       needle = 'JWKS fetch attempt'
       extraNeedles = @('JWKS fetch failed with HTTP', 'Failed to fetch JWKS after')
       rca = @(
           '- Add readiness gating: services should not start processing until JWKS endpoint is healthy.',
           '- Add caching/backoff improvements and alerting when JWKS is unavailable.'
       )
    },
    @{ key = 'reporting-servicebus-handler-none-flow'
       title = 'reporting: azure-servicebus handler crashes with AttributeError (NoneType has no attribute flow)'
       labels = @('bug','reporting','servicebus','messaging','high')
       intro = @(
           "Reporting logs show azure.servicebus handler shutting down due to AttributeError ('NoneType' object has no attribute 'flow').",
           'This may be a library bug, misuse, or an unexpected state transition; it can drop message processing.',
           'We need the full traceback and azure-servicebus package version to determine mitigation.'
       )
       needle = 'ERROR:azure.servicebus._base_handler:Unexpected error occurred'
       rca = @(
           '- Capture full traceback and record azure-servicebus package version.',
           '- Evaluate upgrading azure-servicebus and adding defensive handling to avoid consumer shutdown.'
       )
    },
    @{ key = 'parsing-legacy-doc-missing-source-type'
       title = 'parsing: high-volume warnings for legacy docs missing source_type (backfill + reduce log noise)'
       labels = @('enhancement','parsing','database','maintenance')
       intro = @(
           "Parsing logs repeatedly warn about archives missing 'source_type' (legacy documents), defaulting to 'local'.",
           'Volume is high and can drown out real signal.',
           'Action: backfill source_type for existing docs (migration) and/or rate-limit/downgrade this log once confirmed safe.'
       )
       needle = "missing 'source_type' field"
       rca = @(
           '- Confirm if source_type is required for downstream behavior; if so, run a migration/backfill.',
           '- Reduce log volume (rate limit or lower severity) after confirmation.'
       )
    }
)

$created = @()

foreach ($issue in $issues) {
    $title = [string]$issue.title
    $key = [string]$issue.key
    $labels = @($issue.labels)

    $t = Get-TopMatch -Templates $templates -Needle ([string]$issue.needle)

    $body = New-Object System.Collections.Generic.List[string]
    $body.Add('## Summary')
    foreach ($line in @($issue.intro)) { $body.Add([string]$line) }
    $body.Add('')
    $body.Add('## Context')
    $body.Add($contextText)
    $body.Add('')
    $body.Add('## Evidence (from mined templates)')
    $body.Add((Format-TemplateSection -Template $t -MaxSamples 2))

    if ($issue.ContainsKey('extraNeedles')) {
        foreach ($n in @($issue.extraNeedles)) {
            $extra = Get-TopMatch -Templates $templates -Needle ([string]$n)
            if ($extra) {
                $body.Add('')
                $body.Add('Additional related template:')
                $body.Add((Format-TemplateSection -Template $extra -MaxSamples 1))
            }
        }
    }

    $body.Add('')
    $body.Add('## What we need to finish RCA')
    foreach ($line in @($issue.rca)) { $body.Add([string]$line) }

    $filePath = Join-Path $OutputDir ("$key.md")
    Set-Content -Path $filePath -Value ($body -join "`n") -Encoding utf8

    if ($DryRun) {
        Write-Host "[DryRun] Wrote: $filePath" -ForegroundColor Yellow
        continue
    }

    $labelArgs = @()
    foreach ($l in $labels) {
        $labelArgs += @('-l', [string]$l)
    }

    Write-Host "Creating issue: $title" -ForegroundColor Cyan
    $url = gh issue create -t $title -F $filePath @labelArgs

    $created += [PSCustomObject]@{ key = $key; url = $url }
}

if (-not $DryRun) {
    Write-Host "\nCreated issues:" -ForegroundColor Green
    $created | Format-Table -AutoSize | Out-String | Write-Host
}
