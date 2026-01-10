#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""AWS API Gateway adapter for gateway configuration.

This adapter generates AWS CloudFormation/SAM templates for deploying
the Copilot-for-Consensus API via AWS API Gateway (REST or HTTP API).
"""

import json
from pathlib import Path
from typing import Any, Dict

from adapter_base import GatewayAdapter


class AwsAdapter(GatewayAdapter):
    """Adapter for AWS API Gateway.

    Generates:
    - CloudFormation template (JSON/YAML) with API Gateway configuration
    - SAM template for serverless deployment
    - OpenAPI extension for API Gateway integrations
    - IAM policies for authentication
    """

    @property
    def provider_name(self) -> str:
        return "aws"

    @property
    def deployment_instructions(self) -> str:
        return """
AWS API Gateway Deployment Instructions:
========================================

Prerequisites:
- AWS CLI installed and configured (aws configure)
- AWS SAM CLI installed (optional, for SAM deployments)
- AWS account with appropriate permissions

Deployment Steps (CloudFormation):

1. Review and customize parameters:
   Edit aws-api-gateway-parameters.json to set:
   - ApiGatewayName
   - StageName (e.g., prod, dev)
   - BackendServiceUrls

2. Validate the template:
   aws cloudformation validate-template \\
     --template-body file://aws-api-gateway-template.json

3. Create a stack:
   aws cloudformation create-stack \\
     --stack-name copilot-api-gateway \\
     --template-body file://aws-api-gateway-template.json \\
     --parameters file://aws-api-gateway-parameters.json \\
     --capabilities CAPABILITY_IAM

4. Wait for stack creation:
   aws cloudformation wait stack-create-complete \\
     --stack-name copilot-api-gateway

5. Get the API Gateway URL:
   aws cloudformation describe-stacks \\
     --stack-name copilot-api-gateway \\
     --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \\
     --output text

6. Test the deployment:
   API_URL=$(aws cloudformation describe-stacks --stack-name copilot-api-gateway --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' --output text)
   curl $API_URL/reporting/health

Alternative: SAM Deployment:
   sam build -t aws-sam-template.yaml
   sam deploy --guided

Monitoring:
- View API Gateway metrics in CloudWatch
- Enable CloudWatch Logs for API Gateway
- Use X-Ray for distributed tracing
"""

    def load_spec(self) -> None:
        """Load the OpenAPI specification from YAML file."""
        import yaml

        with open(self.openapi_spec_path, 'r') as f:
            self.openapi_spec = yaml.safe_load(f)

    def validate_spec(self) -> bool:
        """Validate OpenAPI spec for AWS API Gateway compatibility."""
        required_fields = ['openapi', 'info', 'paths']
        for field in required_fields:
            if field not in self.openapi_spec:
                raise ValueError(f"OpenAPI spec missing required field: {field}")

        # Check OpenAPI version (API Gateway supports 3.0)
        version = self.openapi_spec.get('openapi', '')
        if not version.startswith('3.'):
            raise ValueError(f"AWS API Gateway requires OpenAPI 3.x, got {version}")

        return True

    def generate_config(self, output_dir: Path) -> Dict[str, Path]:
        """Generate AWS API Gateway configuration files."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate CloudFormation template
        cfn_template = self._generate_cloudformation_template()
        cfn_template_path = output_dir / "aws-api-gateway-template.json"
        with open(cfn_template_path, 'w') as f:
            json.dump(cfn_template, f, indent=2)

        # Generate parameters file
        parameters = self._generate_parameters()
        parameters_path = output_dir / "aws-api-gateway-parameters.json"
        with open(parameters_path, 'w') as f:
            json.dump(parameters, f, indent=2)

        # Generate SAM template
        sam_template = self._generate_sam_template()
        sam_template_path = output_dir / "aws-sam-template.yaml"
        with open(sam_template_path, 'w') as f:
            f.write(sam_template)

        # Generate OpenAPI spec with AWS extensions
        openapi_with_extensions = self._add_aws_extensions()
        openapi_aws_path = output_dir / "openapi-aws-extensions.json"
        with open(openapi_aws_path, 'w') as f:
            json.dump(openapi_with_extensions, f, indent=2)

        return {
            "cloudformation_template": cfn_template_path,
            "parameters": parameters_path,
            "sam_template": sam_template_path,
            "openapi_aws": openapi_aws_path
        }

    def validate_config(self, config_files: Dict[str, Path]) -> bool:
        """Validate generated AWS configuration files."""
        for file_path in config_files.values():
            if not file_path.exists():
                raise ValueError(f"Generated file does not exist: {file_path}")

        # Validate CloudFormation template structure
        cfn_template_path = config_files.get("cloudformation_template")
        if cfn_template_path:
            with open(cfn_template_path, 'r') as f:
                cfn_template = json.load(f)
                required_fields = ['AWSTemplateFormatVersion', 'Resources']
                for field in required_fields:
                    if field not in cfn_template:
                        raise ValueError(f"CloudFormation template missing required field: {field}")

        # Check for unreplaced placeholders in generated files
        placeholders = ['your-backend-', 'https://your-backend-', 'example.com',
                       '<your-', '<sub-id>', '<rg>', '<app-insights-name>']

        for name, file_path in config_files.items():
            if file_path.suffix in ['.json', '.yaml', '.yml']:
                with open(file_path, 'r') as f:
                    content = f.read()
                    found_placeholders = [p for p in placeholders if p in content]
                    if found_placeholders:
                        print(f"⚠️  Warning: {name} contains unreplaced placeholders: {', '.join(found_placeholders)}")
                        print(f"   These must be configured before deployment. See deployment guide.")

        return True

    def _generate_cloudformation_template(self) -> Dict[str, Any]:
        """Generate AWS CloudFormation template for API Gateway."""
        info = self.openapi_spec.get('info', {})

        return {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": f"{info.get('title', 'Copilot-for-Consensus API')} - API Gateway",
            "Parameters": {
                "ApiGatewayName": {
                    "Type": "String",
                    "Default": "copilot-for-consensus-api",
                    "Description": "Name of the API Gateway"
                },
                "StageName": {
                    "Type": "String",
                    "Default": "prod",
                    "AllowedValues": ["dev", "staging", "prod"],
                    "Description": "Deployment stage name"
                },
                "BackendReportingUrl": {
                    "Type": "String",
                    "Description": "Backend URL for reporting service"
                },
                "BackendIngestionUrl": {
                    "Type": "String",
                    "Description": "Backend URL for ingestion service"
                },
                "BackendAuthUrl": {
                    "Type": "String",
                    "Description": "Backend URL for auth service"
                }
            },
            "Resources": {
                "ApiGatewayRestApi": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
                        "Name": {"Ref": "ApiGatewayName"},
                        "Description": info.get('description', '')[:1024],
                        "EndpointConfiguration": {
                            "Types": ["REGIONAL"]
                        },
                        "Body": self._add_aws_extensions()
                    }
                },
                "ApiGatewayDeployment": {
                    "Type": "AWS::ApiGateway::Deployment",
                    "DependsOn": ["ApiGatewayRestApi"],
                    "Properties": {
                        "RestApiId": {"Ref": "ApiGatewayRestApi"},
                        "StageName": {"Ref": "StageName"}
                    }
                },
                "ApiGatewayStage": {
                    "Type": "AWS::ApiGateway::Stage",
                    "Properties": {
                        "RestApiId": {"Ref": "ApiGatewayRestApi"},
                        "DeploymentId": {"Ref": "ApiGatewayDeployment"},
                        "StageName": {"Ref": "StageName"},
                        "MethodSettings": [
                            {
                                "HttpMethod": "*",
                                "ResourcePath": "/*",
                                "ThrottlingBurstLimit": 5000,
                                "ThrottlingRateLimit": 2000,
                                "LoggingLevel": "INFO",
                                "DataTraceEnabled": True,
                                "MetricsEnabled": True
                            }
                        ]
                    }
                },
                "ApiGatewayUsagePlan": {
                    "Type": "AWS::ApiGateway::UsagePlan",
                    "DependsOn": ["ApiGatewayStage"],
                    "Properties": {
                        "UsagePlanName": "copilot-default-plan",
                        "ApiStages": [
                            {
                                "ApiId": {"Ref": "ApiGatewayRestApi"},
                                "Stage": {"Ref": "StageName"}
                            }
                        ],
                        "Throttle": {
                            "RateLimit": 100,
                            "BurstLimit": 200
                        },
                        "Quota": {
                            "Limit": 10000,
                            "Period": "DAY"
                        }
                    }
                }
            },
            "Outputs": {
                "ApiGatewayUrl": {
                    "Description": "URL of the API Gateway",
                    "Value": {
                        "Fn::Sub": "https://${ApiGatewayRestApi}.execute-api.${AWS::Region}.amazonaws.com/${StageName}"
                    }
                },
                "ApiGatewayId": {
                    "Description": "ID of the API Gateway",
                    "Value": {"Ref": "ApiGatewayRestApi"}
                }
            }
        }

    def _generate_parameters(self) -> list:
        """Generate parameters file for CloudFormation."""
        return [
            {
                "ParameterKey": "ApiGatewayName",
                "ParameterValue": "copilot-for-consensus-api"
            },
            {
                "ParameterKey": "StageName",
                "ParameterValue": "prod"
            },
            {
                "ParameterKey": "BackendReportingUrl",
                "ParameterValue": "https://your-backend-reporting-service.example.com"
            },
            {
                "ParameterKey": "BackendIngestionUrl",
                "ParameterValue": "https://your-backend-ingestion-service.example.com"
            },
            {
                "ParameterKey": "BackendAuthUrl",
                "ParameterValue": "https://your-backend-auth-service.example.com"
            }
        ]

    def _generate_sam_template(self) -> str:
        """Generate AWS SAM template."""
        info = self.openapi_spec.get('info', {})

        return f"""# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: {info.get('title', 'Copilot-for-Consensus API')} - SAM Template

Parameters:
  StageName:
    Type: String
    Default: prod
    AllowedValues:
      - dev
      - staging
      - prod
    Description: Deployment stage name

  BackendReportingUrl:
    Type: String
    Description: Backend URL for reporting service

  BackendIngestionUrl:
    Type: String
    Description: Backend URL for ingestion service

  BackendAuthUrl:
    Type: String
    Description: Backend URL for auth service

Resources:
  CopilotApiGateway:
    Type: AWS::Serverless::Api
    Properties:
      Name: copilot-for-consensus-api
      StageName: !Ref StageName
      DefinitionBody:
        # OpenAPI specification with AWS extensions
        # Import from openapi-aws-extensions.json
        Fn::Transform:
          Name: AWS::Include
          Parameters:
            Location: openapi-aws-extensions.json

      Cors:
        AllowOrigin: "'*'"
        AllowMethods: "'GET,POST,PUT,DELETE,OPTIONS'"
        AllowHeaders: "'Content-Type,Authorization'"

      Auth:
        DefaultAuthorizer: CognitoAuthorizer
        Authorizers:
          CognitoAuthorizer:
            UserPoolArn: !GetAtt CopilotUserPool.Arn

      TracingEnabled: true
      MethodSettings:
        - ResourcePath: '/*'
          HttpMethod: '*'
          ThrottlingBurstLimit: 200
          ThrottlingRateLimit: 100
          MetricsEnabled: true
          LoggingLevel: INFO

  # Optional: Cognito User Pool for authentication
  CopilotUserPool:
    Type: AWS::Cognito::UserPool
    Properties:
      UserPoolName: copilot-for-consensus-users
      AutoVerifiedAttributes:
        - email
      Schema:
        - Name: email
          Required: true
          Mutable: false

Outputs:
  ApiGatewayUrl:
    Description: URL of the API Gateway
    Value: !Sub 'https://${{CopilotApiGateway}}.execute-api.${{AWS::Region}}.amazonaws.com/${{StageName}}'

  ApiGatewayId:
    Description: ID of the API Gateway
    Value: !Ref CopilotApiGateway
"""

    def _add_aws_extensions(self) -> Dict[str, Any]:
        """Add AWS-specific extensions to OpenAPI spec."""
        import copy
        spec = copy.deepcopy(self.openapi_spec)

        # Add x-amazon-apigateway-integration to each path
        gateway_config = spec.get('x-gateway-config', {})
        backends = gateway_config.get('backends', {})

        for path, methods in spec.get('paths', {}).items():
            for method, operation in methods.items():
                if method.upper() not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS']:
                    continue

                # Determine backend based on path prefix
                backend_url = "http://example.com"
                if path.startswith('/reporting'):
                    backend_url = backends.get('reporting', {}).get('url', 'http://reporting:8080')
                elif path.startswith('/ingestion'):
                    backend_url = backends.get('ingestion', {}).get('url', 'http://ingestion:8001')
                elif path.startswith('/auth') or path.startswith('/admin'):
                    backend_url = backends.get('auth', {}).get('url', 'http://auth:8090')

                # Add AWS integration
                operation['x-amazon-apigateway-integration'] = {
                    "type": "http_proxy",
                    "httpMethod": method.upper(),
                    "uri": backend_url + path,
                    "connectionType": "INTERNET",
                    "timeoutInMillis": 29000,
                    "passthroughBehavior": "when_no_match"
                }

        return spec
