<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Scripts

This folder contains developer/ops helper scripts.

## Quick start

Install dependencies for the Python scripts in this directory:

```powershell
python -m pip install -r scripts/requirements.txt
```

## Notable scripts

- `peek_servicebus_dlq.py` — peeks (non-destructively) at Azure Service Bus topic subscription dead-letter messages. See the script docstring for usage.
