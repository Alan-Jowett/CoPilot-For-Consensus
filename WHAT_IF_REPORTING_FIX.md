# What-If Analysis Reporting Fix

## Problem Statement
The CI validation workflow reported "What-if analysis completed" as success even when the what-if step failed. This was due to:
1. `continue-on-error: true` masking failures in the what-if step
2. PR comments always showing success checkmark when the validation job succeeded, regardless of what-if outcome

## Solution Implemented
Implemented **Option B** from issue: Capture what-if outcome and report accurate status in PR comments.

## Changes Made

### 1. Added Job Output to `validate-template` Job
```yaml
validate-template:
  name: ARM Template Validation
  runs-on: ubuntu-latest
  needs: bicep-lint
  outputs:
    whatif-status: ${{ steps.whatif-step.outputs.status }}
```

This exposes the what-if status to downstream jobs.

### 2. Modified "Run what-if analysis (dev)" Step
```yaml
- name: Run what-if analysis (dev)
  id: whatif-step
  continue-on-error: true
  run: |
    cd infra/azure

    # Run what-if and capture exit code
    set +e
    az deployment group what-if \
      --resource-group ${{ env.VALIDATION_RESOURCE_GROUP }} \
      --template-file main.bicep \
      --parameters parameters.dev.json \
      --output json > what-if-output.json
    WHATIF_EXIT_CODE=$?
    set -e

    # Set output based on exit code
    if [ $WHATIF_EXIT_CODE -eq 0 ]; then
      echo "status=success" >> $GITHUB_OUTPUT
      echo "✓ What-if analysis completed successfully"
    else
      echo "status=failed" >> $GITHUB_OUTPUT
      echo "⚠️ What-if analysis failed with exit code: $WHATIF_EXIT_CODE"
    fi
```

Key changes:
- Added `id: whatif-step` to reference the step
- Used `set +e` to allow command to fail without stopping the script
- Captured exit code in `WHATIF_EXIT_CODE` variable
- Used `set -e` to restore error handling
- Set appropriate status to `$GITHUB_OUTPUT` based on exit code

### 3. Updated PR Comment Logic
```javascript
const whatif_status = '${{ needs.validate-template.outputs.whatif-status }}';

// Inside the validation success block:
// Report what-if status based on captured exit code
if (whatif_status === 'success') {
  details += '- ✓ What-if analysis completed successfully\n';
} else if (whatif_status === 'failed') {
  details += '- ⚠️ What-if analysis failed (but syntax validation passed)\n';
} else {
  details += '- ⚠️ What-if analysis status unknown\n';
}
```

Now the PR comment accurately reflects the what-if outcome instead of always showing success.

## Behavior After Fix

### When What-If Succeeds (exit code 0)
- Step completes successfully
- Output: `status=success`
- PR comment: "✓ What-if analysis completed successfully"
- Validation job: ✅ Success

### When What-If Fails (exit code != 0)
- Step fails but is caught by `continue-on-error: true`
- Output: `status=failed`
- PR comment: "⚠️ What-if analysis failed (but syntax validation passed)"
- Validation job: ✅ Success (doesn't block CI)

### Edge Case: Status Unknown
- Output is not set or empty
- PR comment: "⚠️ What-if analysis status unknown"
- Validation job: ✅ Success

## Benefits
1. **Accurate PR feedback**: Reviewers see the actual what-if status
2. **Non-blocking**: What-if failures don't block CI (preserved behavior)
3. **Clear distinction**: Success vs. failure is clearly indicated
4. **Debugging**: Exit code is logged for troubleshooting

## Testing
To test this fix:
1. Create a PR that modifies Bicep files in `infra/azure/`
2. Wait for the workflow to complete
3. Verify PR comment shows accurate what-if status
4. Check workflow logs to see captured exit code

## Related Files
- `.github/workflows/bicep-validate.yml`: Modified workflow file
- Issue: "bug: CI what-if analysis reports success even when it fails"

## References
- GitHub Actions: Job outputs - https://docs.github.com/en/actions/using-jobs/defining-outputs-for-jobs
- GitHub Actions: continue-on-error - https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#jobsjob_idcontinue-on-error
- Bash exit codes and error handling
