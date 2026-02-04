<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Issue Resolution: Azure Cosmos DB SDK API Inconsistency

## Summary

Embedding service (and potentially all Azure-deployed services) failing with `TypeError: Session.request() got an unexpected keyword argument 'partition_key'` when interacting with Azure Cosmos DB.

## Root Cause

**The azure-cosmos SDK's `replace_item()` method does NOT have a `partition_key` parameter**, unlike `read_item()` and `delete_item()` which do. When `partition_key` is passed to `replace_item()`, it goes into `**kwargs` and leaks through to the underlying HTTP transport layer (`requests.Session.request()`).

This is an inconsistency in the SDK API design that affects all versions of azure-cosmos.

### Technical Details

1. **Error location**: `azure_cosmos_document_store.py` calling `container.replace_item(..., partition_key=...)`
2. **Error message**: `TypeError: Session.request() got an unexpected keyword argument 'partition_key'`
3. **SDK versions affected**: All versions of azure-cosmos (the API inconsistency exists in all versions)
4. **Solution**: Do NOT pass `partition_key` to `replace_item()` - the SDK infers it from the document body's `id` field

### History

- Initially diagnosed as Python 3.14 incompatibility (PR #1083 downgraded to Python 3.13)
- Then diagnosed as azure-cosmos 4.14.x regression (pinned to `<4.14.0`)
- Final root cause: Our code incorrectly passed `partition_key` to `replace_item()` which doesn't support it
- The integration test that would have caught this was incorrectly skipped as "emulator limitation"

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
| `adapters/copilot_storage/tests/test_integration_azurecosmos.py` | Removed skip from `test_update_document` - now passes on emulator |

## Verification

After deploying with the fix:
1. Check embedding service logs for successful Cosmos DB operations
2. Verify no `Session.request()` errors in logs
3. Test end-to-end pipeline: ingestion → parsing → chunking → embedding
4. Verify chunks have `embedding_generated: true`

## Prevention

1. **Integration tests**: `test_update_document` now runs against the Cosmos DB emulator in CI
2. **No skipping tests for "emulator limitations"**: If a test fails on the emulator, investigate whether it's a real bug first
3. **SDK API validation**: Consider adding tests that validate SDK method signatures at runtime

## Previous Attempts

1. **PR #1083** - Downgraded Python 3.14 to 3.13 (didn't fix the issue)
2. **PR #1110** - Pinned azure-cosmos SDK to `<4.14.0` (didn't fix the issue - wrong root cause)
3. **PR #1122** - Removed `partition_key` from `replace_item()` call (actual fix)

## References

- azure-cosmos PyPI: https://pypi.org/project/azure-cosmos/
- Related Issue #30876: https://github.com/Azure/azure-sdk-for-python/issues/30876

## Timeline

- **Detection**: Embedding service failed in Azure deployment
- **Misdiagnosis 1**: Python 3.14 incompatibility
- **Misdiagnosis 2**: azure-cosmos 4.14.x regression
- **Root Cause**: Our code passed `partition_key` to `replace_item()` which doesn't support it
- **Fix Applied**: PR #1122 - Removed `partition_key` parameter from `replace_item()` call
