#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Qdrant Metrics Exporter for Prometheus.

Exposes Qdrant vectorstore metrics including:
- Vector counts per collection
- Collection sizes and memory usage
- Query/search performance metrics
- Index status and health

Environment Variables:
    QDRANT_HOST: Qdrant host (default: vectorstore)
    QDRANT_PORT: Qdrant port (default: 6333)
    PORT: Exporter HTTP port (default: 9501)
    SCRAPE_INTERVAL_SEC: Metrics collection interval (default: 5)
"""

import os
import time
from typing import Dict, List, Any

import requests
from prometheus_client import Gauge, Counter, Histogram, start_http_server


# Configuration
QDRANT_HOST = os.environ.get("QDRANT_HOST", "vectorstore")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
PORT = int(os.environ.get("PORT", "9501"))
INTERVAL = float(os.environ.get("SCRAPE_INTERVAL_SEC", "5"))
QDRANT_BASE_URL = f"http://{QDRANT_HOST}:{QDRANT_PORT}"

# Prometheus metrics
vector_count_gauge = Gauge(
    "qdrant_collection_vectors_count",
    "Total number of vectors in a Qdrant collection",
    ["collection"],
)

collection_size_bytes = Gauge(
    "qdrant_collection_size_bytes",
    "Storage size of a Qdrant collection in bytes",
    ["collection"],
)

collection_indexed_vectors = Gauge(
    "qdrant_collection_indexed_vectors_count",
    "Number of indexed vectors in a collection",
    ["collection"],
)

collection_segments = Gauge(
    "qdrant_collection_segments_count",
    "Number of segments in a collection",
    ["collection"],
)

qdrant_memory_usage_bytes = Gauge(
    "qdrant_memory_usage_bytes",
    "Qdrant memory usage in bytes (if available)",
    [],
)

qdrant_scrape_success = Gauge(
    "qdrant_scrape_success",
    "Whether the last scrape of Qdrant metrics was successful",
    [],
)

qdrant_scrape_errors_total = Counter(
    "qdrant_scrape_errors_total",
    "Total number of errors while scraping Qdrant metrics",
    [],
)

qdrant_scrape_duration_seconds = Histogram(
    "qdrant_scrape_duration_seconds",
    "Time spent scraping Qdrant metrics",
    [],
)


def get_collections() -> List[str]:
    """Get list of collection names from Qdrant."""
    try:
        resp = requests.get(f"{QDRANT_BASE_URL}/collections", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        # Qdrant returns {"result": {"collections": [{"name": "..."}, ...]}}
        if "result" in data and "collections" in data["result"]:
            return [c["name"] for c in data["result"]["collections"]]
        return []
    except Exception as e:
        print(f"Error fetching collections: {e}")
        return []


def get_collection_info(collection_name: str) -> Dict[str, Any]:
    """Get detailed information about a specific collection."""
    try:
        resp = requests.get(
            f"{QDRANT_BASE_URL}/collections/{collection_name}",
            timeout=5
        )
        resp.raise_for_status()
        data = resp.json()
        
        # Qdrant returns {"result": {...collection info...}}
        if "result" in data:
            return data["result"]
        return {}
    except Exception as e:
        print(f"Error fetching collection info for {collection_name}: {e}")
        return {}


def extract_metrics_from_collection_info(info: Dict[str, Any]) -> Dict[str, Any]:
    """Extract relevant metrics from collection info response."""
    metrics = {
        "vectors_count": 0,
        "indexed_vectors_count": 0,
        "points_count": 0,
        "segments_count": 0,
        "disk_data_size": 0,
    }
    
    if not info:
        return metrics
    
    # Points count (total vectors)
    if "points_count" in info:
        metrics["points_count"] = info["points_count"]
        metrics["vectors_count"] = info["points_count"]
    
    # Indexed vectors count
    if "indexed_vectors_count" in info:
        metrics["indexed_vectors_count"] = info["indexed_vectors_count"]
    
    # Segments count
    if "segments_count" in info:
        metrics["segments_count"] = info["segments_count"]
    
    # Storage size
    # Check different possible locations for size info
    if "config" in info and "optimizer_config" in info["config"]:
        optimizer = info["config"]["optimizer_config"]
        if "deleted_threshold" in optimizer:
            pass  # Size not directly available in config
    
    # Try to get size from status
    if "status" in info:
        status = info["status"]
        if isinstance(status, dict):
            # Size might be in different locations depending on Qdrant version
            for key in ["disk_data_size", "disk_size", "vectors_size"]:
                if key in status:
                    metrics["disk_data_size"] = status[key]
                    break
    
    return metrics


def scrape_qdrant_metrics():
    """Scrape all Qdrant metrics and update Prometheus gauges."""
    start_time = time.time()
    success = True
    
    try:
        # Get all collections
        collections = get_collections()
        
        if not collections:
            print("No collections found or unable to fetch collections list")
            # Don't treat empty collections as an error
            # Could be a fresh install
        
        # Collect metrics for each collection
        for collection_name in collections:
            info = get_collection_info(collection_name)
            metrics = extract_metrics_from_collection_info(info)
            
            # Update Prometheus metrics
            vector_count_gauge.labels(collection=collection_name).set(
                metrics["vectors_count"]
            )
            collection_indexed_vectors.labels(collection=collection_name).set(
                metrics["indexed_vectors_count"]
            )
            collection_segments.labels(collection=collection_name).set(
                metrics["segments_count"]
            )
            collection_size_bytes.labels(collection=collection_name).set(
                metrics["disk_data_size"]
            )
            
            print(
                f"Collection '{collection_name}': "
                f"{metrics['vectors_count']} vectors, "
                f"{metrics['indexed_vectors_count']} indexed, "
                f"{metrics['segments_count']} segments, "
                f"{metrics['disk_data_size']} bytes"
            )
        
        # Try to get cluster/node telemetry if available
        try:
            telemetry_resp = requests.get(
                f"{QDRANT_BASE_URL}/telemetry",
                timeout=5
            )
            if telemetry_resp.status_code == 200:
                telemetry = telemetry_resp.json()
                # Extract memory usage if available
                # Telemetry structure varies by version
                # Example path: result.app.mem_rss
                if "result" in telemetry:
                    result = telemetry["result"]
                    if "app" in result and "mem_rss" in result["app"]:
                        mem_bytes = result["app"]["mem_rss"]
                        qdrant_memory_usage_bytes.set(mem_bytes)
        except Exception as e:
            # Telemetry endpoint might not be available in all versions
            print(f"Telemetry not available: {e}")
        
        qdrant_scrape_success.set(1)
        
    except Exception as e:
        print(f"Error during scrape: {e}")
        qdrant_scrape_errors_total.inc()
        qdrant_scrape_success.set(0)
        success = False
    
    finally:
        duration = time.time() - start_time
        qdrant_scrape_duration_seconds.observe(duration)
        print(f"Scrape completed in {duration:.2f}s, success={success}")


def main():
    """Main exporter loop."""
    print(f"Starting Qdrant exporter on port {PORT}")
    print(f"Qdrant URL: {QDRANT_BASE_URL}")
    print(f"Scrape interval: {INTERVAL}s")
    
    # Start Prometheus HTTP server
    start_http_server(PORT)
    print(f"Metrics endpoint available at http://0.0.0.0:{PORT}/metrics")
    
    # Main scrape loop
    while True:
        scrape_qdrant_metrics()
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
