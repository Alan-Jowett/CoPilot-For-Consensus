#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import os
import time
from typing import Dict

from prometheus_client import Gauge, start_http_server
from pymongo import MongoClient


MONGO_URI = os.environ.get("MONGO_URI", "mongodb://root:example@documentdb:27017/admin")
DB_NAME = os.environ.get("MONGO_DB", "copilot")
PORT = int(os.environ.get("PORT", "9500"))
INTERVAL = float(os.environ.get("SCRAPE_INTERVAL_SEC", "5"))


doc_count_gauge = Gauge(
    "copilot_collection_document_count",
    "Document count per MongoDB collection",
    ["database", "collection"],
)


def get_counts(client: MongoClient) -> Dict[str, int]:
    db = client[DB_NAME]
    counts = {}
    # target collections
    for coll in ["archives", "messages", "chunks", "threads", "summaries"]:
        try:
            counts[coll] = db[coll].count_documents({})
        except Exception:
            counts[coll] = 0
    return counts


def main():
    start_http_server(PORT)
    client = MongoClient(MONGO_URI, directConnection=True)
    while True:
        counts = get_counts(client)
        for coll, value in counts.items():
            doc_count_gauge.labels(database=DB_NAME, collection=coll).set(value)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
