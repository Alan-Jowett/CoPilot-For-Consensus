# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

Param(
    [int]$TimeoutSeconds = 600,
    [int]$PollIntervalSeconds = 5
)

$ErrorActionPreference = 'Stop'
$project = 'copilot-for-consensus'
$root = Split-Path -Parent $PSScriptRoot

function Remove-CopilotContainers {
    $ids = docker ps -a -q --filter "label=com.docker.compose.project=$project"
    if ($ids) {
        Write-Host "Stopping and removing containers: $ids" -ForegroundColor Yellow
        docker rm -f $ids | Out-Null
    } else {
        Write-Host 'No copilot containers to remove.' -ForegroundColor DarkGray
    }
}

function Remove-CopilotVolumes {
    $vols = docker volume ls -q --filter "label=com.docker.compose.project=$project"
    if ($vols) {
        Write-Host "Removing volumes: $vols" -ForegroundColor Yellow
        docker volume rm $vols | Out-Null
    } else {
        Write-Host 'No copilot volumes to remove.' -ForegroundColor DarkGray
    }
}

function Remove-CopilotNetworks {
    $nets = docker network ls -q --filter "label=com.docker.compose.project=$project"
    if ($nets) {
        Write-Host "Removing networks: $nets" -ForegroundColor Yellow
        docker network rm $nets | Out-Null
    } else {
        Write-Host 'No copilot networks to remove.' -ForegroundColor DarkGray
    }
}

function Wait-ForHealthy {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ($true) {
        $statusJson = docker compose ps --format json
        $status = $statusJson | ConvertFrom-Json
        $unhealthy = @()
        foreach ($svc in $status) {
            $health = $svc.Health
            $state = $svc.State
            if ($health -and $health -ne 'healthy') {
                $unhealthy += $svc
            } elseif (-not $health -and $state -ne 'running') {
                $unhealthy += $svc
            }
        }

        if (-not $unhealthy) {
            Write-Host 'All services are healthy.' -ForegroundColor Green
            return
        }

        if ((Get-Date) -gt $deadline) {
            Write-Host 'Health check timed out. Unhealthy services:' -ForegroundColor Red
            $unhealthy | ForEach-Object { Write-Host " - $($_.Service): health=$($_.Health) state=$($_.State)" -ForegroundColor Red }
            throw 'Services did not become healthy in time.'
        }

        Write-Host 'Waiting for services to become healthy...' -ForegroundColor Yellow
        Start-Sleep -Seconds $PollIntervalSeconds
    }
}

Push-Location $root
try {
    Write-Host '--- Cleaning existing copilot resources ---' -ForegroundColor Cyan
    Remove-CopilotContainers
    Remove-CopilotVolumes
    Remove-CopilotNetworks

    Write-Host '--- Building images (no cache) ---' -ForegroundColor Cyan
    docker compose build --no-cache

    Write-Host '--- Starting stack ---' -ForegroundColor Cyan
    docker compose up -d

    Write-Host '--- Checking service health ---' -ForegroundColor Cyan
    Wait-ForHealthy

    Write-Host '--- Sanity pass complete; tearing down ---' -ForegroundColor Cyan
    docker compose down -v
    Write-Host 'Cleanup complete.' -ForegroundColor Green
} finally {
    Pop-Location
}
