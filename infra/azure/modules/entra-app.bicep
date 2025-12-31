// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to create Microsoft Entra (Azure AD) app registration for OAuth authentication using deployment script'
metadata author = 'Copilot-for-Consensus Team'

@description('Display name for the Entra app registration')
param appName string

@description('Location for deployment script resources')
param location string

@description('Microsoft Entra tenant ID')
param tenantId string

@description('Redirect URIs for OAuth callbacks (web platform)')
param redirectUris array

@description('Environment name for resource tagging')
param environment string

@description('Tags to apply to resources')
param tags object = {}

@description('Client secret expiration in days')
@minValue(30)
@maxValue(730)
param secretExpirationDays int = 365

@description('User-assigned managed identity resource ID with Graph API permissions')
param deploymentIdentityId string

// Note: The deployment identity specified by deploymentIdentityId must have the following
// Microsoft Graph API application permissions (not delegated):
// - Application.ReadWrite.All (for creating/updating app registration)
// - Directory.ReadWrite.All (for creating service principal)
//
// These permissions must be granted by a Global Administrator or Privileged Role Administrator
// using Azure Portal or CLI before running this deployment.

// Create or update Entra App Registration using Azure CLI in deployment script
// This approach is more reliable than the Microsoft.Graph provider which is in preview
resource appRegistrationScript 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: 'create-entra-app-${environment}'
  location: location
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${deploymentIdentityId}': {}
    }
  }
  properties: {
    azCliVersion: '2.55.0'
    timeout: 'PT10M'
    retentionInterval: 'P1D'
    cleanupPreference: 'OnSuccess'
    environmentVariables: [
      {
        name: 'APP_NAME'
        value: appName
      }
      {
        name: 'TENANT_ID'
        value: tenantId
      }
      {
        name: 'REDIRECT_URIS'
        value: join(redirectUris, ',')
      }
      {
        name: 'ENVIRONMENT'
        value: environment
      }
      {
        name: 'SECRET_EXPIRATION_DAYS'
        value: string(secretExpirationDays)
      }
    ]
    scriptContent: '''
      #!/bin/bash
      set -e
      
      # Install jq for JSON parsing
      apk add --no-cache jq
      
      # Convert comma-separated redirect URIs to JSON array
      IFS=',' read -ra URI_ARRAY <<< "$REDIRECT_URIS"
      REDIRECT_URIS_JSON="["
      for i in "${!URI_ARRAY[@]}"; do
        if [ $i -gt 0 ]; then
          REDIRECT_URIS_JSON+=","
        fi
        REDIRECT_URIS_JSON+="\"${URI_ARRAY[$i]}\""
      done
      REDIRECT_URIS_JSON+="]"
      
      echo "Creating or updating Entra app: $APP_NAME"
      echo "Redirect URIs: $REDIRECT_URIS_JSON"
      
      # Check if app already exists
      EXISTING_APP=$(az ad app list --display-name "$APP_NAME" --query "[0]" -o json || echo "{}")
      
      if [ "$(echo "$EXISTING_APP" | jq -r '.appId // empty')" != "" ]; then
        # Update existing app
        APP_ID=$(echo "$EXISTING_APP" | jq -r '.appId')
        OBJECT_ID=$(echo "$EXISTING_APP" | jq -r '.id')
        echo "Updating existing app with ID: $APP_ID"
        
        # Update redirect URIs
        az ad app update --id "$APP_ID" \
          --web-redirect-uris $REDIRECT_URIS \
          --enable-id-token-issuance true
        
      else
        # Create new app
        echo "Creating new app registration..."
        
        # Create app with redirect URIs
        NEW_APP=$(az ad app create \
          --display-name "$APP_NAME" \
          --sign-in-audience AzureADMyOrg \
          --web-redirect-uris $REDIRECT_URIS \
          --enable-id-token-issuance true \
          --required-resource-accesses '[
            {
              "resourceAppId": "00000003-0000-0000-c000-000000000000",
              "resourceAccess": [
                {"id": "e1fe6dd8-ba31-4d61-89e7-88639da4683d", "type": "Scope"},
                {"id": "37f7f235-527c-4136-accd-4a02d197296e", "type": "Scope"},
                {"id": "14dad69e-099b-42c9-810b-d002981feec1", "type": "Scope"},
                {"id": "64a6cdd6-aab1-4aaf-94b8-3cc8405e90d0", "type": "Scope"}
              ]
            }
          ]' -o json)
        
        APP_ID=$(echo "$NEW_APP" | jq -r '.appId')
        OBJECT_ID=$(echo "$NEW_APP" | jq -r '.id')
        echo "Created app with ID: $APP_ID"
        
        # Create service principal
        SP_RESULT=$(az ad sp create --id "$APP_ID" -o json || echo "{}")
        SP_ID=$(echo "$SP_RESULT" | jq -r '.id // empty')
        if [ -z "$SP_ID" ]; then
          # Service principal may already exist
          SP_ID=$(az ad sp list --filter "appId eq '$APP_ID'" --query "[0].id" -o tsv)
        fi
        echo "Service principal ID: $SP_ID"
      fi
      
      # Generate or rotate client secret
      echo "Generating client secret..."
      EXPIRATION_DATE=$(date -u -d "+${SECRET_EXPIRATION_DAYS} days" +"%Y-%m-%dT%H:%M:%SZ")
      SECRET_RESULT=$(az ad app credential reset \
        --id "$APP_ID" \
        --display-name "Primary Secret - Created by Bicep" \
        --end-date "$EXPIRATION_DATE" \
        -o json)
      
      CLIENT_SECRET=$(echo "$SECRET_RESULT" | jq -r '.password')
      SECRET_KEY_ID=$(echo "$SECRET_RESULT" | jq -r '.keyId // empty')
      
      # Get service principal ID if not set
      if [ -z "$SP_ID" ]; then
        SP_ID=$(az ad sp list --filter "appId eq '$APP_ID'" --query "[0].id" -o tsv)
      fi
      
      # Output results as JSON
      jq -n \
        --arg appId "$APP_ID" \
        --arg objectId "$OBJECT_ID" \
        --arg tenantId "$TENANT_ID" \
        --arg clientSecret "$CLIENT_SECRET" \
        --arg secretKeyId "$SECRET_KEY_ID" \
        --arg secretExpirationDate "$EXPIRATION_DATE" \
        --arg servicePrincipalId "$SP_ID" \
        '{
          clientId: $appId,
          objectId: $objectId,
          tenantId: $tenantId,
          clientSecret: $clientSecret,
          secretKeyId: $secretKeyId,
          secretExpirationDate: $secretExpirationDate,
          servicePrincipalId: $servicePrincipalId
        }' > $AZ_SCRIPTS_OUTPUT_PATH
      
      echo "App registration completed successfully"
    '''
  }
  tags: tags
}

// Outputs from deployment script
@description('Application (client) ID')
output clientId string = appRegistrationScript.properties.outputs.clientId

@description('Tenant ID')
output tenantId string = appRegistrationScript.properties.outputs.tenantId

@description('Application object ID')
output objectId string = appRegistrationScript.properties.outputs.objectId

@description('Service principal object ID')
output servicePrincipalId string = appRegistrationScript.properties.outputs.servicePrincipalId

@description('Client secret value (sensitive - store in Key Vault immediately)')
output clientSecret string = appRegistrationScript.properties.outputs.clientSecret

@description('Client secret key ID for rotation tracking')
output secretKeyId string = appRegistrationScript.properties.outputs.secretKeyId

@description('Client secret expiration date')
output secretExpirationDate string = appRegistrationScript.properties.outputs.secretExpirationDate
