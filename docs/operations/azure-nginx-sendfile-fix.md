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
- `curl` to large assets may fail with `curl: (18) end of response with ... bytes missing`

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

**Important**: Avoid disabling proxy buffering for large static assets when running behind ACA ingress.
In particular, forcing streaming with `proxy_buffering off;` in the gateway `location /ui/` block can
make truncation more likely because Envoy/proxies see the response as an unbuffered stream.
Prefer buffered proxying at the gateway for `/ui/assets/...`.

### What We Changed (and Why)

1) **UI: enable gzip compression for static assets**
- Files: `ui/Dockerfile` and `ui/Dockerfile.azure`
- Why: In ACA, we observed intermittent truncation primarily on larger JS assets when served as a fixed-length body (with `Content-Length`). Enabling `gzip` reduces the number of bytes transferred and (in practice for these requests) results in a chunked response (`Transfer-Encoding: chunked`) instead of a fixed `Content-Length`, which avoids client-visible "bytes missing" failures.

2) **Gateway: keep UI proxying buffered (do not force streaming)**
- File: `infra/nginx/nginx.conf`
- Why: Forcing streaming (`proxy_buffering off`) increases the chance of truncation behind proxy chains like ACA ingress. Buffered proxying makes upstream/downstream behavior more predictable.

3) **Add trace headers for debugging**
- Files: `infra/nginx/nginx.conf`, `ui/Dockerfile`, `ui/Dockerfile.azure`
- Why: We added `X-CFC-Gateway: 1` (gateway) and `X-CFC-UI: 1` (ui) so production responses can be proven to traverse the expected hop chain during troubleshooting.

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

  # Optional but recommended for large JS/CSS assets behind proxy chains:
  # compress responses so browsers transfer fewer bytes.
  gzip on;

  # Recommended gzip settings
  gzip_comp_level 6;
  gzip_min_length 1024;
  gzip_proxied any;
  gzip_vary on;
  gzip_types text/plain text/css application/json application/javascript application/xml image/svg+xml;

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

For command-line verification, prefer a request that advertises compression and validates that the download completes:

```powershell
# Replace the URL with the current hashed asset on your environment
$url = "https://dev.copilot-for-consensus.com/ui/assets/index-<hash>.js"

# Should include: content-encoding: gzip, transfer-encoding: chunked, x-cfc-ui: 1, x-cfc-gateway: 1
curl.exe -sS -I -H "Accept-Encoding: gzip" $url

# Must complete with exit code 0 (no curl 18 truncation)
curl.exe -sS --compressed -o $env:TEMP\ui-asset.js $url
```

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
