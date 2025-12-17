#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
MongoDB Collection Stats Exporter for Prometheus.

Exposes MongoDB collection-level storage metrics including:
- Storage size per collection
- Document count per collection
- Average object size
- Index sizes
- Total index size

Environment Variables:
    MONGO_URI: MongoDB connection URI (default: mongodb://root:example@documentdb:27017/admin)
    MONGO_DB: Database name to monitor (default: copilot)
    PORT: Exporter HTTP port (default: 9502)
    SCRAPE_INTERVAL_SEC: Metrics collection interval (default: 5)
"""

import os
import time
from typing import Dict, Any

from prometheus_client import Gauge, start_http_server
from pymongo import MongoClient


# Configuration
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://root:example@documentdb:27017/admin")
DB_NAME = os.environ.get("MONGO_DB", "copilot")
PORT = int(os.environ.get("PORT", "9502"))
INTERVAL = float(os.environ.get("SCRAPE_INTERVAL_SEC", "5"))


# Prometheus metrics
storage_size_gauge = Gauge(
    "mongodb_collstats_storageSize",
    "Storage size of a MongoDB collection in bytes",
    ["db", "collection"],
)

count_gauge = Gauge(
    "mongodb_collstats_count",
    "Number of documents in a MongoDB collection",
    ["db", "collection"],
)

avg_obj_size_gauge = Gauge(
    "mongodb_collstats_avgObjSize",
    "Average object size in bytes for a MongoDB collection",
    ["db", "collection"],
)

total_index_size_gauge = Gauge(
    "mongodb_collstats_totalIndexSize",
    "Total size of all indexes in bytes for a MongoDB collection",
    ["db", "collection"],
)

index_sizes_gauge = Gauge(
    "mongodb_collstats_indexSize",
    "Size of a specific index in bytes",
    ["db", "collection", "index"],
)


# Target collections to monitor
TARGET_COLLECTIONS = [
    "archives",
    "messages", 
    "chunks",
    "threads",
    "summaries",
    "reports",
    "sources",
]


def get_collection_stats(db, collection_name: str) -> Dict[str, Any]:
    """Get collection statistics from MongoDB."""
    try:
        stats = db.command("collStats", collection_name)
        return stats
    except Exception as e:
        print(f"Error fetching stats for collection {collection_name}: {e}")
        return {}


def collect_metrics(client: MongoClient) -> None:
    """Collect and update all collection stats metrics."""
    db = client[DB_NAME]
    
    for collection_name in TARGET_COLLECTIONS:
        try:
            stats = get_collection_stats(db, collection_name)
            
            if not stats:
                continue
            
            # Storage size
            if "storageSize" in stats:
                storage_size_gauge.labels(
                    db=DB_NAME, 
                    collection=collection_name
                ).set(stats["storageSize"])
            
            # Document count
            if "count" in stats:
                count_gauge.labels(
                    db=DB_NAME,
                    collection=collection_name
                ).set(stats["count"])
            
            # Average object size
            if "avgObjSize" in stats:
                avg_obj_size_gauge.labels(
                    db=DB_NAME,
                    collection=collection_name
                ).set(stats["avgObjSize"])
            
            # Total index size
            if "totalIndexSize" in stats:
                total_index_size_gauge.labels(
                    db=DB_NAME,
                    collection=collection_name
                ).set(stats["totalIndexSize"])
            
            # Individual index sizes
            if "indexSizes" in stats:
                for index_name, index_size in stats["indexSizes"].items():
                    index_sizes_gauge.labels(
                        db=DB_NAME,
                        collection=collection_name,
                        index=index_name
                    ).set(index_size)
            
            print(
                f"Collection '{collection_name}': "
                f"{stats.get('count', 0)} docs, "
                f"{stats.get('storageSize', 0)} bytes storage, "
                f"{stats.get('totalIndexSize', 0)} bytes indexes"
            )
            
        except Exception as e:
            print(f"Error collecting metrics for {collection_name}: {e}")


def main():
    """Main exporter loop."""
    print(f"Starting MongoDB CollStats exporter on port {PORT}")
    print(f"MongoDB URI: {MONGO_URI}")
    print(f"Database: {DB_NAME}")
    print(f"Scrape interval: {INTERVAL}s")
    
    # Start Prometheus HTTP server
    start_http_server(PORT)
    print(f"Metrics endpoint available at http://0.0.0.0:{PORT}/metrics")
    
    # Connect to MongoDB
    client = MongoClient(MONGO_URI, directConnection=True)
    
    # Main scrape loop
    while True:
        collect_metrics(client)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
