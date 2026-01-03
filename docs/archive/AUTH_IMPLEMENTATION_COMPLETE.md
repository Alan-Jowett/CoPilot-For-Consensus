docker compose ps | grep -E "auth|reporting|ui|gateway"
docker compose build ui --no-cache
docker compose restart ui
docker compose logs -f auth --tail=20
docker compose build ui --no-cache
docker compose restart ui
<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Moved: OAuth2 + JWT Authentication – Complete Implementation Guide

This content now lives at [docs/features/authentication.md](../docs/features/authentication.md).
