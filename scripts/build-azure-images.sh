#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Build script for Azure-optimized Docker images
# Usage: ./scripts/build-azure-images.sh [--push] [--registry REGISTRY]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
PUSH=false
REGISTRY="ghcr.io/alan-jowett/copilot-for-consensus"

while [[ $# -gt 0 ]]; do
  case $1 in
    --push)
      PUSH=true
      shift
      ;;
    --registry)
      REGISTRY="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [--push] [--registry REGISTRY]"
      echo ""
      echo "Options:"
      echo "  --push              Push images to registry after building"
      echo "  --registry REGISTRY Use custom registry (default: ghcr.io/alan-jowett/copilot-for-consensus)"
      echo "  -h, --help          Show this help message"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

# Services to build
SERVICES=(
  "auth"
  "chunking"
  "embedding"
  "ingestion"
  "orchestrator"
  "parsing"
  "reporting"
  "summarization"
)

# UI and gateway have different contexts
UI_CONTEXT="ui"
GATEWAY_CONTEXT="infra/nginx"

echo -e "${GREEN}Building Azure-optimized Docker images...${NC}"
echo -e "Registry: ${YELLOW}${REGISTRY}${NC}"
echo -e "Push: ${YELLOW}${PUSH}${NC}"
echo ""

# Function to build and optionally push an image
build_image() {
  local service=$1
  local context=$2
  local dockerfile=$3
  
  echo -e "${GREEN}Building ${service}...${NC}"
  
  # Build the image
  docker build \
    --file "$dockerfile" \
    --tag "${REGISTRY}/${service}:azure" \
    --tag "${REGISTRY}/${service}:azure-local" \
    --cache-from "${REGISTRY}/${service}:azure" \
    "$context"
  
  if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Built ${service}${NC}"
    
    # Push if requested
    if [ "$PUSH" = true ]; then
      echo -e "${YELLOW}Pushing ${service}...${NC}"
      docker push "${REGISTRY}/${service}:azure"
      docker push "${REGISTRY}/${service}:azure-local"
      echo -e "${GREEN}✓ Pushed ${service}${NC}"
    fi
  else
    echo -e "${RED}✗ Failed to build ${service}${NC}"
    return 1
  fi
  
  echo ""
}

# Build main services
for service in "${SERVICES[@]}"; do
  build_image "$service" "." "${service}/Dockerfile.azure"
done

# Build UI
build_image "ui" "$UI_CONTEXT" "${UI_CONTEXT}/Dockerfile.azure"

# Build gateway
build_image "gateway" "$GATEWAY_CONTEXT" "${GATEWAY_CONTEXT}/Dockerfile.azure"

echo -e "${GREEN}All images built successfully!${NC}"
echo ""
echo "To see image sizes, run:"
echo "  docker images | grep '${REGISTRY}'"
echo ""

if [ "$PUSH" = false ]; then
  echo "To push images to registry, run:"
  echo "  $0 --push"
  echo ""
fi

# Display summary
echo -e "${GREEN}Summary:${NC}"
docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}" | grep "${REGISTRY}" | grep "azure"
