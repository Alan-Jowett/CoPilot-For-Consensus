# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#
.SYNOPSIS
    Test script to run ingestion service with config.test.yaml and verify it publishes events

.DESCRIPTION
    This script:
    1. Ensures messagebus and monitoring services are running
    2. Builds the ingestion service Docker image
    3. Runs the ingestion service with test configuration
    4. Can optionally monitor RabbitMQ for published events

.PARAMETER Monitor
    If set, will run a Python script to monitor RabbitMQ for events

.EXAMPLE
    .\run_ingestion_test.ps1
    
.EXAMPLE
    .\run_ingestion_test.ps1 -Monitor
#>

param(
    [switch]$Monitor
)

Write-Host "`n==================================================================" -ForegroundColor Cyan
Write-Host "Ingestion Service Integration Test" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# Step 1: Ensure messagebus and monitoring are running
Write-Host "`n[1/4] Checking if messagebus, monitoring, and pushgateway are running..." -ForegroundColor Yellow
$services = docker compose ps --services --filter "status=running"

if ($services -notcontains "messagebus") {
    Write-Host "  Starting messagebus..." -ForegroundColor Yellow
    docker compose up -d messagebus
    Start-Sleep -Seconds 5
}

if ($services -notcontains "monitoring") {
    Write-Host "  Starting monitoring..." -ForegroundColor Yellow
    docker compose up -d monitoring
    Start-Sleep -Seconds 3
}

if ($services -notcontains "pushgateway") {
    Write-Host "  Starting pushgateway..." -ForegroundColor Yellow
    docker compose up -d pushgateway
    Start-Sleep -Seconds 3
}

Write-Host "  ✓ Services are running" -ForegroundColor Green

# Step 2: Build ingestion service
Write-Host "`n[2/4] Building ingestion service..." -ForegroundColor Yellow
docker compose build ingestion
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ Failed to build ingestion service" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Build complete" -ForegroundColor Green

# Step 3: Show RabbitMQ and Prometheus info
Write-Host "`n[3/4] Service Information:" -ForegroundColor Yellow
Write-Host "  RabbitMQ Management: http://localhost:15672 (guest/guest)" -ForegroundColor Cyan
Write-Host "  Prometheus: http://localhost:9090" -ForegroundColor Cyan
Write-Host "  Pushgateway: http://localhost:9091" -ForegroundColor Cyan

$configPath = Join-Path (Get-Location) "ingestion/config.test.yaml"
if (-not (Test-Path $configPath)) {
    Write-Host "  ✗ Config file not found at $configPath" -ForegroundColor Red
    exit 1
}
Write-Host "  Using config: $configPath" -ForegroundColor Cyan

# Step 4: Run ingestion or monitor
if ($Monitor) {
    Write-Host "`n[4/4] Starting event monitor..." -ForegroundColor Yellow
    Write-Host "  The monitor will listen for events for 60 seconds." -ForegroundColor Cyan
    Write-Host "  In another terminal, run:" -ForegroundColor Cyan
    $mountArg = "${configPath}:/app/config.test.yaml:ro"
    Write-Host "    docker compose run --rm -v `"$mountArg`" -e CONFIG_FILE=/app/config.test.yaml ingestion`n" -ForegroundColor White
    
    # Run the Python monitoring script
    python .\ingestion\test_integration.py
} else {
    Write-Host "`n[4/4] Running ingestion service with test configuration..." -ForegroundColor Yellow
    Write-Host "  Config file: ingestion/config.test.yaml" -ForegroundColor Cyan
    Write-Host "  Environment variables:" -ForegroundColor Cyan
    Write-Host "    - RABBITMQ_HOST=messagebus" -ForegroundColor Cyan
    Write-Host "    - METRICS_BACKEND=prometheus_pushgateway" -ForegroundColor Cyan
    Write-Host "    - PROMETHEUS_PUSHGATEWAY=http://pushgateway:9091" -ForegroundColor Cyan
    Write-Host ""
    
    # Run ingestion service with test config
    $mountArg = "${configPath}:/app/config.test.yaml:ro"
    docker compose run --rm `
        -v "$mountArg" `
        -e CONFIG_FILE=/app/config.test.yaml `
        -e MESSAGE_BUS_HOST=messagebus `
        -e MESSAGE_BUS_PORT=5672 `
        -e METRICS_BACKEND=prometheus_pushgateway `
        -e PROMETHEUS_PUSHGATEWAY=http://pushgateway:9091 `
        -e LOG_LEVEL=DEBUG `
        ingestion
    
    Write-Host "`n==================================================================" -ForegroundColor Cyan
    Write-Host "Ingestion Complete!" -ForegroundColor Cyan
    Write-Host "==================================================================" -ForegroundColor Cyan
    Write-Host "`nTo verify events were published:" -ForegroundColor Yellow
    Write-Host "  1. Check RabbitMQ Management UI: http://localhost:15672" -ForegroundColor Cyan
    Write-Host "     - Look for exchanges: 'copilot.events'" -ForegroundColor Cyan
    Write-Host "     - Check queues for messages" -ForegroundColor Cyan
    Write-Host "`n  2. Check Prometheus metrics: http://localhost:9090" -ForegroundColor Cyan
    Write-Host "     - Try query: copilot_ingestion" -ForegroundColor Cyan
    Write-Host "`n  3. Run monitoring script:" -ForegroundColor Cyan
    Write-Host "     .\run_ingestion_test.ps1 -Monitor" -ForegroundColor White
}

Write-Host ""
