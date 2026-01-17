<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Azure Container Apps NGINX Sendfile Issue

## Problem

When deploying the UI service (or any NGINX-based service) to Azure Container Apps, HTML responses may be truncated, resulting in a blank or partially rendered page. This issue does not occur when running the same container locally behind NGINX.

## Root Cause

Azure Container Apps uses **Envoy** as its ingress proxy. When NGINX is configured with `sendfile on` (the default), it uses the kernel's `sendfile()` system call to send files directly from disk to the network socket, bypassing user space. This optimization is incompatible with Envoy's proxy implementation, which may not correctly handle the file descriptor passing, resulting in truncated responses.

## Symptoms

- HTML responses are truncated mid-document
- SPA fails to render (blank page or partial content)
- No errors appear in NGINX logs
- Issue only occurs when deployed to Azure Container Apps
- Same container works fine locally with NGINX

## Solution

The fix involves disabling `sendfile` and configuring proper TCP and buffering settings for compatibility with Envoy:

### Gateway Configuration (`infra/nginx/nginx.conf`)

```nginx
http {
  # Disable sendfile for Azure Container Apps / Envoy compatibility
  sendfile        off;
  tcp_nopush      off;
  tcp_nodelay     on;

  # Proxy buffering settings to prevent truncation issues
  proxy_buffering on;
  proxy_buffer_size 4k;
  proxy_buffers 8 4k;
  proxy_busy_buffers_size 8k;
  
  # ... rest of configuration
}
```

### UI Service Configuration (`ui/Dockerfile` and `ui/Dockerfile.azure`)

```nginx
server {
  listen 80;
  server_name _;
  root /usr/share/nginx/html;

  # Disable sendfile for Azure Container Apps / Envoy compatibility
  sendfile off;
  tcp_nopush off;
  tcp_nodelay on;

  # ... rest of configuration
}
```

## Performance Impact

Disabling `sendfile` has a minor performance impact:

- **Local Development**: Negligible impact for small files (< 1MB)
- **Azure Container Apps**: No practical impact, as the alternative would be truncated responses
- **Static Assets**: Consider using a CDN for production deployments to offset any performance loss

## Related Issues

This is a well-documented issue when running NGINX behind other reverse proxies:

- NGINX behind Envoy: [envoyproxy/envoy#12908](https://github.com/envoyproxy/envoy/issues/12908)
- Azure Container Apps ingress uses Envoy under the hood
- Similar issues reported with AWS ALB, GCP Load Balancer when using sendfile

## Testing

To verify the fix:

1. Build the updated Docker images
2. Deploy to Azure Container Apps
3. Access the UI and verify that pages load completely
4. Check browser DevTools Network tab to ensure full HTML response

## Alternative Solutions

If you prefer to keep `sendfile` enabled for performance reasons, you can:

1. **Use a CDN**: Serve static assets from Azure CDN or Azure Front Door
2. **Enable gzip compression**: This forces NGINX to buffer responses in memory
3. **Adjust buffer sizes**: Increase `proxy_buffers` and `proxy_buffer_size` values

However, the simplest and most reliable solution is to disable `sendfile` when deploying behind Envoy.

## References

- [NGINX sendfile documentation](http://nginx.org/en/docs/http/ngx_http_core_module.html#sendfile)
- [Envoy proxy documentation](https://www.envoyproxy.io/docs/envoy/latest/)
- [Azure Container Apps ingress configuration](https://learn.microsoft.com/en-us/azure/container-apps/ingress-overview)
