
# File: Cancel-All-GitHubRuns.ps1
<#
.SYNOPSIS
  Obtains a GitHub token and cancels all queued/in-progress Actions runs for a repo.
  Uses normal cancel; then force-cancel for stuck runs.

.PARAMETER Owner
  GitHub owner/org. Example: "Alan-Jowett"

.PARAMETER Repo
  GitHub repository name. Example: "CoPilot-For-Consensus"

.PARAMETER Token
  Optional. If omitted, tries `gh auth token`; otherwise securely prompts for a PAT.

.PARAMETER IncludeQueued
  Also cancel queued runs (default: $true)

.PARAMETER DryRun
  Print what would be cancelled without making API calls (default: $false)

.PARAMETER Workflows
  Optional list of workflow names to limit cancellation (exact match). If omitted, cancels all.

.REQUIREMENTS
  PowerShell 7+
  Internet access
  Optional: GitHub CLI (`gh`) for automatic token retrieval

.NOTES
  The script first attempts normal cancellation, then force-cancel for robustness.
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)] [string] $Owner,
  [Parameter(Mandatory = $true)] [string] $Repo,
  [string] $Token,
  [bool]   $IncludeQueued = $true,
  [bool]   $DryRun = $false,
  [string[]] $Workflows
)

$ErrorActionPreference = 'Stop'

# ---------------------------
# Config / constants
# ---------------------------
$ApiBase = "https://api.github.com"
$ApiVersionHeader = "2022-11-28"   # current stable as of 2025
$UserAgent = "Cancel-All-GitHubRuns-PS/1.1"

# ---------------------------
# Helpers
# ---------------------------
function Write-Info { param([string]$m) Write-Host $m -ForegroundColor Cyan }
function Write-Warn { param([string]$m) Write-Host $m -ForegroundColor Yellow }
function Write-Err  { param([string]$m) Write-Host $m -ForegroundColor Red }

function Get-GitHubToken {
  param([string] $TokenIn)

  if ($TokenIn) { return $TokenIn }

  # Try gh CLI if present
  $gh = Get-Command gh -ErrorAction SilentlyContinue
  if ($gh) {
    try {
      Write-Info "Using GitHub CLI to retrieve token (gh auth token)..."
      $t = & $gh.Source auth token 2>$null
      if ($t -and $t.Trim().Length -gt 0) { return $t.Trim() }
      Write-Warn "gh CLI is installed but no token was returned; try 'gh auth login'."
    } catch {
      Write-Warn "Unable to read token from gh CLI: $($_.Exception.Message)"
    }
  }

  # Fallback: secure prompt for a PAT
  Write-Info "Opening GitHub token page in your browser..."
  try { Start-Process "https://github.com/settings/tokens?type=beta" | Out-Null } catch { }

  Write-Warn "Create a fine-grained PAT with 'Actions: Read & Write' for the target repository."
  $secure = Read-Host "Paste your GitHub Personal Access Token (PAT)" -AsSecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    if (-not $plain) { throw "Empty token provided." }
    return $plain
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
  }
}

function Invoke-GitHubApi {
  param(
    [Parameter(Mandatory=$true)][ValidateSet('GET','POST','PATCH','PUT','DELETE')] [string] $Method,
    [Parameter(Mandatory=$true)][string] $Uri,
    [Parameter()][hashtable] $Headers,
    [Parameter()][object] $Body,
    [int] $Retry = 3
  )

  $commonHeaders = @{
    "Accept" = "application/vnd.github+json"
    "Authorization" = "Bearer $script:Token"
    "X-GitHub-Api-Version" = $ApiVersionHeader
    "User-Agent" = $UserAgent
  }
  if ($Headers) { $commonHeaders += $Headers }

  if ($DryRun) {
    Write-Info "[DRYRUN] $Method $Uri"
    return $null
  }

  for ($i=0; $i -lt $Retry; $i++) {
    try {
      if ($Body) {
        return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $commonHeaders -Body ($Body | ConvertTo-Json) -ContentType "application/json"
      } else {
        return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $commonHeaders
      }
    } catch {
      $status = $_.Exception.Response.StatusCode.Value__ 2>$null
      $msg = $_.Exception.Message
      if ($status -eq 429 -or $status -eq 502 -or $status -eq 503) {
        $backoff = [Math]::Pow(2, $i) * 2
        Write-Warn "API $status, retrying in ${backoff}s... ($msg)"
        Start-Sleep -Seconds [int]$backoff
        continue
      }
      throw
    }
  }
}

function Get-WorkflowIdByName {
  param([string] $Name)

  $uri = "$ApiBase/repos/$Owner/$Repo/actions/workflows?per_page=100"
  $r = Invoke-GitHubApi -Method GET -Uri $uri
  if (-not $r) { return $null }
  $wf = $r.workflows | Where-Object { $_.name -eq $Name } | Select-Object -First 1
  return $wf.id
}

function Get-AllRuns {
  param([string] $Status, [int[]] $WorkflowIds)

  $runs = @()
  $page = 1
  $perPage = 100

  while ($true) {
    $uri = "$ApiBase/repos/$Owner/$Repo/actions/runs?status=$Status&per_page=$perPage&page=$page"
    $resp = Invoke-GitHubApi -Method GET -Uri $uri
    if (-not $resp) { break }

    $chunk = $resp.workflow_runs
    if ($chunk -and $chunk.Count -gt 0) {
      # Filter by specific workflow IDs (if provided)
      if ($WorkflowIds -and $WorkflowIds.Count -gt 0) {
        $chunk = $chunk | Where-Object { $WorkflowIds -contains $_.workflow_id }
      }
      $runs += $chunk
      if ($chunk.Count -lt $perPage) { break }
      $page++
    } else {
      break
    }
  }
  return $runs
}

function Cancel-Run {
  param(
    [Parameter(Mandatory=$true)][long] $RunId,
    [string] $Display
  )

  # Normal cancel
  $cancelUri = "$ApiBase/repos/$Owner/$Repo/actions/runs/$RunId/cancel"
  Write-Info "⏳ Cancelling run $RunId ($Display) via standard cancel..."
  try { Invoke-GitHubApi -Method POST -Uri $cancelUri | Out-Null } catch { Write-Warn "Standard cancel failed: $($_.Exception.Message)" }

  Start-Sleep -Seconds 2

  # Force-cancel (for stuck runs)
  $forceUri = "$ApiBase/repos/$Owner/$Repo/actions/runs/$RunId/force-cancel"
  Write-Info "🛑 Force-cancelling run $RunId ($Display)..."
  try { Invoke-GitHubApi -Method POST -Uri $forceUri | Out-Null } catch { Write-Warn "Force-cancel attempt failed: $($_.Exception.Message)" }

  # Verify
  Start-Sleep -Seconds 3
  $statusUri = "$ApiBase/repos/$Owner/$Repo/actions/runs/$RunId"
  try {
    $s = Invoke-GitHubApi -Method GET -Uri $statusUri
    if ($s) {
      Write-Info ("➡ Status after cancel: {0}, Conclusion: {1}" -f $s.status, $s.conclusion)
    }
  } catch {
    Write-Warn "Verification read failed: $($_.Exception.Message)"
  }
}

# ---------------------------
# Main
# ---------------------------
$script:Token = Get-GitHubToken -TokenIn $Token
if (-not $script:Token) { throw "No GitHub token available." }

# Resolve workflows filter -> IDs
$wfIds = @()
if ($Workflows -and $Workflows.Count -gt 0) {
  foreach ($name in $Workflows) {
    $id = Get-WorkflowIdByName -Name $name
    if ($id) {
      Write-Info "Workflow '$name' => id $id"
      $wfIds += [int]$id
    } else {
      Write-Warn "Workflow '$name' not found; it will be skipped."
    }
  }
  if ($wfIds.Count -eq 0) {
    Write-Warn "No workflow IDs resolved from provided names; continuing without workflow filter."
  }
}

Write-Info "🔍 Listing in-progress runs..."
$inProgress = Get-AllRuns -Status "in_progress" -WorkflowIds $wfIds
Write-Info ("Found {0} in-progress run(s)" -f $inProgress.Count)

$queued = @()
if ($IncludeQueued) {
  Write-Info "🔍 Listing queued runs..."
  $queued = Get-AllRuns -Status "queued" -WorkflowIds $wfIds
  Write-Info ("Found {0} queued run(s)" -f $queued.Count)
}

$targets = @()
$targets += $inProgress
$targets += $queued

if ($targets.Count -eq 0) {
  Write-Info "✅ No runs to cancel."
  exit 0
}

foreach ($r in $targets) {
  $name   = $r.name
  $branch = $r.head_branch

  # Robust Int64 parsing for run IDs (string or numeric)
  $runIdStr = "$($r.id)"
  try {
    $runId = [Int64]::Parse($runIdStr)
  } catch {
    Write-Err "Failed to parse run id '$runIdStr' as Int64: $($_.Exception.Message)"
    continue
  }

   Cancel-Run -RunId $runId -Display "$name @ $branch"
}

