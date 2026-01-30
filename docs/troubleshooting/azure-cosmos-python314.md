<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Issue Resolution: Azure Cosmos DB SDK Incompatibility with Python 3.14

## Summary

Embedding service (and potentially all Azure-deployed services) failing with `TypeError: Session.request() got an unexpected keyword argument 'partition_key'` when interacting with Azure Cosmos DB.

## Root Cause

**Python 3.14 is not officially supported by the azure-cosmos SDK.** The SDK's PyPI classifiers only list Python 3.9 through 3.13. Python 3.14 introduced changes to how keyword arguments are forwarded through the HTTP request pipeline, causing the `partition_key` parameter to leak through to the underlying `requests.Session.request()` method.

### Technical Details

1. **Error location**: `azure_cosmos_document_store.py` line 565 calling `container.replace_item(item=doc_id, body=merged_doc, partition_key=partition_key_value)`
2. **Error message**: `TypeError: Session.request() got an unexpected keyword argument 'partition_key'`
3. **SDK version**: `azure-cosmos>=4.9.0,<5.0.0` (latest is 4.14.5)
4. **Python version**: 3.14-slim in all Dockerfile.azure files

### Why This Happened

- Dependabot automatically bumped the Python base image from 3.13 to 3.14 (commits #942, #881)
- The azure-cosmos SDK has not yet released support for Python 3.14
- The SDK passes `partition_key` through its internal HTTP pipeline, which worked in Python 3.13 but breaks in 3.14 due to stricter keyword argument handling

## Affected Services

All Azure-deployed services using Cosmos DB via `copilot_storage` adapter:
- embedding
- parsing
- chunking
- orchestrator
- summarization
- reporting

## Solution

Downgrade all Azure Dockerfiles from Python 3.14 to Python 3.13, which is the latest officially supported version.

### Files Changed

| File | Change |
|------|--------|
| `embedding/Dockerfile.azure` | Python 3.14-slim → 3.13-slim |
| `auth/Dockerfile.azure` | Python 3.14-slim → 3.13-slim |
| `parsing/Dockerfile.azure` | Python 3.14-slim → 3.13-slim |
| `chunking/Dockerfile.azure` | Python 3.14-slim → 3.13-slim |
| `summarization/Dockerfile.azure` | Python 3.14-slim → 3.13-slim |
| `ingestion/Dockerfile.azure` | Python 3.14-slim → 3.13-slim |
| `orchestrator/Dockerfile.azure` | Python 3.14-slim → 3.13-slim |
| `reporting/Dockerfile.azure` | Python 3.14-slim → 3.13-slim |

## Verification

After deploying with Python 3.13:
1. Check embedding service logs for successful Cosmos DB operations
2. Verify no `Session.request()` errors in logs
3. Test end-to-end pipeline: ingestion → parsing → chunking → embedding

## Prevention

1. **Dependabot constraint for Docker Python base image**: Updated `.github/dependabot.yml` to prevent the Docker ecosystem from auto-upgrading Python base images beyond 3.13 until the azure-cosmos SDK officially supports Python 3.14:

   ```yaml
   ignore:
     - dependency-name: "python"
       versions: [">=3.14"]
   ```
2. **SDK compatibility testing**: Add a CI test that validates the azure-cosmos SDK works with the Docker base image Python version used in all Azure Dockerfiles.
3. **Monitor azure-cosmos releases**: Track https://github.com/Azure/azure-sdk-for-python/releases for Python 3.14 support and update the Dependabot constraint once official support is available.

## References

- azure-cosmos PyPI: https://pypi.org/project/azure-cosmos/ (classifiers show Python 3.9-3.13 only)
- Dependabot commit: https://github.com/Alan-Jowett/CoPilot-For-Consensus/commit/442441c4 (Python 3.14 bump)
- Previous fix attempt: https://github.com/Alan-Jowett/CoPilot-For-Consensus/pull/1075 (pinned SDK version, but Python version was the real issue)

## Timeline

- **Detection**: Service failed after Dependabot Python version bump
- **RCA Duration**: ~30 minutes
- **Fix Applied**: Python downgrade to 3.13
