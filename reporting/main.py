# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import logging
from flask import Flask

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "reporting"}, 200

@app.route("/api/reports", methods=["GET"])
def get_reports():
    """Retrieve generated reports."""
    return {"reports": []}, 200

if __name__ == "__main__":
    logger.info("Starting Reporting Service on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
