#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""GCP Cloud Endpoints adapter for gateway configuration.

This adapter generates Google Cloud Platform configuration for deploying
the Copilot-for-Consensus API via Cloud Endpoints with ESPv2 proxy.
"""

from pathlib import Path
from typing import Any, Dict

from adapter_base import GatewayAdapter


class GcpAdapter(GatewayAdapter):
    """Adapter for GCP Cloud Endpoints.

    Generates:
    - OpenAPI specification with GCP extensions
    - Cloud Run/GKE deployment configuration
    - ESPv2 (Extensible Service Proxy v2) configuration
    - Service configuration for Cloud Endpoints
    """

    @property
    def provider_name(self) -> str:
        return "gcp"

    @property
    def deployment_instructions(self) -> str:
        return """
GCP Cloud Endpoints Deployment Instructions:
==========================================

Prerequisites:
- gcloud CLI installed and configured (gcloud auth login)
- GCP project with appropriate APIs enabled:
  - Cloud Endpoints API
  - Service Management API
  - Service Control API
- Cloud Run or GKE cluster (for backend services)

Deployment Steps:

1. Set your GCP project:
   export PROJECT_ID=your-gcp-project-id
   gcloud config set project $PROJECT_ID

2. Enable required APIs:
   gcloud services enable endpoints.googleapis.com
   gcloud services enable servicemanagement.googleapis.com
   gcloud services enable servicecontrol.googleapis.com

3. Update the OpenAPI spec with your backend service URLs:
   Edit gcp-openapi-spec.yaml and replace backend URLs
   with your Cloud Run or GKE service endpoints

4. Deploy the API configuration to Cloud Endpoints:
   gcloud endpoints services deploy gcp-openapi-spec.yaml

5. Get the service configuration ID:
   gcloud endpoints services describe copilot-api.endpoints.$PROJECT_ID.cloud.goog

6. Deploy ESPv2 proxy (Cloud Run):
   gcloud run deploy copilot-gateway \\
     --image="gcr.io/endpoints-release/endpoints-runtime-serverless:2" \\
     --allow-unauthenticated \\
     --platform managed \\
     --project=$PROJECT_ID \\
     --set-env-vars=ENDPOINTS_SERVICE_NAME=copilot-api.endpoints.$PROJECT_ID.cloud.goog

7. Get the gateway URL:
   gcloud run services describe copilot-gateway \\
     --platform managed \\
     --format 'value(status.url)'

8. Test the deployment:
   GATEWAY_URL=$(gcloud run services describe copilot-gateway --platform managed --format 'value(status.url)')
   curl $GATEWAY_URL/reporting/health

Alternative: Kubernetes/GKE Deployment:
   kubectl apply -f gcp-k8s-deployment.yaml

Monitoring:
- View API metrics in Cloud Console → Endpoints
- Enable Cloud Logging for detailed logs
- Use Cloud Trace for distributed tracing
- Set up Cloud Monitoring alerts
"""

    def load_spec(self) -> None:
        """Load the OpenAPI specification from YAML file."""
        import yaml

        with open(self.openapi_spec_path, 'r') as f:
            self.openapi_spec = yaml.safe_load(f)

    def validate_spec(self) -> bool:
        """Validate OpenAPI spec for GCP Cloud Endpoints compatibility."""
        required_fields = ['openapi', 'info', 'paths']
        for field in required_fields:
            if field not in self.openapi_spec:
                raise ValueError(f"OpenAPI spec missing required field: {field}")

        # Check OpenAPI version (Cloud Endpoints supports 2.0 and 3.0)
        version = self.openapi_spec.get('openapi', '')
        if not (version.startswith('3.') or version.startswith('2.')):
            raise ValueError(f"GCP Cloud Endpoints requires OpenAPI 2.x or 3.x, got {version}")

        return True

    def generate_config(self, output_dir: Path) -> Dict[str, Path]:
        """Generate GCP Cloud Endpoints configuration files."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate OpenAPI spec with GCP extensions
        gcp_spec = self._add_gcp_extensions()
        gcp_spec_path = output_dir / "gcp-openapi-spec.yaml"

        import yaml
        with open(gcp_spec_path, 'w') as f:
            yaml.dump(gcp_spec, f, default_flow_style=False, sort_keys=False)

        # Generate Cloud Run deployment config
        cloud_run_config = self._generate_cloud_run_config()
        cloud_run_path = output_dir / "gcp-cloud-run-deployment.yaml"
        with open(cloud_run_path, 'w') as f:
            yaml.dump(cloud_run_config, f, default_flow_style=False)

        # Generate Kubernetes deployment config (for GKE)
        k8s_config = self._generate_k8s_config()
        k8s_path = output_dir / "gcp-k8s-deployment.yaml"
        with open(k8s_path, 'w') as f:
            yaml.dump_all(k8s_config, f, default_flow_style=False)

        # Generate ESPv2 configuration
        esp_config = self._generate_esp_config()
        esp_config_path = output_dir / "gcp-esp-config.yaml"
        with open(esp_config_path, 'w') as f:
            yaml.dump(esp_config, f, default_flow_style=False)

        # Generate deployment script
        deploy_script = self._generate_deploy_script()
        deploy_script_path = output_dir / "deploy-to-gcp.sh"
        with open(deploy_script_path, 'w') as f:
            f.write(deploy_script)
        deploy_script_path.chmod(0o755)

        return {
            "openapi_gcp": gcp_spec_path,
            "cloud_run_config": cloud_run_path,
            "k8s_config": k8s_path,
            "esp_config": esp_config_path,
            "deploy_script": deploy_script_path
        }

    def validate_config(self, config_files: Dict[str, Path]) -> bool:
        """Validate generated GCP configuration files."""
        for file_path in config_files.values():
            if not file_path.exists():
                raise ValueError(f"Generated file does not exist: {file_path}")

        # Check for unreplaced placeholders in generated files
        placeholders = ['PROJECT_ID', 'your-gcp-project-id', 'admin@example.com',
                       'https://example.com', 'your-backend-', 'REPLACE_WITH']

        for name, file_path in config_files.items():
            if file_path.suffix in ['.yaml', '.yml', '.json', '.sh']:
                with open(file_path, 'r') as f:
                    content = f.read()
                    found_placeholders = [p for p in placeholders if p in content]
                    if found_placeholders:
                        print(f"⚠️  Warning: {name} contains unreplaced placeholders: {', '.join(found_placeholders)}")
                        print(f"   These must be configured before deployment. See deployment guide.")

        return True

    def _add_gcp_extensions(self) -> Dict[str, Any]:
        """Add GCP-specific extensions to OpenAPI spec."""
        import copy
        spec = copy.deepcopy(self.openapi_spec)

        # Update host to use Cloud Endpoints format
        # This should be customized per deployment
        spec['host'] = 'copilot-api.endpoints.PROJECT_ID.cloud.goog'

        # Add x-google-backend extension for each path
        gateway_config = spec.get('x-gateway-config', {})
        backends = gateway_config.get('backends', {})

        # Add Google-specific configuration
        spec['x-google-endpoints'] = [
            {
                'name': 'copilot-api.endpoints.PROJECT_ID.cloud.goog',
                'allowCors': True
            }
        ]

        # Add backend routing
        for path, methods in spec.get('paths', {}).items():
            for method, operation in methods.items():
                if method.upper() not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS']:
                    continue

                # Determine backend based on path prefix
                backend_url = "https://example.com"
                if path.startswith('/reporting'):
                    backend_url = backends.get('reporting', {}).get('url', 'https://reporting-service.run.app')
                elif path.startswith('/ingestion'):
                    backend_url = backends.get('ingestion', {}).get('url', 'https://ingestion-service.run.app')
                elif path.startswith('/auth') or path.startswith('/admin'):
                    backend_url = backends.get('auth', {}).get('url', 'https://auth-service.run.app')

                # Add Google backend extension
                operation['x-google-backend'] = {
                    'address': backend_url,
                    'deadline': 30.0
                }

        # Add security definitions for JWT
        if 'components' not in spec:
            spec['components'] = {}

        spec['components']['securitySchemes'] = {
            'firebase': {
                'type': 'oauth2',
                'authorizationUrl': '',
                'flow': 'implicit',
                'x-google-issuer': 'https://securetoken.google.com/PROJECT_ID',
                'x-google-jwks_uri': 'https://www.googleapis.com/service_accounts/v1/metadata/x509/securetoken@system.gserviceaccount.com',
                'x-google-audiences': 'PROJECT_ID'
            }
        }

        return spec

    def _generate_cloud_run_config(self) -> Dict[str, Any]:
        """Generate Cloud Run service configuration."""
        return {
            'apiVersion': 'serving.knative.dev/v1',
            'kind': 'Service',
            'metadata': {
                'name': 'copilot-gateway',
                'namespace': 'default',
                'labels': {
                    'app': 'copilot-for-consensus',
                    'component': 'gateway'
                }
            },
            'spec': {
                'template': {
                    'metadata': {
                        'annotations': {
                            'autoscaling.knative.dev/minScale': '1',
                            'autoscaling.knative.dev/maxScale': '10'
                        }
                    },
                    'spec': {
                        'containers': [
                            {
                                'name': 'esp',
                                'image': 'gcr.io/endpoints-release/endpoints-runtime-serverless:2',
                                'env': [
                                    {
                                        'name': 'ENDPOINTS_SERVICE_NAME',
                                        'value': 'copilot-api.endpoints.PROJECT_ID.cloud.goog'
                                    },
                                    {
                                        'name': 'ESPv2_ARGS',
                                        'value': '--cors_preset=basic --cors_allow_origin=*'
                                    }
                                ],
                                'resources': {
                                    'limits': {
                                        'cpu': '1',
                                        'memory': '512Mi'
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }

    def _generate_k8s_config(self) -> list:
        """Generate Kubernetes deployment configuration for GKE."""
        return [
            {
                'apiVersion': 'v1',
                'kind': 'Service',
                'metadata': {
                    'name': 'copilot-gateway',
                    'labels': {
                        'app': 'copilot-for-consensus',
                        'component': 'gateway'
                    }
                },
                'spec': {
                    'type': 'LoadBalancer',
                    'selector': {
                        'app': 'copilot-gateway'
                    },
                    'ports': [
                        {
                            'name': 'http',
                            'port': 80,
                            'targetPort': 8080
                        }
                    ]
                }
            },
            {
                'apiVersion': 'apps/v1',
                'kind': 'Deployment',
                'metadata': {
                    'name': 'copilot-gateway',
                    'labels': {
                        'app': 'copilot-for-consensus',
                        'component': 'gateway'
                    }
                },
                'spec': {
                    'replicas': 2,
                    'selector': {
                        'matchLabels': {
                            'app': 'copilot-gateway'
                        }
                    },
                    'template': {
                        'metadata': {
                            'labels': {
                                'app': 'copilot-gateway'
                            }
                        },
                        'spec': {
                            'containers': [
                                {
                                    'name': 'esp',
                                    'image': 'gcr.io/endpoints-release/endpoints-runtime:2',
                                    'args': [
                                        '--service=copilot-api.endpoints.PROJECT_ID.cloud.goog',
                                        '--rollout_strategy=managed',
                                        '--backend=127.0.0.1:8081'
                                    ],
                                    'ports': [
                                        {
                                            'containerPort': 8080
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
        ]

    def _generate_esp_config(self) -> Dict[str, Any]:
        """Generate ESPv2 configuration."""
        return {
            'service_config_id': 'REPLACE_WITH_CONFIG_ID',
            'backend': {
                'address': 'http://backend-service:8080',
                'timeout': 30
            },
            'cors': {
                'enabled': True,
                'allow_origins': ['*'],
                'allow_methods': ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
                'allow_headers': ['Authorization', 'Content-Type']
            },
            'logging': {
                'level': 'info'
            }
        }

    def _generate_deploy_script(self) -> str:
        """Generate deployment script for GCP."""
        return """#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

set -e

# GCP Cloud Endpoints Deployment Script
# This script deploys the Copilot-for-Consensus API to GCP Cloud Endpoints

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-gcp-project-id}"
SERVICE_NAME="copilot-api.endpoints.${PROJECT_ID}.cloud.goog"
REGION="${GCP_REGION:-us-central1}"

echo "🚀 Deploying Copilot-for-Consensus API to GCP Cloud Endpoints"
echo "Project: $PROJECT_ID"
echo "Service: $SERVICE_NAME"
echo "Region: $REGION"
echo ""

# Step 1: Set project
echo "📋 Setting GCP project..."
gcloud config set project "$PROJECT_ID"

# Step 2: Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable endpoints.googleapis.com
gcloud services enable servicemanagement.googleapis.com
gcloud services enable servicecontrol.googleapis.com
gcloud services enable run.googleapis.com

# Step 3: Replace placeholders in OpenAPI spec
echo "📝 Preparing OpenAPI specification..."
python3 -c "
import sys
project_id = '$PROJECT_ID'
with open('gcp-openapi-spec.yaml', 'r') as f:
    content = f.read()
content = content.replace('PROJECT_ID', project_id)
with open('gcp-openapi-spec-processed.yaml', 'w') as f:
    f.write(content)
"

# Step 4: Deploy API configuration
echo "☁️  Deploying API configuration to Cloud Endpoints..."
gcloud endpoints services deploy gcp-openapi-spec-processed.yaml

# Step 5: Get service configuration ID
echo "🔍 Retrieving service configuration ID..."
CONFIG_ID=$(gcloud endpoints services describe "$SERVICE_NAME" --format="value(serviceConfig.id)")
echo "Configuration ID: $CONFIG_ID"

# Step 6: Deploy ESPv2 gateway on Cloud Run
echo "🚢 Deploying ESPv2 gateway on Cloud Run..."
gcloud run deploy copilot-gateway \\
  --image="gcr.io/endpoints-release/endpoints-runtime-serverless:2" \\
  --allow-unauthenticated \\
  --platform managed \\
  --region="$REGION" \\
  --set-env-vars="ENDPOINTS_SERVICE_NAME=$SERVICE_NAME,ESPv2_ARGS=--cors_preset=basic"

# Step 7: Get gateway URL
echo "✅ Deployment complete!"
GATEWAY_URL=$(gcloud run services describe copilot-gateway --platform managed --region="$REGION" --format 'value(status.url)')
echo ""
echo "Gateway URL: $GATEWAY_URL"
echo ""
echo "Test with:"
echo "  curl $GATEWAY_URL/reporting/health"
"""
