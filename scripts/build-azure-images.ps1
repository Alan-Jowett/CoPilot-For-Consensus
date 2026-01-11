# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#
.SYNOPSIS
    Build script for Azure-optimized Docker images

.DESCRIPTION
    Builds all Azure-optimized Docker images for Copilot-for-Consensus

.PARAMETER Push
    Push images to registry after building

.PARAMETER Registry
    Custom registry to use (default: ghcr.io/alan-jowett/copilot-for-consensus)

.EXAMPLE
    .\scripts\build-azure-images.ps1
    Build all images locally

.EXAMPLE
    .\scripts\build-azure-images.ps1 -Push -Registry "myregistry.azurecr.io/copilot"
    Build and push images to a custom registry
#>

[CmdletBinding()]
param(
    [switch]$Push,
    [string]$Registry = "ghcr.io/alan-jowett/copilot-for-consensus"
)

$ErrorActionPreference = "Stop"

# Services to build
$services = @(
    "auth",
    "chunking",
    "embedding",
    "ingestion",
    "orchestrator",
    "parsing",
    "reporting",
    "summarization"
)

Write-Host "Building Azure-optimized Docker images..." -ForegroundColor Green
Write-Host "Registry: $Registry" -ForegroundColor Yellow
Write-Host "Push: $Push" -ForegroundColor Yellow
Write-Host ""

function Build-Image {
    param(
        [string]$Service,
        [string]$Context,
        [string]$Dockerfile
    )
    
    Write-Host "Building $Service..." -ForegroundColor Green
    
    $tags = @(
        "${Registry}/${Service}:azure",
        "${Registry}/${Service}:azure-local"
    )
    
    $tagArgs = $tags | ForEach-Object { "--tag", $_ }
    
    try {
        docker build `
            --file $Dockerfile `
            @tagArgs `
            --cache-from "${Registry}/${Service}:azure" `
            $Context
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Built $Service" -ForegroundColor Green
            
            if ($Push) {
                Write-Host "Pushing $Service..." -ForegroundColor Yellow
                foreach ($tag in $tags) {
                    docker push $tag
                }
                Write-Host "✓ Pushed $Service" -ForegroundColor Green
            }
        } else {
            Write-Host "✗ Failed to build $Service" -ForegroundColor Red
            exit 1
        }
    } catch {
        Write-Host "✗ Error building $Service`: $_" -ForegroundColor Red
        exit 1
    }
    
    Write-Host ""
}

# Build main services
foreach ($service in $services) {
    Build-Image -Service $service -Context "." -Dockerfile "$service/Dockerfile.azure"
}

# Build UI
Build-Image -Service "ui" -Context "ui" -Dockerfile "ui/Dockerfile.azure"

# Build gateway
Build-Image -Service "gateway" -Context "infra/nginx" -Dockerfile "infra/nginx/Dockerfile.azure"

Write-Host "All images built successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "To see image sizes, run:"
Write-Host "  docker images | Select-String '$Registry'" -ForegroundColor Cyan
Write-Host ""

if (-not $Push) {
    Write-Host "To push images to registry, run:"
    Write-Host "  .\scripts\build-azure-images.ps1 -Push" -ForegroundColor Cyan
    Write-Host ""
}

# Display summary
Write-Host "Summary:" -ForegroundColor Green
docker images --format "table {{.Repository}}:{{.Tag}}`t{{.Size}}" | Select-String "$Registry.*azure"
