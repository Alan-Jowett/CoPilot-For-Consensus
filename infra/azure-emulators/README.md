<!-- SPDX-License-Identifier: MIT -->
<!-- Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Azure Emulators Configuration

This directory contains configuration files for Azure service emulators.

## Files

### servicebus-config.json

Configuration for the Azure Service Bus emulator. Defines queues and topics
for local development and testing.

**Status**: This configuration is intended for **local development only** at this time.
The Service Bus emulator is available in `docker-compose.azure-emulators.yml`
for developers who want to test Service Bus code locally. CI integration tests
will be added in a follow-up PR once the messaging adapter supports Service Bus.

**Why included**: Having the emulator configuration in place enables local
development and testing without waiting for full CI integration.

## Usage

See `docker-compose.azure-emulators.yml` in the repository root and
`docs/LOCAL_DEVELOPMENT.md` for instructions on running Azure emulators locally.
