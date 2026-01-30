<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Issue Resolution: Azure Service Bus Subscription Filter Rules Not Applied

## Summary

After deploying commit `3a44511c` (Add server-side SQL filters to Azure Service Bus subscriptions), messages published to the `copilot.events` topic were not being delivered to any subscriptions. This caused the entire pipeline to stall after ingestion - parsing never received `ArchiveIngested` events.

## Root Cause

The Bicep template named the SQL filter rules `$Default` with the intention of replacing the auto-created `$Default` TrueFilter rule. However, this approach has a critical flaw:

1. When a subscription is created, Azure Service Bus **automatically** creates a `$Default` rule with a TrueFilter (matches all messages)
2. When Bicep/ARM then tries to create a rule also named `$Default` with a SqlFilter, the behavior is undefined:
   - ARM reports the operation as "Succeeded"
   - But the rule either doesn't persist or is immediately deleted
   - The result is a subscription with **no rules at all**
3. In Azure Service Bus, a subscription with no rules **delivers no messages**

## Symptoms

- Ingestion service logs showed `files_processed: 1` and `Ingestion completed` 
- No errors in ingestion logs
- Azure Monitor showed incoming messages to the topic
- No messages appeared in any subscription
- Parsing service showed no activity (scaled to 0 due to KEDA with no messages)

## Investigation Steps

1. Checked ingestion logs - confirmed successful ingestion
2. Checked Azure Service Bus metrics - messages were arriving at the topic
3. Examined subscription rules:
   ```powershell
   az servicebus topic subscription rule list --subscription-name parsing ...
   ```
   Result: Empty array `[]` - no rules existed!

4. Attempted to manually create `$Default` rule - it was immediately deleted
5. Created a rule with a different name (`EventTypeFilter`) - it persisted

## Fix

Changed the rule name from `$Default` to `EventTypeFilter` in the Bicep template:

```bicep
// Before (broken)
resource subscriptionFilters '...' = [
  for (service, i) in receiverServices: {
    name: '$Default'  // Does not work as intended
    ...
  }
]

// After (working)
resource subscriptionFilters '...' = [
  for (service, i) in receiverServices: {
    name: 'EventTypeFilter'  // Custom name works correctly
    ...
  }
]
```

Key insight: When at least one custom rule is defined during subscription creation (via Bicep), Azure Service Bus **does not auto-create** the `$Default` TrueFilter rule. This is the documented and intended behavior.

## Files Changed

- `infra/azure/modules/servicebus.bicep` - Changed rule name from `$Default` to `EventTypeFilter`
- `tests/infra/azure/test_servicebus_filters.py` - Updated test assertion to check for `EventTypeFilter`
- `docs/troubleshooting/servicebus-filter-rules.md` - New troubleshooting document for Service Bus subscription filter rules incident

## Deployment Steps

After applying the fix, redeploy the Service Bus module:

**Linux/macOS (bash):**
```bash
# Delete existing subscriptions (they have no rules anyway)
for sub in parsing chunking embedding orchestrator summarization reporting; do
  az servicebus topic subscription delete \
    --resource-group copilot-app-rg \
    --namespace-name <namespace> \
    --topic-name copilot.events \
    --subscription-name $sub
done

# Redeploy the Bicep template
az deployment group create \
  --resource-group copilot-app-rg \
  --template-file infra/azure/modules/servicebus.bicep \
  --parameters <your-params.json>
```

**Windows (PowerShell):**
```powershell
# Delete existing subscriptions (they have no rules anyway)
$subs = @('parsing', 'chunking', 'embedding', 'orchestrator', 'summarization', 'reporting')
foreach ($sub in $subs) {
  az servicebus topic subscription delete `
    --resource-group copilot-app-rg `
    --namespace-name <namespace> `
    --topic-name copilot.events `
    --subscription-name $sub
}

# Redeploy the Bicep template
az deployment group create `
  --resource-group copilot-app-rg `
  --template-file infra/azure/modules/servicebus.bicep `
  --parameters <your-params.json>
```

## Verification

After redeployment, verify rules exist:

```bash
az servicebus topic subscription rule list \
  --resource-group copilot-app-rg \
  --namespace-name <namespace> \
  --topic-name copilot.events \
  --subscription-name parsing \
  --query "[].{Name:name, Filter:sqlFilter.sqlExpression}" \
  -o table
```

Expected output:
```
Name             Filter
---------------  ------------------------------------------------------------
EventTypeFilter  event_type IN ('ArchiveIngested', 'SourceDeletionRequested')
```

## Lessons Learned

1. **Don't rely on replacing `$Default` rules in Bicep/ARM** - Use unique rule names instead
2. **Verify subscription rules after deployment** - A deployment can succeed even if rules don't persist
3. **Monitor message delivery, not just topic ingress** - Topic metrics alone don't show subscription-level issues
4. **Test filter behavior in a dev environment before production** - SQL filter syntax and rule naming edge cases can cause silent failures

## References

- [Azure Service Bus topic filters](https://docs.microsoft.com/en-us/azure/service-bus-messaging/topic-filters)
- [Terraform issue on default rule filter](https://github.com/hashicorp/terraform-provider-azurerm/issues/20718)
- [Bicep Service Bus examples](https://alanparr.github.io/bicep-create-servicebus-with-topic-and-subscription)
