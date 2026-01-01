# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM nginx:alpine

# Copy the nginx configuration template
# This will be processed by 30-substitute-env.sh entrypoint to inject backend URLs
COPY nginx.conf /etc/nginx/nginx.conf.template

# Copy custom entrypoints
# 30-substitute-env.sh: Substitute environment variables for backend URLs
# 40-configure-tls.sh: Enable TLS configuration if certificates are provided
COPY 30-substitute-env.sh /docker-entrypoint.d/30-substitute-env.sh
COPY docker-entrypoint.sh /docker-entrypoint.d/40-configure-tls.sh
RUN chmod +x /docker-entrypoint.d/30-substitute-env.sh /docker-entrypoint.d/40-configure-tls.sh
