# GCP Cloud Endpoints Deployment

## Overview

Deploy Copilot-for-Consensus to Google Cloud Platform using Cloud Endpoints with ESPv2 (Extensible Service Proxy v2) for API management with Cloud Monitoring, Cloud Trace, and Firebase authentication.

## Quick Start

```bash
# Generate GCP configuration
cd infra/gateway
./generate_gateway_config.py --provider gcp --output ../../dist/gateway/gcp

# Set project and deploy
cd ../../dist/gateway/gcp
export PROJECT_ID=your-gcp-project-id
./deploy-to-gcp.sh
```

## Generated Files

| File | Description |
|------|-------------|
| `gcp-openapi-spec.yaml` | OpenAPI spec with GCP extensions |
| `gcp-cloud-run-deployment.yaml` | Cloud Run service config |
| `gcp-k8s-deployment.yaml` | GKE Kubernetes manifests |
| `gcp-esp-config.yaml` | ESPv2 proxy configuration |
| `deploy-to-gcp.sh` | Automated deployment script |

## Prerequisites

- `gcloud` CLI installed and configured
- GCP project with billing enabled
- Required APIs enabled:
  - Cloud Endpoints API
  - Service Management API
  - Service Control API
  - Cloud Run API (for Cloud Run deployment)
- Backend services deployed to GCP

## Configuration

### 1. Set GCP Project

```bash
export PROJECT_ID=your-gcp-project-id
gcloud config set project $PROJECT_ID
```

### 2. Enable Required APIs

```bash
gcloud services enable endpoints.googleapis.com
gcloud services enable servicemanagement.googleapis.com
gcloud services enable servicecontrol.googleapis.com
gcloud services enable run.googleapis.com
```

### 3. Update Backend URLs

Edit `gcp-openapi-spec.yaml` and replace `PROJECT_ID` placeholders:

```bash
sed -i "s/PROJECT_ID/$PROJECT_ID/g" gcp-openapi-spec.yaml
```

Also update backend service URLs to point to your deployed services:

```yaml
x-google-backend:
  address: https://reporting-service-<hash>-uc.a.run.app
  deadline: 30.0
```

### 4. Deploy API Configuration

```bash
gcloud endpoints services deploy gcp-openapi-spec.yaml
```

This creates the Cloud Endpoints service configuration.

### 5. Get Service Configuration ID

```bash
SERVICE_NAME=copilot-api.endpoints.$PROJECT_ID.cloud.goog
CONFIG_ID=$(gcloud endpoints services describe $SERVICE_NAME \
  --format="value(serviceConfig.id)")
echo "Service Config ID: $CONFIG_ID"
```

## Deployment Options

### Option 1: Cloud Run (Recommended)

Deploy ESPv2 gateway on Cloud Run (serverless):

```bash
gcloud run deploy copilot-gateway \
  --image="gcr.io/endpoints-release/endpoints-runtime-serverless:2" \
  --allow-unauthenticated \
  --platform managed \
  --region us-central1 \
  --set-env-vars="ENDPOINTS_SERVICE_NAME=$SERVICE_NAME,ESPv2_ARGS=--cors_preset=basic"
```

**Benefits**:
- Serverless (no infrastructure management)
- Automatic scaling to zero
- Pay-per-use pricing
- Built-in HTTPS

**Get URL**:
```bash
gcloud run services describe copilot-gateway \
  --platform managed \
  --region us-central1 \
  --format 'value(status.url)'
```

### Option 2: GKE (Kubernetes)

Deploy to Google Kubernetes Engine:

```bash
# Create GKE cluster (if needed)
gcloud container clusters create copilot-cluster \
  --zone us-central1-a \
  --num-nodes 3

# Get credentials
gcloud container clusters get-credentials copilot-cluster \
  --zone us-central1-a

# Deploy gateway
kubectl apply -f gcp-k8s-deployment.yaml
```

**Benefits**:
- Full Kubernetes control
- Better for complex microservices
- Integration with service mesh (Istio, etc.)
- More configuration options

**Get IP**:
```bash
kubectl get service copilot-gateway -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

### Option 3: Compute Engine

Deploy on VM instances with managed instance group:

```bash
# Create instance template with ESPv2
gcloud compute instance-templates create copilot-gateway-template \
  --machine-type e2-medium \
  --image-family debian-11 \
  --image-project debian-cloud \
  --metadata startup-script='#!/bin/bash
    docker run -d -p 8080:8080 \
      -e ENDPOINTS_SERVICE_NAME='$SERVICE_NAME' \
      gcr.io/endpoints-release/endpoints-runtime:2'

# Create managed instance group
gcloud compute instance-groups managed create copilot-gateway-group \
  --template copilot-gateway-template \
  --size 2 \
  --region us-central1

# Create load balancer
# (Additional configuration required)
```

## Testing

```bash
# Get gateway URL (Cloud Run)
GATEWAY_URL=$(gcloud run services describe copilot-gateway \
  --platform managed \
  --region us-central1 \
  --format 'value(status.url)')

# Test health endpoint
curl $GATEWAY_URL/reporting/health

# Test API endpoint
curl $GATEWAY_URL/reporting/api/reports
```

## Security

### Authentication

#### Option 1: Firebase Authentication

1. Enable Firebase Authentication:
   ```bash
   firebase init
   firebase auth:import users.json
   ```

2. Update OpenAPI spec with Firebase issuer:
   ```yaml
   components:
     securitySchemes:
       firebase:
         type: oauth2
         x-google-issuer: https://securetoken.google.com/$PROJECT_ID
         x-google-jwks_uri: https://www.googleapis.com/service_accounts/v1/metadata/x509/securetoken@system.gserviceaccount.com
   ```

3. Require authentication on endpoints:
   ```yaml
   paths:
     /api/endpoint:
       get:
         security:
           - firebase: []
   ```

#### Option 2: API Keys

Generate API keys for service-to-service authentication:

```bash
gcloud services api-keys create \
  --display-name="Copilot Client Key" \
  --api-target=service=$SERVICE_NAME
```

Clients include key in request:
```bash
curl "$GATEWAY_URL/api/endpoint?key=YOUR_API_KEY"
```

#### Option 3: Service Accounts

For GCP service-to-service auth:

```bash
# Create service account
gcloud iam service-accounts create copilot-client \
  --display-name "Copilot API Client"

# Grant permissions
gcloud endpoints services add-iam-policy-binding $SERVICE_NAME \
  --member serviceAccount:copilot-client@$PROJECT_ID.iam.gserviceaccount.com \
  --role roles/servicemanagement.serviceController
```

### Network Security

#### Cloud Armor

Add DDoS protection and WAF:

```bash
# Create security policy
gcloud compute security-policies create copilot-policy \
  --description "Copilot API security policy"

# Add rules
gcloud compute security-policies rules create 1000 \
  --security-policy copilot-policy \
  --expression "origin.region_code == 'CN'" \
  --action deny-403

# Attach to backend service
gcloud compute backend-services update copilot-backend \
  --security-policy copilot-policy \
  --global
```

#### VPC Service Controls

Restrict API access to specific VPC networks:

```bash
gcloud access-context-manager perimeters create copilot-perimeter \
  --title "Copilot API Perimeter" \
  --resources "projects/$PROJECT_NUMBER" \
  --restricted-services endpoints.googleapis.com
```

## Monitoring

### Cloud Monitoring

View API metrics:

```bash
# Open Cloud Console
gcloud monitoring dashboards create --config-from-file=dashboard.yaml
```

Available metrics:
- `serviceruntime.googleapis.com/api/request_count`
- `serviceruntime.googleapis.com/api/request_latencies`
- `serviceruntime.googleapis.com/api/request_sizes`
- `serviceruntime.googleapis.com/api/response_sizes`

### Cloud Logging

View API logs:

```bash
gcloud logging read "resource.type=api AND resource.labels.service=$SERVICE_NAME" \
  --limit 50 \
  --format json
```

### Cloud Trace

Enable tracing for distributed request analysis:

```bash
gcloud endpoints services update $SERVICE_NAME \
  --enable-tracing
```

View traces in Cloud Console → Trace.

### Error Reporting

Automatic error aggregation:

```bash
gcloud error-reporting events list \
  --service $SERVICE_NAME \
  --time-range 1d
```

## Custom Domain

### 1. Reserve Static IP

```bash
gcloud compute addresses create copilot-gateway-ip \
  --global
```

### 2. Get IP Address

```bash
gcloud compute addresses describe copilot-gateway-ip \
  --global \
  --format="value(address)"
```

### 3. Update DNS

Create A record pointing to the static IP.

### 4. Create SSL Certificate

```bash
gcloud compute ssl-certificates create copilot-cert \
  --domains=api.yourdomain.com \
  --global
```

### 5. Configure Load Balancer

```bash
# Create backend service
gcloud compute backend-services create copilot-backend \
  --global \
  --load-balancing-scheme=EXTERNAL \
  --protocol=HTTP

# Create URL map
gcloud compute url-maps create copilot-urlmap \
  --default-service copilot-backend

# Create HTTPS proxy
gcloud compute target-https-proxies create copilot-proxy \
  --url-map copilot-urlmap \
  --ssl-certificates copilot-cert

# Create forwarding rule
gcloud compute forwarding-rules create copilot-https-rule \
  --address copilot-gateway-ip \
  --global \
  --target-https-proxy copilot-proxy \
  --ports 443
```

## Quota Management

Configure quotas per consumer:

```bash
# Create quota override
gcloud endpoints services update $SERVICE_NAME \
  --quota-override api_calls=1000000,consumer_id=project:$PROJECT_ID
```

## Cost Optimization

1. **Use Cloud Run** for automatic scaling to zero
2. **Enable caching** in ESPv2:
   ```
   --service_config_id=$CONFIG_ID \
   --backend_cache_size=10m
   ```
3. **Set up budget alerts**:
   ```bash
   gcloud billing budgets create \
     --billing-account=$BILLING_ACCOUNT \
     --display-name="Copilot API Budget" \
     --budget-amount=100
   ```
4. **Monitor API usage** and set alerts for anomalies

### Cost Example

For 1 million requests/day:

| Component | Cost/Month |
|-----------|------------|
| Cloud Endpoints | Free (first 2M calls) |
| Cloud Run (ESPv2) | ~$10 |
| Cloud Load Balancing | ~$20 |
| Cloud Logging | ~$5 |
| **Total** | **~$35** |

## Troubleshooting

### Service Not Found

Verify deployment:
```bash
gcloud endpoints services list
gcloud endpoints services describe $SERVICE_NAME
```

### 502 Bad Gateway

Check backend services are running:
```bash
gcloud run services list
gcloud run services describe <service-name>
```

### Permission Denied

Check IAM roles:
```bash
gcloud projects get-iam-policy $PROJECT_ID
```

### High Latency

- Enable Cloud CDN for static content
- Use regional endpoints closer to users
- Optimize backend services
- Enable HTTP/2

## Multi-Region Setup

Deploy to multiple regions:

```bash
# Deploy to us-central1
gcloud run deploy copilot-gateway-us \
  --image=gcr.io/endpoints-release/endpoints-runtime-serverless:2 \
  --region us-central1 \
  --set-env-vars="ENDPOINTS_SERVICE_NAME=$SERVICE_NAME"

# Deploy to europe-west1
gcloud run deploy copilot-gateway-eu \
  --image=gcr.io/endpoints-release/endpoints-runtime-serverless:2 \
  --region europe-west1 \
  --set-env-vars="ENDPOINTS_SERVICE_NAME=$SERVICE_NAME"

# Configure Cloud Load Balancer for global routing
```

## Resources

- [Cloud Endpoints Documentation](https://cloud.google.com/endpoints/docs)
- [ESPv2 Documentation](https://cloud.google.com/endpoints/docs/openapi/specify-esp-v2-startup-options)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [OpenAPI Specification](../../infra/gateway/openapi.yaml)
- [Generated Configuration](../../dist/gateway/gcp/)

## Next Steps

- Configure API quotas and rate limiting
- Set up Cloud Monitoring dashboards
- Enable Cloud Trace for performance analysis
- Create custom domain with SSL certificate
- Implement API key management
- Configure backend authentication (Firebase or service accounts)
