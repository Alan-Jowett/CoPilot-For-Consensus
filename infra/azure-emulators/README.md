# Azure Emulators Configuration

This directory contains configuration files for Azure service emulators.

## Files

### servicebus-config.json

Configuration for the Azure Service Bus emulator. Defines queues and topics
for local development and testing.

**Status**: This configuration is defined but **not yet active in CI**.
The Service Bus emulator is available in `docker-compose.azure-emulators.yml`
but integration tests for Service Bus are not yet implemented.

**Future work**: Add Service Bus integration tests to `azure-integration-ci.yml`.

## Usage

See `docker-compose.azure-emulators.yml` in the repository root and
`docs/LOCAL_DEVELOPMENT.md` for instructions on running Azure emulators locally.
