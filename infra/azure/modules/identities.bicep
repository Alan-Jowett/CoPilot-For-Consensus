// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to create user-assigned managed identities for all microservices'

param location string
param identityPrefix string
param services array
param tags object

// Create user-assigned managed identity for each service
resource managedIdentities 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = [
  for service in services: {
    name: '${identityPrefix}-${service}-id'
    location: location
    tags: tags
  }
]

// Output all identity details
output identities array = [
  for (service, idx) in services: {
    service: service
    resourceId: managedIdentities[idx].id
    principalId: managedIdentities[idx].properties.principalId
  }
]

output identityPrincipalIds array = [
  for (service, idx) in services: managedIdentities[idx].properties.principalId
]

// IMPORTANT: The order of the services array must not change, as downstream
// modules depend on this specific mapping of service names to identity resource IDs
output identityResourceIds object = {
  ingestion: managedIdentities[0].id
  parsing: managedIdentities[1].id
  chunking: managedIdentities[2].id
  embedding: managedIdentities[3].id
  orchestrator: managedIdentities[4].id
  summarization: managedIdentities[5].id
  reporting: managedIdentities[6].id
  auth: managedIdentities[7].id
  ui: managedIdentities[8].id
  gateway: managedIdentities[9].id
}
