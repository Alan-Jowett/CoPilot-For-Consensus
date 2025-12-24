#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Azure API Management adapter for gateway configuration.

This adapter generates Azure Resource Manager (ARM) templates and Bicep
configurations for deploying the Copilot-for-Consensus API via Azure API Management.
"""

import json
from pathlib import Path
from typing import Any, Dict

from adapter_base import GatewayAdapter


class AzureAdapter(GatewayAdapter):
    """Adapter for Azure API Management (APIM).
    
    Generates:
    - ARM template (JSON) with API Management service configuration
    - Parameters file for customization
    - Bicep template (optional, for infrastructure-as-code)
    - Policy XML files for rate limiting, authentication, CORS
    """
    
    @property
    def provider_name(self) -> str:
        return "azure"
    
    @property
    def deployment_instructions(self) -> str:
        return """
Azure API Management Deployment Instructions:
============================================

Prerequisites:
- Azure CLI installed and configured (az login)
- Azure subscription with appropriate permissions
- Resource group created for deployment

Deployment Steps:

1. Review and customize parameters:
   Edit azure-apim-parameters.json to set:
   - apimServiceName (must be globally unique)
   - location (e.g., eastus, westeurope)
   - backendServiceUrls (URLs of your backend services)
   - publisherEmail and publisherName

2. Validate the template:
   az deployment group validate \\
     --resource-group <your-resource-group> \\
     --template-file azure-apim-template.json \\
     --parameters azure-apim-parameters.json

3. Deploy to Azure:
   az deployment group create \\
     --resource-group <your-resource-group> \\
     --template-file azure-apim-template.json \\
     --parameters azure-apim-parameters.json \\
     --name copilot-apim-deployment

4. Wait for deployment (APIM provisioning takes 30-45 minutes)
   
5. Get the gateway URL:
   az apim show \\
     --resource-group <your-resource-group> \\
     --name <apimServiceName> \\
     --query gatewayUrl -o tsv

6. Test the deployment:
   curl https://<gateway-url>/reporting/health

For Bicep deployment (alternative):
   az deployment group create \\
     --resource-group <your-resource-group> \\
     --template-file azure-apim.bicep \\
     --parameters azure-apim-parameters.json

Monitoring:
- Navigate to Azure Portal → API Management → your APIM instance
- View Analytics, Metrics, and Logs
- Configure Application Insights for detailed telemetry
"""
    
    def load_spec(self) -> None:
        """Load the OpenAPI specification from YAML file."""
        import yaml
        
        with open(self.openapi_spec_path, 'r') as f:
            self.openapi_spec = yaml.safe_load(f)
    
    def validate_spec(self) -> bool:
        """Validate OpenAPI spec for Azure APIM compatibility."""
        required_fields = ['openapi', 'info', 'paths']
        for field in required_fields:
            if field not in self.openapi_spec:
                raise ValueError(f"OpenAPI spec missing required field: {field}")
        
        # Check OpenAPI version (APIM supports 2.0 and 3.0)
        version = self.openapi_spec.get('openapi', '')
        if not (version.startswith('3.') or version.startswith('2.')):
            raise ValueError(f"Azure APIM requires OpenAPI 2.x or 3.x, got {version}")
        
        return True
    
    def generate_config(self, output_dir: Path) -> Dict[str, Path]:
        """Generate Azure APIM configuration files."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate ARM template
        arm_template = self._generate_arm_template()
        arm_template_path = output_dir / "azure-apim-template.json"
        with open(arm_template_path, 'w') as f:
            json.dump(arm_template, f, indent=2)
        
        # Generate parameters file
        parameters = self._generate_parameters()
        parameters_path = output_dir / "azure-apim-parameters.json"
        with open(parameters_path, 'w') as f:
            json.dump(parameters, f, indent=2)
        
        # Generate Bicep template
        bicep = self._generate_bicep_template()
        bicep_path = output_dir / "azure-apim.bicep"
        with open(bicep_path, 'w') as f:
            f.write(bicep)
        
        # Generate policy files
        policies_dir = output_dir / "policies"
        policies_dir.mkdir(exist_ok=True)
        
        cors_policy_path = policies_dir / "cors-policy.xml"
        with open(cors_policy_path, 'w') as f:
            f.write(self._generate_cors_policy())
        
        rate_limit_policy_path = policies_dir / "rate-limit-policy.xml"
        with open(rate_limit_policy_path, 'w') as f:
            f.write(self._generate_rate_limit_policy())
        
        jwt_policy_path = policies_dir / "jwt-validation-policy.xml"
        with open(jwt_policy_path, 'w') as f:
            f.write(self._generate_jwt_policy())
        
        return {
            "arm_template": arm_template_path,
            "parameters": parameters_path,
            "bicep": bicep_path,
            "cors_policy": cors_policy_path,
            "rate_limit_policy": rate_limit_policy_path,
            "jwt_policy": jwt_policy_path
        }
    
    def validate_config(self, config_files: Dict[str, Path]) -> bool:
        """Validate generated Azure configuration files."""
        # Check that all files exist
        for file_path in config_files.values():
            if not file_path.exists():
                raise ValueError(f"Generated file does not exist: {file_path}")
        
        # Validate ARM template JSON structure
        arm_template_path = config_files.get("arm_template")
        if arm_template_path:
            with open(arm_template_path, 'r') as f:
                arm_template = json.load(f)
                required_arm_fields = ['$schema', 'contentVersion', 'parameters', 'resources']
                for field in required_arm_fields:
                    if field not in arm_template:
                        raise ValueError(f"ARM template missing required field: {field}")
        
        return True
    
    def _generate_arm_template(self) -> Dict[str, Any]:
        """Generate Azure Resource Manager (ARM) template for APIM."""
        info = self.openapi_spec.get('info', {})
        
        return {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "contentVersion": "1.0.0.0",
            "parameters": {
                "apimServiceName": {
                    "type": "string",
                    "metadata": {
                        "description": "Name of the API Management service (must be globally unique)"
                    }
                },
                "location": {
                    "type": "string",
                    "defaultValue": "[resourceGroup().location]",
                    "metadata": {
                        "description": "Azure region for deployment"
                    }
                },
                "publisherEmail": {
                    "type": "string",
                    "metadata": {
                        "description": "Publisher email for API Management"
                    }
                },
                "publisherName": {
                    "type": "string",
                    "metadata": {
                        "description": "Publisher organization name"
                    }
                },
                "sku": {
                    "type": "string",
                    "defaultValue": "Developer",
                    "allowedValues": ["Developer", "Standard", "Premium"],
                    "metadata": {
                        "description": "API Management pricing tier"
                    }
                },
                "skuCapacity": {
                    "type": "int",
                    "defaultValue": 1,
                    "metadata": {
                        "description": "Number of scale units"
                    }
                },
                "backendReportingUrl": {
                    "type": "string",
                    "metadata": {
                        "description": "Backend URL for reporting service"
                    }
                },
                "backendIngestionUrl": {
                    "type": "string",
                    "metadata": {
                        "description": "Backend URL for ingestion service"
                    }
                },
                "backendAuthUrl": {
                    "type": "string",
                    "metadata": {
                        "description": "Backend URL for auth service"
                    }
                }
            },
            "variables": {
                "apiName": "copilot-for-consensus-api",
                "apiVersion": info.get('version', '0.1.0')
            },
            "resources": [
                {
                    "type": "Microsoft.ApiManagement/service",
                    "apiVersion": "2021-08-01",
                    "name": "[parameters('apimServiceName')]",
                    "location": "[parameters('location')]",
                    "sku": {
                        "name": "[parameters('sku')]",
                        "capacity": "[parameters('skuCapacity')]"
                    },
                    "properties": {
                        "publisherEmail": "[parameters('publisherEmail')]",
                        "publisherName": "[parameters('publisherName')]"
                    }
                },
                {
                    "type": "Microsoft.ApiManagement/service/apis",
                    "apiVersion": "2021-08-01",
                    "name": "[concat(parameters('apimServiceName'), '/', variables('apiName'))]",
                    "dependsOn": [
                        "[resourceId('Microsoft.ApiManagement/service', parameters('apimServiceName'))]"
                    ],
                    "properties": {
                        "displayName": info.get('title', 'Copilot-for-Consensus API'),
                        "description": info.get('description', ''),
                        "path": "",
                        "protocols": ["https"],
                        "subscriptionRequired": True,
                        "format": "openapi+json",
                        "value": json.dumps(self.openapi_spec)
                    }
                },
                {
                    "type": "Microsoft.ApiManagement/service/backends",
                    "apiVersion": "2021-08-01",
                    "name": "[concat(parameters('apimServiceName'), '/reporting-backend')]",
                    "dependsOn": [
                        "[resourceId('Microsoft.ApiManagement/service', parameters('apimServiceName'))]"
                    ],
                    "properties": {
                        "protocol": "http",
                        "url": "[parameters('backendReportingUrl')]"
                    }
                },
                {
                    "type": "Microsoft.ApiManagement/service/backends",
                    "apiVersion": "2021-08-01",
                    "name": "[concat(parameters('apimServiceName'), '/ingestion-backend')]",
                    "dependsOn": [
                        "[resourceId('Microsoft.ApiManagement/service', parameters('apimServiceName'))]"
                    ],
                    "properties": {
                        "protocol": "http",
                        "url": "[parameters('backendIngestionUrl')]"
                    }
                },
                {
                    "type": "Microsoft.ApiManagement/service/backends",
                    "apiVersion": "2021-08-01",
                    "name": "[concat(parameters('apimServiceName'), '/auth-backend')]",
                    "dependsOn": [
                        "[resourceId('Microsoft.ApiManagement/service', parameters('apimServiceName'))]"
                    ],
                    "properties": {
                        "protocol": "http",
                        "url": "[parameters('backendAuthUrl')]"
                    }
                }
            ],
            "outputs": {
                "apimGatewayUrl": {
                    "type": "string",
                    "value": "[reference(resourceId('Microsoft.ApiManagement/service', parameters('apimServiceName'))).gatewayUrl]"
                }
            }
        }
    
    def _generate_parameters(self) -> Dict[str, Any]:
        """Generate parameters file for ARM template."""
        return {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
            "contentVersion": "1.0.0.0",
            "parameters": {
                "apimServiceName": {
                    "value": "copilot-apim-REPLACE_WITH_UNIQUE_SUFFIX"
                },
                "publisherEmail": {
                    "value": "admin@example.com"
                },
                "publisherName": {
                    "value": "Copilot for Consensus"
                },
                "sku": {
                    "value": "Developer"
                },
                "skuCapacity": {
                    "value": 1
                },
                "backendReportingUrl": {
                    "value": "https://your-backend-reporting-service.azurewebsites.net"
                },
                "backendIngestionUrl": {
                    "value": "https://your-backend-ingestion-service.azurewebsites.net"
                },
                "backendAuthUrl": {
                    "value": "https://your-backend-auth-service.azurewebsites.net"
                }
            }
        }
    
    def _generate_bicep_template(self) -> str:
        """Generate Bicep template (infrastructure as code)."""
        info = self.openapi_spec.get('info', {})
        
        return f"""// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

// Azure API Management deployment for Copilot-for-Consensus
// Generated from OpenAPI specification

@description('Name of the API Management service (must be globally unique)')
param apimServiceName string

@description('Azure region for deployment')
param location string = resourceGroup().location

@description('Publisher email for API Management')
param publisherEmail string

@description('Publisher organization name')
param publisherName string

@description('API Management pricing tier')
@allowed(['Developer', 'Standard', 'Premium'])
param sku string = 'Developer'

@description('Number of scale units')
param skuCapacity int = 1

@description('Backend URL for reporting service')
param backendReportingUrl string

@description('Backend URL for ingestion service')
param backendIngestionUrl string

@description('Backend URL for auth service')
param backendAuthUrl string

var apiName = 'copilot-for-consensus-api'
var apiVersion = '{info.get('version', '0.1.0')}'

// API Management Service
resource apimService 'Microsoft.ApiManagement/service@2021-08-01' = {{
  name: apimServiceName
  location: location
  sku: {{
    name: sku
    capacity: skuCapacity
  }}
  properties: {{
    publisherEmail: publisherEmail
    publisherName: publisherName
  }}
}}

// Backend services
resource reportingBackend 'Microsoft.ApiManagement/service/backends@2021-08-01' = {{
  parent: apimService
  name: 'reporting-backend'
  properties: {{
    protocol: 'http'
    url: backendReportingUrl
  }}
}}

resource ingestionBackend 'Microsoft.ApiManagement/service/backends@2021-08-01' = {{
  parent: apimService
  name: 'ingestion-backend'
  properties: {{
    protocol: 'http'
    url: backendIngestionUrl
  }}
}}

resource authBackend 'Microsoft.ApiManagement/service/backends@2021-08-01' = {{
  parent: apimService
  name: 'auth-backend'
  properties: {{
    protocol: 'http'
    url: backendAuthUrl
  }}
}}

// API definition (import from OpenAPI spec)
resource api 'Microsoft.ApiManagement/service/apis@2021-08-01' = {{
  parent: apimService
  name: apiName
  properties: {{
    displayName: '{info.get('title', 'Copilot-for-Consensus API')}'
    description: '{info.get('description', '')[:100]}'
    path: ''
    protocols: ['https']
    subscriptionRequired: true
    // Import OpenAPI spec here via separate deployment or use format/value
  }}
}}

output gatewayUrl string = apimService.properties.gatewayUrl
output apimResourceId string = apimService.id
"""
    
    def _generate_cors_policy(self) -> str:
        """Generate CORS policy XML for APIM."""
        gateway_config = self.openapi_spec.get('x-gateway-config', {})
        cors_config = gateway_config.get('cors', {})
        
        allowed_origins = cors_config.get('allowed-origins', ['*'])
        allowed_methods = cors_config.get('allowed-methods', ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
        allowed_headers = cors_config.get('allowed-headers', ['Authorization', 'Content-Type'])
        
        return f"""<policies>
    <inbound>
        <cors allow-credentials="true">
            <allowed-origins>
                {' '.join(f'<origin>{origin}</origin>' for origin in allowed_origins)}
            </allowed-origins>
            <allowed-methods>
                {' '.join(f'<method>{method}</method>' for method in allowed_methods)}
            </allowed-methods>
            <allowed-headers>
                {' '.join(f'<header>{header}</header>' for header in allowed_headers)}
            </allowed-headers>
        </cors>
    </inbound>
</policies>"""
    
    def _generate_rate_limit_policy(self) -> str:
        """Generate rate limiting policy XML for APIM."""
        return """<policies>
    <inbound>
        <rate-limit-by-key calls="100" renewal-period="60" counter-key="@(context.Subscription.Id)" />
        <quota-by-key calls="10000" renewal-period="86400" counter-key="@(context.Subscription.Id)" />
    </inbound>
</policies>"""
    
    def _generate_jwt_policy(self) -> str:
        """Generate JWT validation policy XML for APIM."""
        return """<policies>
    <inbound>
        <validate-jwt header-name="Authorization" failed-validation-httpcode="401" failed-validation-error-message="Unauthorized">
            <openid-config url="https://your-auth-service/.well-known/openid-configuration" />
            <audiences>
                <audience>copilot-for-consensus</audience>
            </audiences>
            <issuers>
                <issuer>https://your-auth-service</issuer>
            </issuers>
        </validate-jwt>
    </inbound>
</policies>"""
