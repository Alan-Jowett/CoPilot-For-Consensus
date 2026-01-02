# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* pnpm-lock.yaml* yarn.lock* ./
RUN if [ -f package-lock.json ]; then npm ci; \
    elif [ -f pnpm-lock.yaml ]; then npm i -g pnpm && pnpm i --frozen-lockfile; \
    elif [ -f yarn.lock ]; then npm i -g yarn && yarn install --frozen-lockfile; \
    else npm install; fi
ARG VITE_REPORTING_API_URL
ENV VITE_REPORTING_API_URL=${VITE_REPORTING_API_URL}
ARG VITE_BASE
ENV VITE_BASE=${VITE_BASE:-/ui/}
ARG VITE_GRAFANA_ENABLED
ENV VITE_GRAFANA_ENABLED=${VITE_GRAFANA_ENABLED:-false}
COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY <<'EOF' /etc/nginx/conf.d/default.conf
# Use Docker's internal DNS server for dynamic hostname resolution
resolver 127.0.0.11 valid=10s ipv6=off;
resolver_timeout 5s;

server {
  listen 80;
  server_name _;
  root /usr/share/nginx/html;

  # Increase client body size limit for file uploads (100MB)
  client_max_body_size 100M;

  location / {
    try_files $uri $uri/ /index.html;
  }

  # NOTE: The proxy blocks below support standalone UI deployment (docker run ui:80).
  # When accessed via the API Gateway at http://localhost:8080/ui/, the gateway routes
  # requests to /reporting and /ingestion directly, so these UI proxy blocks are bypassed.
  # These blocks enable direct UI testing (docker run -p 8084:80 ui) where the UI handles
  # its own API proxying. In production, access via gateway is recommended.

  # Proxy Reporting API requests (for standalone UI runs)
  # Using variables forces nginx to resolve at request time, not startup
  location /reporting/ {
    set $reporting_upstream reporting:8080;
    proxy_pass http://$reporting_upstream/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }

  # Proxy ingestion source management API requests
  # Using variables forces nginx to resolve at request time, not startup
  location /ingestion/ {
    set $ingestion_upstream ingestion:8001;
    proxy_pass http://$ingestion_upstream/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Increase timeouts for large file uploads
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
    proxy_connect_timeout 75s;
  }

  # Proxy auth service API requests
  location /auth/ {
    proxy_pass http://auth:8090/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Authorization $http_authorization;
  }
}
EOF

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
