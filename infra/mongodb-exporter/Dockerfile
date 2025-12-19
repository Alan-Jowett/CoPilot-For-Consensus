# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Wrapper for Percona MongoDB Exporter to support Docker secrets
# This image provides a shell entrypoint that reads secrets and constructs MONGODB_URI
FROM alpine:3.20@sha256:765942a4039992336de8dd5db680586e1a206607dd06170ff0a37267a9e01958

# Install the Percona MongoDB Exporter binary
# We copy it from the official image to maintain version consistency
COPY --from=percona/mongodb_exporter:0.40@sha256:d66daa6aff0513860d1577cee3b55ab82fde43394f8319d7b4674411b9153cce /mongodb_exporter /mongodb_exporter

# Create a non-root user for running the exporter
RUN addgroup -g 1001 exporter && \
    adduser -D -u 1001 -G exporter exporter && \
    chmod +x /mongodb_exporter

USER exporter

ENTRYPOINT ["/bin/sh"]
