# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

param(
    [string]$Registry = "ghcr.io/alan-jowett/copilot-for-consensus",
    [string]$Tag = "alan-jowett",
    [string]$Platform = "linux/amd64",
    [switch]$NoPush,
    [switch]$SkipLogin,
    [string]$BuilderName = "copilotbuilder"
)

$ErrorActionPreference = "Stop"

function Get-CommandOrNull {
    param(
        [Parameter(Mandatory = $true)][string]$Name
    )

    return Get-Command -Name $Name -ErrorAction SilentlyContinue
}

function Login-Ghcr {
    param(
        [Parameter(Mandatory = $true)][string]$RegistryHost
    )

    if ($env:GHCR_USER -and $env:GHCR_TOKEN) {
        $env:GHCR_TOKEN | docker login $RegistryHost -u $env:GHCR_USER --password-stdin | Out-Null
        Assert-LastExitCode "docker login $RegistryHost (GHCR_USER/GHCR_TOKEN)"
        return
    }

    $gh = Get-CommandOrNull -Name "gh"
    if (-not $gh) {
        Write-Host "Missing GHCR credentials and GitHub CLI (gh) is not installed." -ForegroundColor Red
        Write-Host "Either install gh and run 'gh auth login', or set:" -ForegroundColor Yellow
        Write-Host "  `$env:GHCR_USER = '<github-username>'" -ForegroundColor Yellow
        Write-Host "  `$env:GHCR_TOKEN = '<PAT with write:packages>'" -ForegroundColor Yellow
        exit 1
    }

    try {
        $ghUser = & gh api user --jq '.login' 2>$null
        if (-not $ghUser) {
            throw "Unable to determine GitHub user. Is 'gh auth login' complete?"
        }

        $ghToken = & gh auth token 2>$null
        if (-not $ghToken) {
            throw "Unable to retrieve GitHub token. Is 'gh auth login' complete?"
        }

        $ghToken | docker login $RegistryHost --username $ghUser --password-stdin | Out-Null
        Assert-LastExitCode "docker login $RegistryHost (gh auth token)"
    } catch {
        Write-Host "Failed to login to $RegistryHost via GitHub CLI." -ForegroundColor Red
        Write-Host $_ -ForegroundColor DarkGray
        Write-Host "Fix options:" -ForegroundColor Yellow
        Write-Host "  1) Run: gh auth login" -ForegroundColor Yellow
        Write-Host "  2) Or set `$env:GHCR_USER and `$env:GHCR_TOKEN (PAT with write:packages)" -ForegroundColor Yellow
        exit 1
    }
}

function Assert-LastExitCode {
    param(
        [string]$Context
    )

    if ($LASTEXITCODE -ne 0) {
        throw "Command failed (exit $LASTEXITCODE): $Context"
    }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

Write-Host "Using repo root: $repoRoot" -ForegroundColor DarkGray

if (-not $SkipLogin -and -not $NoPush) {
    Login-Ghcr -RegistryHost "ghcr.io"
}

# Ensure buildx builder exists and is selected.
docker buildx create --use --name $BuilderName 2>$null | Out-Null
$null = docker buildx inspect --bootstrap
Assert-LastExitCode "docker buildx inspect --bootstrap"

# Most services need repo-root context because they COPY adapters/ and docs/schemas.
$images = @(
    @{ Name = "auth";          Dockerfile = "auth/Dockerfile.azure";         Context = "." },
    @{ Name = "chunking";      Dockerfile = "chunking/Dockerfile.azure";     Context = "." },
    @{ Name = "embedding";     Dockerfile = "embedding/Dockerfile.azure";    Context = "." },
    @{ Name = "ingestion";     Dockerfile = "ingestion/Dockerfile.azure";    Context = "." },
    @{ Name = "parsing";       Dockerfile = "parsing/Dockerfile.azure";      Context = "." },
    @{ Name = "orchestrator";  Dockerfile = "orchestrator/Dockerfile.azure"; Context = "." },
    @{ Name = "reporting";     Dockerfile = "reporting/Dockerfile.azure";    Context = "." },
    @{ Name = "summarization"; Dockerfile = "summarization/Dockerfile.azure";Context = "." },

    # UI is a standalone Node build; its Dockerfile expects ui/ as the context.
    @{ Name = "ui";            Dockerfile = "ui/Dockerfile.azure";           Context = "ui" },

    # Gateway is nginx; its Dockerfile expects infra/nginx/ as the context.
    @{ Name = "gateway";       Dockerfile = "infra/nginx/Dockerfile.azure";  Context = "infra/nginx" }
)

$pushOrLoad = if ($NoPush) { "--load" } else { "--push" }

Push-Location $repoRoot
try {
    foreach ($img in $images) {
        $full = "$Registry/$($img.Name):$Tag"

        Write-Host "" 
        Write-Host "=== Building $full ===" -ForegroundColor Cyan

        docker buildx build `
            --platform $Platform `
            -t $full `
            -f $img.Dockerfile `
            $img.Context `
            $pushOrLoad

        Assert-LastExitCode "docker buildx build $full"

        if (-not $NoPush) {
            Write-Host "Pushed: $full" -ForegroundColor Green
        } else {
            Write-Host "Built locally (--load): $full" -ForegroundColor Green
        }
    }
}
finally {
    Pop-Location
}

Write-Host "" 
Write-Host "Done." -ForegroundColor Green
