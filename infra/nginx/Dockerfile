# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM nginx:alpine

# Copy the nginx configuration template
COPY nginx.conf /etc/nginx/nginx.conf

# Copy custom entrypoint
COPY docker-entrypoint.sh /docker-entrypoint.d/40-configure-tls.sh
RUN chmod +x /docker-entrypoint.d/40-configure-tls.sh
