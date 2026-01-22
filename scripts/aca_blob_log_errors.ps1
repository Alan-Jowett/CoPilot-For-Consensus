# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#+
.SYNOPSIS
  Extract "error-ish" Azure Container Apps logs archived to Blob Storage.

.DESCRIPTION
  Discovers Container Apps in a resource group, finds the Container Apps managed
  environment diagnostic settings that archive to a Storage Account, downloads
  the most recent log blobs from Azure Monitor containers, and prints a summary
  of error-ish entries by service.

  This script uses Azure CLI and Entra auth for Storage (`--auth-mode login`).
  You need a data-plane role like "Storage Blob Data Reader" on the storage account.

.EXAMPLE
  ./scripts/aca_blob_log_errors.ps1 -ResourceGroup copilot-app-rg

.EXAMPLE
  ./scripts/aca_blob_log_errors.ps1 -ResourceGroup copilot-app-rg -MaxBlobs 2 -Json -IncludeSamples
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)]
  [string]$ResourceGroup,

  [int]$MaxBlobs = 1,

  [string]$Out = $null,

  [switch]$Json,

  [switch]$IncludeSamples
)

$ErrorActionPreference = 'Stop'

function Invoke-AzJson {
  param([Parameter(Mandatory=$true)][string[]]$Args)

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

function Invoke-Az {
  param([Parameter(Mandatory=$true)][string[]]$Args)

  # Some PowerShell versions treat native command stderr/exit codes as errors when
  # $ErrorActionPreference = 'Stop'. Temporarily relax it during the call.
  $prevEap = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    $out = ((& az @Args 2>&1) | Out-String)
    $exitCode = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $prevEap
  }

  if ($exitCode -ne 0) {
    throw "Azure CLI call failed: az $($Args -join ' ')`n$out"
  }
}

function Get-ResourceNameFromId {
  param([string]$Id)
  if (-not $Id) { return $null }
  $parts = $Id.Trim('/') -split '/'
  return $parts[$parts.Length - 1]
}

function Redact-Text {
  param([string]$Text)
  if (-not $Text) { return $Text }

  $out = $Text
  # Bearer tokens
  $out = [regex]::Replace($out, "(?i)(Authorization\\s*[:=]\\s*Bearer\\s+)\\S+", '$1<REDACTED>')
  $out = [regex]::Replace($out, "(Bearer\\s+)\\S+", '$1<REDACTED>')
  # App Insights connection strings
  $out = [regex]::Replace($out, "(?i)(InstrumentationKey=)[^;\\s]+", '$1<REDACTED>')
  $out = [regex]::Replace($out, "(?i)(IngestionEndpoint=)[^;\\s]+", '$1<REDACTED>')
  $out = [regex]::Replace($out, "(?i)(Authorization=)[^;\\s]+", '$1<REDACTED>')
  # Common key/value secrets
  $out = [regex]::Replace($out, "(?i)\\b(api[_-]?key|token|secret|password)\\b\\s*[:=]\\s*\\S+", '$1=<REDACTED>')
  # Key Vault secret URIs
  $out = [regex]::Replace($out, "(?i)https://[a-z0-9\\-]+\\.vault\\.azure\\.net/secrets/\\S+", '<REDACTED_KV_SECRET_URI>')

  return $out
}

$containers = @('insights-logs-containerappconsolelogs','insights-logs-containerappsystemlogs')

try {
  $envs = Invoke-AzJson -Args @('resource','list','-g',$ResourceGroup,'--resource-type','Microsoft.App/managedEnvironments')
} catch {
  Write-Host "Failed to query managed environments. Ensure you're logged in ('az login') and the resource group exists. Details: $($_.Exception.Message)" -ForegroundColor Red
  exit 2
}
if (-not $envs -or $envs.Count -eq 0) {
  Write-Error "No Container Apps managed environments found in resource group '$ResourceGroup'."
  exit 2
}

try {
  $apps = Invoke-AzJson -Args @('containerapp','list','-g',$ResourceGroup)
} catch {
  Write-Host "Failed to query container apps. Ensure you're logged in ('az login') and have access to the resource group. Details: $($_.Exception.Message)" -ForegroundColor Red
  exit 2
}
$services = @($apps | ForEach-Object { $_.name } | Where-Object { $_ } | Sort-Object -Unique)
if (-not $services -or $services.Count -eq 0) {
  Write-Error "No Container Apps found in resource group '$ResourceGroup'."
  exit 2
}

# Build a regex matching known service names
$serviceRegex = [regex]::new('(?:' + (($services | Sort-Object Length -Descending | ForEach-Object { [regex]::Escape($_) }) -join '|') + ')')

$storageAccounts = New-Object System.Collections.Generic.HashSet[string]
foreach ($env in $envs) {
  $settings = Invoke-AzJson -Args @('monitor','diagnostic-settings','list','--resource',$env.id)
  foreach ($s in $settings) {
    if ($s.storageAccountId) {
      [void]$storageAccounts.Add((Get-ResourceNameFromId -Id $s.storageAccountId))
    }
  }
}

$storageAccounts = @($storageAccounts | ForEach-Object { $_ } | Sort-Object)
if (-not $storageAccounts -or $storageAccounts.Count -eq 0) {
  Write-Error "No environment diagnostic settings with storageAccountId were found. Ensure diagnostics archive to Storage."
  exit 2
}

$timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
if (-not $Out) {
  $temp = $env:TEMP
  if (-not $temp) { $temp = (Get-Location).Path }
  $Out = Join-Path $temp (Join-Path 'aca-blob-errors' $timestamp)
}
New-Item -ItemType Directory -Path $Out -Force | Out-Null

$chosenSa = $null
$blobRefs = @()

foreach ($sa in $storageAccounts) {
  try {
    $refs = @()
    foreach ($c in $containers) {
      $blobs = Invoke-AzJson -Args @('storage','blob','list','--account-name',$sa,'--auth-mode','login','--container-name',$c)
      $cRefs = @(
        $blobs |
          Where-Object { $_.name -and $_.properties.lastModified } |
          Sort-Object { $_.properties.lastModified } |
          Select-Object -Last ([Math]::Max(0,$MaxBlobs)) |
          ForEach-Object {
            [pscustomobject]@{
              storageAccount = $sa
              container      = $c
              name           = $_.name
              lastModified   = $_.properties.lastModified
              size           = $_.properties.contentLength
            }
          }
      )
      $refs += $cRefs
    }

    if ($refs.Count -gt 0) {
      $blobRefs = $refs
      $chosenSa = $sa
      break
    }
  } catch {
    # try next storage account
    continue
  }
}

if (-not $chosenSa -or $blobRefs.Count -eq 0) {
  Write-Error "Unable to list/download blobs via --auth-mode login. Ensure you have 'Storage Blob Data Reader' on the Storage Account."
  exit 3
}

$perService = @{}
foreach ($s in $services) { $perService[$s] = 0 }
$total = 0

foreach ($ref in $blobRefs) {
  $leaf = Split-Path -Leaf $ref.name
  $localName = ($ref.container -replace '[^A-Za-z0-9_.-]','_') + '__' + ($leaf -replace '[^A-Za-z0-9_.-]','_')
  $localPath = Join-Path $Out $localName

  Invoke-Az -Args @(
    'storage','blob','download',
    '--account-name',$ref.storageAccount,
    '--auth-mode','login',
    '--container-name',$ref.container,
    '--name',$ref.name,
    '--file',$localPath,
    '--only-show-errors'
  )

  $jsonParseErrors = 0

  Get-Content -Path $localPath -ErrorAction SilentlyContinue | ForEach-Object {
    $line = $_.Trim()
    if (-not $line) { return }

    try {
      $rec = $line | ConvertFrom-Json
    } catch {
      # Skip corrupted / non-JSON lines; keep processing later lines.
      $script:jsonParseErrors += 1
      return
    }

    $msg = $null
    foreach ($k in @('message','msg','log','Log','Message','RenderedMessage')) {
      if ($rec.PSObject.Properties.Name -contains $k -and $rec.$k) { $msg = [string]$rec.$k; break }
    }
    if (-not $msg -and $rec.properties) {
      foreach ($k in @('message','msg','log','Log','RenderedMessage')) {
        if ($rec.properties.PSObject.Properties.Name -contains $k -and $rec.properties.$k) { $msg = [string]$rec.properties.$k; break }
      }
    }

    $svc = $null
    foreach ($k in @('containerAppName','ContainerAppName','appName','AppName')) {
      if ($rec.PSObject.Properties.Name -contains $k -and $rec.$k) { $svc = [string]$rec.$k; break }
    }
    if (-not $svc -and $rec.properties) {
      foreach ($k in @('containerAppName','ContainerAppName','appName','AppName')) {
        if ($rec.properties.PSObject.Properties.Name -contains $k -and $rec.properties.$k) { $svc = [string]$rec.properties.$k; break }
      }
    }
    if (-not $svc -and $msg) {
      $m = $serviceRegex.Match($msg)
      if ($m.Success) { $svc = $m.Value }
    }
    if (-not $svc) {
      $dump = $line
      $m = $serviceRegex.Match($dump)
      if ($m.Success) { $svc = $m.Value }
    }
    if (-not $svc) { return }

    if ($null -eq $msg) { $msg = '' }
    $low = $msg.ToLowerInvariant()
    $isErrorish = $false
    if ($low -match 'traceback|exception| fatal| crash| error') { $isErrorish = $true }

    if (-not $isErrorish) { return }

    $total += 1
    if (-not $perService.ContainsKey($svc)) { $perService[$svc] = 0 }
    $perService[$svc] = [int]$perService[$svc] + 1

    if ($Json) {
      $outObj = [ordered]@{
        resourceGroup = $ResourceGroup
        storageAccount = $chosenSa
        container = $ref.container
        blob = $ref.name
        service = $svc
      }
      if ($IncludeSamples) {
        $red = Redact-Text -Text $msg
        if ($red.Length -gt 500) { $red = $red.Substring(0, 500) }
        $outObj.message = $red
      }
      $outObj | ConvertTo-Json -Compress
    }
  }

  if ($jsonParseErrors -gt 0) {
    Write-Warning "Skipped $jsonParseErrors invalid JSON lines in $localName."
  }
}

Write-Host "" 
Write-Host "Summary:" 
Write-Host "- resourceGroup: $ResourceGroup" 
Write-Host "- storageAccount: $chosenSa" 
Write-Host "- servicesFound: $($services.Count)" 
Write-Host "- blobsScanned: $($blobRefs.Count) ($((($blobRefs | Select-Object -ExpandProperty container | Sort-Object -Unique) -join ', ')))" 
Write-Host "- totalErrorishRecords: $total" 

$perService.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object {
  if ($_.Value -gt 0) { Write-Host "- $($_.Key): $($_.Value)" }
}

Write-Host "" 
Write-Host "Output directory: $Out" 
