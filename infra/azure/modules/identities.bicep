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

// Named map of principal IDs to avoid fragile index-based references in downstream modules
output identityPrincipalIdsByName object = {
  ingestion: managedIdentities[0].properties.principalId
  parsing: managedIdentities[1].properties.principalId
  chunking: managedIdentities[2].properties.principalId
  embedding: managedIdentities[3].properties.principalId
  orchestrator: managedIdentities[4].properties.principalId
  summarization: managedIdentities[5].properties.principalId
  reporting: managedIdentities[6].properties.principalId
  auth: managedIdentities[7].properties.principalId
  ui: managedIdentities[8].properties.principalId
  gateway: managedIdentities[9].properties.principalId
  openai: managedIdentities[10].properties.principalId
}

// Named map of client IDs (same as principal IDs for user-assigned identities)
// Required for Azure SDK DefaultAzureCredential to detect user-assigned managed identity
output identityClientIdsByName object = {
  ingestion: managedIdentities[0].properties.clientId
  parsing: managedIdentities[1].properties.clientId
  chunking: managedIdentities[2].properties.clientId
  embedding: managedIdentities[3].properties.clientId
  orchestrator: managedIdentities[4].properties.clientId
  summarization: managedIdentities[5].properties.clientId
  reporting: managedIdentities[6].properties.clientId
  auth: managedIdentities[7].properties.clientId
  ui: managedIdentities[8].properties.clientId
  gateway: managedIdentities[9].properties.clientId
  openai: managedIdentities[10].properties.clientId
}

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
  openai: managedIdentities[10].id
}
