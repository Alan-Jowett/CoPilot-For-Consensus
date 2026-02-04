<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Issue Resolution: Azure Cosmos DB SDK Incompatibility

## Summary

Embedding service (and potentially all Azure-deployed services) failing with `TypeError: Session.request() got an unexpected keyword argument 'partition_key'` when interacting with Azure Cosmos DB.

## Root Cause

**The azure-cosmos SDK 4.9.0's `replace_item()` method does NOT have a `partition_key` parameter**, unlike `read_item()` and `delete_item()` which do. When `partition_key` is passed to `replace_item()`, it goes into `**kwargs` and leaks through to the underlying HTTP transport layer (`requests.Session.request()`).

This is an inconsistency in the SDK API design, not a regression.

### Technical Details

1. **Error location**: `azure_cosmos_document_store.py` calling `container.replace_item(..., partition_key=...)`
2. **Error message**: `TypeError: Session.request() got an unexpected keyword argument 'partition_key'`
3. **SDK version**: azure-cosmos 4.9.0 (and likely all 4.x before 4.14.0)
4. **Solution**: Do NOT pass `partition_key` to `replace_item()` - the SDK infers it from the document body's `id` field

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

Remove the `partition_key` parameter from `replace_item()` calls. The SDK infers the partition key from the document body's `id` field:

```python
# Before (broken):
container.replace_item(item=doc_id, body=merged_doc, partition_key=partition_key_value)

# After (working):
container.replace_item(item=doc_id, body=merged_doc)  # SDK uses body["id"] as partition key
```

### Files Changed

| File | Change |
|------|--------|
| `adapters/copilot_storage/copilot_storage/azure_cosmos_document_store.py` | Removed `partition_key` from `replace_item()` call |

## Verification

After deploying with pinned SDK:
1. Check embedding service logs for successful Cosmos DB operations
2. Verify no `Session.request()` errors in logs
3. Test end-to-end pipeline: ingestion → parsing → chunking → embedding

## Prevention

1. **SDK version constraint**: azure-cosmos pinned to `<4.14.0` in setup.py
2. **Monitor azure-cosmos releases**: Track [GitHub Issue #43662](https://github.com/Azure/azure-sdk-for-python/issues/43662) for fix
3. **Dependabot constraint**: Keep the Python 3.14+ ignore rule in place until the azure-cosmos 4.14.x regression (Issue #43662) is fixed and the SDK is validated on Python 3.14+ (see `.github/dependabot.yml` and `scripts/update-dependabot.py`)

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
- **Fix Applied**: Pinned azure-cosmos SDK to `<4.14.0` in `adapters/copilot_storage/setup.py` (see "Solution"; supersedes earlier Python downgrade to 3.13)
