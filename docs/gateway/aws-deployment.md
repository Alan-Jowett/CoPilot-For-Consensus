<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# AWS API Gateway Deployment

## Overview

Deploy Copilot-for-Consensus to AWS using API Gateway for serverless, scalable API management with CloudWatch monitoring, X-Ray tracing, and AWS IAM integration.

## Quick Start

```bash
# Generate AWS configuration
cd infra/gateway
./generate_gateway_config.py --provider aws --output ../../dist/gateway/aws

# Deploy to AWS
cd ../../dist/gateway/aws
aws cloudformation create-stack \
  --stack-name copilot-api-gateway \
  --template-body file://aws-api-gateway-template.json \
  --parameters file://aws-api-gateway-parameters.json \
  --capabilities CAPABILITY_IAM
```

## Generated Files

| File | Description |
|------|-------------|
| `aws-api-gateway-template.json` | CloudFormation template |
| `aws-api-gateway-parameters.json` | Stack parameters |
| `aws-sam-template.yaml` | SAM template (serverless) |
| `openapi-aws-extensions.json` | OpenAPI spec with AWS integrations |

## Prerequisites

- AWS CLI installed (`aws`)
- AWS account with appropriate permissions
- Backend services deployed to AWS (ECS, Lambda, or EC2)
- Optional: AWS SAM CLI for SAM deployments

## Configuration

### 1. Customize Parameters

Edit `aws-api-gateway-parameters.json`:

```json
[
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
    "ParameterValue": "https://reporting.example.com"
  },
  {
    "ParameterKey": "BackendIngestionUrl",
    "ParameterValue": "https://ingestion.example.com"
  },
  {
    "ParameterKey": "BackendAuthUrl",
    "ParameterValue": "https://auth.example.com"
  }
]
```

### 2. Validate Template

```bash
aws cloudformation validate-template \
  --template-body file://aws-api-gateway-template.json
```

### 3. Create Stack

```bash
aws cloudformation create-stack \
  --stack-name copilot-api-gateway \
  --template-body file://aws-api-gateway-template.json \
  --parameters file://aws-api-gateway-parameters.json \
  --capabilities CAPABILITY_IAM
```

### 4. Wait for Completion

```bash
aws cloudformation wait stack-create-complete \
  --stack-name copilot-api-gateway
```

### 5. Get API Gateway URL

```bash
aws cloudformation describe-stacks \
  --stack-name copilot-api-gateway \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
  --output text
```

### 6. Test

```bash
API_URL=$(aws cloudformation describe-stacks --stack-name copilot-api-gateway --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' --output text)
curl $API_URL/reporting/health
```

## Alternative: SAM Deployment

Using AWS SAM for simplified serverless deployment:

### 1. Build

```bash
sam build -t aws-sam-template.yaml
```

### 2. Deploy (Guided)

```bash
sam deploy --guided
```

Follow the prompts to configure:
- Stack name
- AWS region
- Parameter values
- Capabilities (IAM)

### 3. Deploy (Non-Interactive)

After first deployment, use:

```bash
sam deploy
```

Configuration is saved in `samconfig.toml`.

## API Gateway Types

AWS offers two API Gateway types:

### REST API (Default)

**Best for**: Feature-rich APIs with caching, request validation, SDK generation

**Features**:
- Request/response transformation
- API keys and usage plans
- Custom domains
- Resource policies
- Comprehensive monitoring

**Cost**: $3.50/million requests + $0.09/GB data transfer

### HTTP API (Alternative)

**Best for**: Cost-effective, low-latency APIs

**Features**:
- JWT authorization (built-in)
- CORS support
- Lower latency
- Lower cost

**Cost**: $1.00/million requests

To use HTTP API instead of REST API, modify the CloudFormation template to use `AWS::ApiGatewayV2::Api` resource type.

## Security

### Authentication

#### Option 1: JWT Authorizer (Cognito)

1. Create Cognito User Pool:
   ```bash
   aws cognito-idp create-user-pool \
     --pool-name copilot-users \
     --auto-verified-attributes email
   ```

2. Update API Gateway authorizer in template

#### Option 2: Lambda Authorizer

Create custom Lambda function for authentication:

```python
def lambda_handler(event, context):
    token = event['authorizationToken']
    # Validate token against your auth service
    if valid:
        return generate_policy('user', 'Allow', event['methodArn'])
    return generate_policy('user', 'Deny', event['methodArn'])
```

#### Option 3: IAM Authorization

For service-to-service communication:

```bash
# Generate signed request
aws apigateway test-invoke-method \
  --rest-api-id <api-id> \
  --resource-id <resource-id> \
  --http-method GET \
  --path-with-query-string "/reporting/api/reports"
```

### API Keys and Usage Plans

```bash
# Create API key
aws apigateway create-api-key \
  --name copilot-client-1 \
  --enabled

# Create usage plan
aws apigateway create-usage-plan \
  --name copilot-basic \
  --throttle rateLimit=100,burstLimit=200 \
  --quota limit=10000,period=DAY
```

### WAF Integration

Add AWS WAF for additional protection:

```bash
aws wafv2 associate-web-acl \
  --web-acl-arn <waf-acl-arn> \
  --resource-arn <api-gateway-arn>
```

## Monitoring

### CloudWatch Metrics

View API Gateway metrics:

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Count \
  --dimensions Name=ApiName,Value=copilot-for-consensus-api \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Sum
```

Available metrics:
- `Count`: Number of API requests
- `4XXError`: Client errors
- `5XXError`: Server errors
- `Latency`: End-to-end latency
- `IntegrationLatency`: Backend latency

### CloudWatch Logs

Enable logging:

```bash
# Create log group
aws logs create-log-group \
  --log-group-name /aws/apigateway/copilot-api

# Update stage settings
aws apigateway update-stage \
  --rest-api-id <api-id> \
  --stage-name prod \
  --patch-operations \
    op=replace,path=/accessLogSettings/destinationArn,value=arn:aws:logs:region:account:log-group:/aws/apigateway/copilot-api
```

### X-Ray Tracing

Enable X-Ray for distributed tracing:

```bash
aws apigateway update-stage \
  --rest-api-id <api-id> \
  --stage-name prod \
  --patch-operations op=replace,path=/tracingEnabled,value=true
```

View traces in X-Ray console.

## Custom Domain

### 1. Request Certificate (ACM)

```bash
aws acm request-certificate \
  --domain-name api.yourdomain.com \
  --validation-method DNS
```

### 2. Create Domain Name

```bash
aws apigateway create-domain-name \
  --domain-name api.yourdomain.com \
  --certificate-arn <acm-cert-arn> \
  --endpoint-configuration types=REGIONAL
```

### 3. Create Base Path Mapping

```bash
aws apigateway create-base-path-mapping \
  --domain-name api.yourdomain.com \
  --rest-api-id <api-id> \
  --stage prod
```

### 4. Update DNS

Create CNAME or A record pointing to API Gateway domain.

## Caching

Enable caching to reduce backend load:

```bash
aws apigateway update-stage \
  --rest-api-id <api-id> \
  --stage-name prod \
  --patch-operations \
    op=replace,path=/cacheClusterEnabled,value=true \
    op=replace,path=/cacheClusterSize,value=0.5
```

Cache sizes: 0.5GB, 1.6GB, 6.1GB, 13.5GB, 28.4GB, 58.2GB, 118GB, 237GB

**Cost**: $0.020/hour for 0.5GB cache

## Throttling and Quotas

Configure per-method throttling:

```bash
aws apigateway update-method \
  --rest-api-id <api-id> \
  --resource-id <resource-id> \
  --http-method POST \
  --patch-operations \
    op=replace,path=/throttle/rateLimit,value=100 \
    op=replace,path=/throttle/burstLimit,value=200
```

## Cost Optimization

1. **Use HTTP API** instead of REST API (70% cost reduction)
2. **Enable caching** for read-heavy endpoints
3. **Implement request throttling** to prevent abuse
4. **Use regional endpoints** instead of edge-optimized (lower cost)
5. **Monitor unused API keys** and remove them
6. **Set up alarms** for unexpected traffic spikes

### Cost Example

For 1 million requests/day with 1KB payload:

| Component | Cost/Month |
|-----------|------------|
| API Gateway (REST) | ~$105 |
| Data transfer | ~$9 |
| CloudWatch logs | ~$5 |
| **Total** | **~$119** |

Using HTTP API reduces to ~$39/month.

## Troubleshooting

### 403 Forbidden

Check:
- API Key is present in request (if required)
- IAM permissions (if using IAM auth)
- Resource policy doesn't block access

### 502 Bad Gateway

Backend service issues:
- Check backend is running and healthy
- Verify security groups allow API Gateway access
- Check backend service logs

### 504 Gateway Timeout

Backend timeout (29-second limit):
- Optimize backend performance
- Use async processing for long operations
- Increase backend timeout if possible

### High Latency

- Enable API Gateway caching
- Use X-Ray to identify slow backends
- Optimize database queries
- Consider edge-optimized endpoint

## Multi-Region Setup

Deploy to multiple regions for high availability:

```bash
# Deploy to us-east-1
aws cloudformation create-stack \
  --stack-name copilot-api-us-east-1 \
  --region us-east-1 \
  --template-body file://aws-api-gateway-template.json \
  --parameters file://aws-api-gateway-parameters.json

# Deploy to eu-west-1
aws cloudformation create-stack \
  --stack-name copilot-api-eu-west-1 \
  --region eu-west-1 \
  --template-body file://aws-api-gateway-template.json \
  --parameters file://aws-api-gateway-parameters.json
```

Use Route 53 with health checks for global load balancing.

## Resources

- [AWS API Gateway Documentation](https://docs.aws.amazon.com/apigateway/)
- [CloudFormation API Gateway Resource Reference](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/AWS_ApiGateway.html)
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [OpenAPI Specification](../../infra/gateway/openapi.yaml)
- [Generated Configuration](../../dist/gateway/aws/)

## Next Steps

- Configure CloudWatch alarms for errors and latency
- Set up X-Ray for distributed tracing
- Enable request validation
- Create API documentation portal
- Implement throttling and quotas per client
