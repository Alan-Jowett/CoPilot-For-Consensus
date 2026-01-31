<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Issue Resolution: Azure Cosmos DB SDK Incompatibility

## Summary

Embedding service (and potentially all Azure-deployed services) failing with `TypeError: Session.request() got an unexpected keyword argument 'partition_key'` when interacting with Azure Cosmos DB.

## Root Cause

**The azure-cosmos SDK versions 4.14.x have a regression bug** where the `partition_key` parameter passed to methods like `replace_item()`, `read_item()`, and `delete_item()` leaks through to the underlying HTTP transport layer (`requests.Session.request()`).

This is tracked as [GitHub Issue #43662](https://github.com/Azure/azure-sdk-for-python/issues/43662).

### Technical Details

1. **Error location**: `azure_cosmos_document_store.py` calling `container.replace_item(item=doc_id, body=merged_doc, partition_key=partition_key_value)`
2. **Error message**: `TypeError: Session.request() got an unexpected keyword argument 'partition_key'`
3. **SDK version**: azure-cosmos 4.14.5 (broken), 4.13.x and earlier (working)
4. **Python version**: 3.13.11 (issue is NOT Python version specific)

### History

- Initially diagnosed as Python 3.14 incompatibility (PR #1083 downgraded to Python 3.13)
- After Python 3.13 deployment, issue persisted - revealing the true cause: azure-cosmos SDK 4.14.x regression
- The SDK bug causes `partition_key` to leak through internal HTTP pipeline to `requests.Session.request()`

## Affected Services

All Azure-deployed services using Cosmos DB via `copilot_storage` adapter:
- embedding
- parsing
- chunking
- orchestrator
- summarization
- reporting

## Solution

Pin azure-cosmos SDK to versions before 4.14.0 where the regression was introduced:

```python
# In adapters/copilot_storage/setup.py
"azure-cosmos>=4.9.0,<4.14.0",  # Pinned <4.14 due to partition_key bug (Issue #43662)
```

### Files Changed

| File | Change |
|------|--------|
| `adapters/copilot_storage/setup.py` | azure-cosmos version pinned to `>=4.9.0,<4.14.0` |

## Verification

After deploying with pinned SDK:
1. Check embedding service logs for successful Cosmos DB operations
2. Verify no `Session.request()` errors in logs
3. Test end-to-end pipeline: ingestion → parsing → chunking → embedding

## Prevention

1. **SDK version constraint**: azure-cosmos pinned to `<4.14.0` in setup.py
2. **Monitor azure-cosmos releases**: Track [GitHub Issue #43662](https://github.com/Azure/azure-sdk-for-python/issues/43662) for fix
3. **Dependabot constraint**: Keep Python 3.14+ ignore rule until azure-cosmos officially supports it

## Previous Attempts

1. **PR #1083** - Downgraded Python 3.14 to 3.13 (helped, but didn't fix the SDK bug)
2. **This fix** - Pins azure-cosmos SDK to working version

## References

- azure-cosmos PyPI: https://pypi.org/project/azure-cosmos/
- SDK Bug: https://github.com/Azure/azure-sdk-for-python/issues/43662
- Related Issue #30876: https://github.com/Azure/azure-sdk-for-python/issues/30876

## Timeline

- **Detection**: Service failed after Dependabot Python version bump
- **RCA Duration**: ~30 minutes
- **Fix Applied**: Python downgrade to 3.13
