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
  managedIdentities[0].properties.principalId
  managedIdentities[1].properties.principalId
  managedIdentities[2].properties.principalId
  managedIdentities[3].properties.principalId
  managedIdentities[4].properties.principalId
  managedIdentities[5].properties.principalId
  managedIdentities[6].properties.principalId
  managedIdentities[7].properties.principalId
  managedIdentities[8].properties.principalId
  managedIdentities[9].properties.principalId
]

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
