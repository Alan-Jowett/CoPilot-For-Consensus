// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to assign Cosmos DB Built-in Data Contributor role to service managed identities'

@description('Cosmos DB account name')
param cosmosAccountName string

@description('Principal IDs of managed identities that need Cosmos DB access')
param principalIds array

@description('Cosmos DB Built-in Data Contributor role definition ID')
var cosmosDataContributorRoleId = '00000000-0000-0000-0000-000000000002'

// Reference to existing Cosmos DB account
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-11-15' existing = {
  name: cosmosAccountName
}

// SECURITY NOTE: All services currently receive Cosmos DB Built-in Data Contributor role
// at the account scope, granting read/write access to ALL databases and containers.
// This is broader than necessary - only the auth service requires access to the auth database.
// TODO: Implement per-database/container scoping using custom role definitions to follow
// principle of least privilege. See: https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-setup-rbac
// Cosmos DB RBAC currently doesn't support built-in roles scoped to specific databases/containers;
// custom role definitions with narrower data actions are required for granular access control.

// Assign Cosmos DB Built-in Data Contributor role to each principal
resource roleAssignments 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2023-11-15' = [for (principalId, i) in principalIds: {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, principalId, cosmosDataContributorRoleId)
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosDataContributorRoleId}'
    principalId: principalId
    scope: cosmosAccount.id
  }
}]

@description('Number of role assignments created')
output roleAssignmentCount int = length(principalIds)

@description('Summary of role assignments')
output summary string = 'Assigned Cosmos DB Built-in Data Contributor role to ${length(principalIds)} managed identities'
