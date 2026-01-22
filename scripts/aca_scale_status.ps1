# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#+
.SYNOPSIS
  Show Azure Container Apps active replica counts (scale-to-zero verification).

.DESCRIPTION
  Lists Container Apps in a resource group and summarizes the active revision
  replica counts plus scaling settings (min/max replicas).

  Optionally expands per-replica state via `az containerapp replica list`.

  Requires Azure CLI and access to the resource group.

.EXAMPLE
  ./scripts/aca_scale_status.ps1 -ResourceGroup copilot-app-rg

.EXAMPLE
  ./scripts/aca_scale_status.ps1 -ResourceGroup copilot-app-rg -IncludeReplicas

.EXAMPLE
  ./scripts/aca_scale_status.ps1 -ResourceGroup copilot-app-rg -AllRevisions -AsJson
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$ResourceGroup,

  [switch]$IncludeReplicas,

  [switch]$AllRevisions,

  [int]$MaxApps = 0,

  [switch]$AsJson
)

$ErrorActionPreference = 'Stop'

function Invoke-AzJson {
  param([Parameter(Mandatory = $true)][string[]]$Args)

  # Some PowerShell versions treat native command stderr/exit codes as errors when
  # $ErrorActionPreference = 'Stop'. Temporarily relax it during the call.
  $prevEap = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    $out = ((& az @Args -o json 2>&1) | Out-String)
    $exitCode = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $prevEap
  }

  if ($exitCode -ne 0) {
    throw "Azure CLI call failed: az $($Args -join ' ') -o json`n$out"
  }
  try {
    return $out | ConvertFrom-Json
  } catch {
    throw "Azure CLI returned non-JSON output: az $($Args -join ' ') -o json`n$out"
  }
}

try {
  $apps = @(Invoke-AzJson -Args @('containerapp', 'list', '-g', $ResourceGroup, '--query', '[].name'))
} catch {
  Write-Host "Failed to query container apps. Ensure you're logged in ('az login') and have access. Details: $($_.Exception.Message)" -ForegroundColor Red
  exit 2
}

if (-not $apps -or $apps.Count -eq 0) {
  Write-Error "No Container Apps found in resource group '$ResourceGroup'."
  exit 2
}

if ($MaxApps -gt 0 -and $apps.Count -gt $MaxApps) {
  $apps = @($apps | Select-Object -First $MaxApps)
}

$rows = @()

foreach ($app in $apps) {
  # Note: Azure CLI's JMESPath literal/escaping varies by shell. To keep this
  # script robust on Windows PowerShell, fetch all revisions and filter in PS.
  $revQuery = "[].{revision:name, active:properties.active, replicas:properties.replicas, runningState:properties.runningState, min:properties.template.scale.minReplicas, max:properties.template.scale.maxReplicas}"

  $revisions = @()
  try {
    $revisions = @(Invoke-AzJson -Args @('containerapp', 'revision', 'list', '-g', $ResourceGroup, '-n', $app, '--query', $revQuery))
  } catch {
    $rows += [pscustomobject]@{
      app             = $app
      activeRevisions  = 0
      totalReplicas    = 0
      scaledToZero     = $null
      minReplicas      = $null
      maxReplicas      = $null
      revisionSummary  = $null
      note            = "Failed to list revisions: $($_.Exception.Message)"
    }
    continue
  }

  $revisionsAll = $revisions
  $revisionsActive = @($revisionsAll | Where-Object { $_.active -eq $true })
  if (-not $AllRevisions) {
    $revisionsAll = $revisionsActive
  }
  $activeRevCount = $revisionsActive.Count
  $totalRevCount = $revisionsAll.Count

  $replicaCounts = @(
    $revisionsActive |
      ForEach-Object {
        if ($null -eq $_.replicas) { 0 } else { [int]$_.replicas }
      }
  )
  $totalReplicas = 0
  if ($replicaCounts.Count -gt 0) {
    $totalReplicas = [int](($replicaCounts | Measure-Object -Sum).Sum)
  }

  $mins = @($revisionsActive | ForEach-Object { $_.min } | Where-Object { $_ -ne $null } | Sort-Object -Unique)
  $maxs = @($revisionsActive | ForEach-Object { $_.max } | Where-Object { $_ -ne $null } | Sort-Object -Unique)
  $minText = if ($mins.Count -gt 0) { ($mins -join ',') } else { $null }
  $maxText = if ($maxs.Count -gt 0) { ($maxs -join ',') } else { $null }

  $scaledToZero = $null
  if ($mins.Count -gt 0) {
    $scaledToZero = (($totalReplicas -eq 0) -and ($mins -contains 0))
  }

  $runningReplicas = $null
  if ($IncludeReplicas) {
    $running = 0
    $known = 0

    foreach ($rev in $revisionsActive) {
      $revName = $rev.revision
      $revReplicas = if ($null -eq $rev.replicas) { 0 } else { [int]$rev.replicas }
      if (-not $revName -or $revReplicas -le 0) { continue }

      try {
        $states = @(Invoke-AzJson -Args @(
          'containerapp', 'replica', 'list',
          '-g', $ResourceGroup,
          '-n', $app,
          '--revision', $revName,
          '--query', "[].properties.runningState"
        ))
        foreach ($s in $states) {
          $known += 1
          if ($s -eq 'Running') { $running += 1 }
        }
      } catch {
        # If we can't list replicas, fall back to revision state only.
        continue
      }
    }

    if ($known -gt 0) {
      $runningReplicas = $running
    }
  }

  $revisionSummary = $null
  if ($revisionsAll.Count -gt 0) {
    $revisionSummary = (
      $revisionsAll |
        Sort-Object { $_.revision } |
        ForEach-Object {
          $r = if ($null -eq $_.replicas) { 0 } else { [int]$_.replicas }
          $st = if ($_.runningState) { $_.runningState } else { 'Unknown' }
          if ($AllRevisions) {
            $flag = if ($_.active -eq $true) { 'A' } else { 'I' }
            "$($flag):$($_.revision)=$r ($st)"
          } else {
            "$($_.revision)=$r ($st)"
          }
        }
    ) -join '; '
  }

  $row = [pscustomobject]@{
    app            = $app
    activeRevisions = $activeRevCount
    totalReplicas  = $totalReplicas
    runningReplicas = $runningReplicas
    scaledToZero   = $scaledToZero
    minReplicas    = $minText
    maxReplicas    = $maxText
    revisionSummary = $revisionSummary
    note           = $null
  }

  if ($AllRevisions) {
    $row | Add-Member -NotePropertyName totalRevisions -NotePropertyValue $totalRevCount -Force
  }

  $rows += $row
}

if ($AsJson) {
  $rows | ConvertTo-Json -Depth 8
  exit 0
}

$rows |
  Sort-Object -Property @{ Expression = 'totalReplicas'; Descending = $true }, @{ Expression = 'app'; Descending = $false } |
  Select-Object app, activeRevisions, totalReplicas, runningReplicas, scaledToZero, minReplicas, maxReplicas |
  Format-Table -AutoSize
