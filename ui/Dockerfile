# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* pnpm-lock.yaml* yarn.lock* ./
RUN if [ -f package-lock.json ]; then npm ci; \
    elif [ -f pnpm-lock.yaml ]; then npm i -g pnpm && pnpm i --frozen-lockfile; \
    elif [ -f yarn.lock ]; then npm i -g yarn && yarn install --frozen-lockfile; \
    else npm install; fi
COPY . .
ARG VITE_REPORTING_API_URL
ENV VITE_REPORTING_API_URL=${VITE_REPORTING_API_URL}
ARG VITE_BASE
ENV VITE_BASE=${VITE_BASE:-/ui/}
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
  listen 80;
  server_name _;
  root /usr/share/nginx/html;

  location / {
    try_files $uri /index.html;
  }

  # Serve the app from subpath /ui/ when proxied via the gateway
  location /ui/ {
    alias /usr/share/nginx/html/;
    try_files $uri $uri/ /index.html;
  }

  # Proxy Reporting API requests (for standalone UI runs)
  location /reporting/ {
    proxy_pass http://reporting:8080/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }

  # Proxy ingestion source management API requests
  location /ingestion/ {
    proxy_pass http://ingestion:8001/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
EOF

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
