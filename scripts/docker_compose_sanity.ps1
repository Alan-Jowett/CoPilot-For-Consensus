# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#
.SYNOPSIS
    Build, launch, and health-check the full docker compose stack, then tear it down.

.DESCRIPTION
    This script cleans existing copilot docker resources (containers, volumes, networks),
    builds all compose images, starts infrastructure and application services, waits for
    them to become healthy, and finally tears everything down with volumes removed.

.PARAMETER TimeoutSeconds
    Maximum time in seconds to wait for all services to report healthy status.

.PARAMETER PollIntervalSeconds
    Delay in seconds between health check polls while waiting for services to become healthy.

.EXAMPLE
    .\scripts\docker_compose_sanity.ps1

.EXAMPLE
    .\scripts\docker_compose_sanity.ps1 -TimeoutSeconds 900 -PollIntervalSeconds 10
#>

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
            } elseif (-not $health -and -not ($state -match '^(?i:up|running)')) {
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

    Write-Host '--- Building images ---' -ForegroundColor Cyan
    docker compose build

    Write-Host '--- Starting infrastructure services ---' -ForegroundColor Cyan
    docker compose up -d documentdb messagebus vectorstore ollama monitoring pushgateway loki grafana promtail

    Write-Host '--- Running infrastructure validators ---' -ForegroundColor Cyan
    docker compose run --rm db-init
    docker compose run --rm db-validate
    docker compose run --rm vectorstore-validate
    docker compose run --rm ollama-validate

    Write-Host '--- Starting application services ---' -ForegroundColor Cyan
    docker compose up -d parsing chunking embedding orchestrator summarization reporting
    Write-Host '--- Checking service health ---' -ForegroundColor Cyan
    Wait-ForHealthy

    Write-Host '--- Running ingestion batch job ---' -ForegroundColor Cyan
    docker compose run --rm ingestion
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Ingestion batch job failed.' -ForegroundColor Red
        throw 'Ingestion service failed with exit code $LASTEXITCODE'
    }
    Write-Host 'Ingestion batch job completed successfully.' -ForegroundColor Green

    Write-Host '--- Sanity pass complete; tearing down ---' -ForegroundColor Cyan
    docker compose down -v
    Write-Host 'Cleanup complete.' -ForegroundColor Green
} finally {
    Pop-Location
}
