<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# CI Coverage Strategy

## Overview

This document describes the CI/CD and code coverage strategy for the Copilot-for-Consensus monorepo. The strategy ensures that code coverage metrics on the `main` branch are stable, comprehensive, and reliable.

## Problem Statement

Previously, code coverage on `main` fluctuated wildly depending on which services or test suites were triggered by path-based filters in prior commits. This made coverage metrics unreliable and could mask regressions, as only changed services would run tests.

## Solution

The CI workflows have been updated to ensure comprehensive test coverage:

### 1. Full Test Execution on Main Branch

On every push to the `main` branch, **all** tests run across all services and adapters, regardless of which files were changed. This ensures:

- Consistent, comparable coverage numbers for the branch of record
- No regressions can be hidden by partial test execution
- Coverage metrics reflect the entire codebase state

### 2. Selective Test Execution on Pull Requests

For pull requests, the CI uses path-based filtering to run only tests for changed components. This provides:

- Faster CI feedback during development
- Reduced resource consumption for PR validation
- Early detection of issues in changed components

### 3. Coverage Aggregation

Coverage data is collected and aggregated using Coveralls with the following approach:

#### Parallel Coverage Upload

Each service and adapter uploads its coverage independently with:
- `parallel: true` flag to indicate partial coverage
- Unique `flag-name` to identify the source (e.g., `chunking`, `copilot_events`)
- LCOV format for compatibility

#### Coverage Finalization

After all tests complete on `main` branch pushes, a final aggregation step:
- Uses `parallel-finished: true` to signal completion
- Combines all coverage reports into a single metric
- Uses `carryforward` to include all component flags

## Workflow Structure

### Services CI (`services-ci.yml`)

**Jobs:**
- `detect-changes`: Runs only on pull requests to determine changed services
- Service jobs (`chunking`, `embedding`, `ingestion`, `orchestrator`, `parsing`, `reporting`, `summarization`, `error-reporting`):
  - On PR: Run only if the service or its dependencies changed
  - On main push: Always run
  - On schedule/manual: Always run
- `coverage-summary`: Runs only on main pushes to finalize coverage aggregation

**Coverage Flags:**
- `chunking`
- `embedding`
- `ingestion`
- `orchestrator`
- `parsing`
- `reporting`
- `summarization`
- `error-reporting`

### Adapters CI (`adapters-ci.yml`)

**Jobs:**
- `detect-changes`: Runs only on pull requests to determine changed adapters
- Adapter jobs (15 adapters including unit and integration tests):
  - On PR: Run only if the adapter changed
  - On main push: Always run
  - On schedule/manual: Always run
- `coverage-summary`: Runs only on main pushes to finalize coverage aggregation

**Coverage Flags:**
- `copilot_auth`
- `copilot_config`
- `copilot_events`
- `copilot_logging`
- `copilot_metrics`
- `copilot_archive_fetcher`
- `copilot_reporting`
- `copilot_storage`
- `copilot_embedding`
- `copilot_chunking`
- `copilot_consensus`
- `copilot_schema_validation`
- `copilot_summarization`
- `copilot_vectorstore`
- `copilot_draft_diff`

## Implementation Details

### Conditional Logic

The workflows use GitHub Actions conditional expressions:

```yaml
# detect-changes job only runs on pull requests
if: ${{ github.event_name != 'schedule' && github.event_name != 'workflow_dispatch' && github.event_name == 'pull_request' }}

# Test jobs run on:
# - All pushes (including main)
# - Schedule/manual triggers
# - PR when the component changed
if: ${{ always() && (github.event_name == 'schedule' || github.event_name == 'workflow_dispatch' || github.event_name == 'push' || needs.detect-changes.outputs.<component> == 'true' || needs.detect-changes.outputs.ci-workflows == 'true') }}

# Coverage summary only runs on main branch pushes
if: ${{ always() && github.event_name == 'push' && github.ref == 'refs/heads/main' }}
```

### Coverage Upload Configuration

Reusable test workflows include:

```yaml
- name: Upload coverage to Coveralls
  continue-on-error: true
  uses: coverallsapp/github-action@v2
  with:
    github-token: ${{ github.token }}
    path-to-lcov: ./path/to/coverage.lcov
    flag-name: <component-name>
    parallel: true  # Indicates this is partial coverage
```

Coverage finalization in main workflows:

```yaml
- name: Finalize coverage upload
  uses: coverallsapp/github-action@v2
  with:
    github-token: ${{ github.token }}
    parallel-finished: true
    carryforward: "component1,component2,component3,..."
```

## Benefits

1. **Stable Coverage Metrics**: Every commit to `main` generates a consistent coverage percentage based on the full test suite
2. **Regression Prevention**: No changes can slip through without full test coverage being computed
3. **Efficient PR Testing**: Pull requests still benefit from fast, targeted test execution
4. **Comprehensive Visibility**: All components are tested and coverage is tracked per component
5. **Artifact Retention**: Coverage reports and test results are uploaded as artifacts for inspection

## Coverage Artifact Retention

Each test job uploads:
- Test results (JUnit XML format) for test reporting
- Coverage reports (HTML format) for detailed inspection
- Coverage data (LCOV format) for aggregation

These artifacts are available in the GitHub Actions run for 90 days (default retention).

## Accessing Coverage Reports

### Via Coveralls

Coverage trends and detailed reports are available at:
- Repository: https://coveralls.io/github/Alan-Jowett/CoPilot-For-Consensus
- Per-component coverage visible via flags
- Historical trends for `main` branch

### Via GitHub Actions

Individual coverage reports can be downloaded from:
1. Navigate to Actions tab
2. Select the workflow run
3. Scroll to "Artifacts" section
4. Download `<component>-coverage-report` for HTML reports

## Testing the Strategy

To verify the coverage strategy is working:

1. **Push to a feature branch**: Only changed components should run tests
2. **Push to main branch**: All components should run tests
3. **Check Coveralls**: Verify coverage is aggregated and stable
4. **Review artifacts**: Confirm coverage reports are uploaded for all components

## Future Improvements

Potential enhancements to consider:

1. **Coverage Thresholds**: Fail builds if coverage drops below a threshold
2. **Differential Coverage**: Show coverage change between PR and main
3. **Coverage Comments**: Automatically comment on PRs with coverage impact
4. **Code Coverage Badges**: Add badges to README showing main branch coverage
5. **Multi-Format Reports**: Generate additional report formats (Cobertura, XML)

## Related Documentation

- [TESTING_MESSAGE_BUS.md](./TESTING_MESSAGE_BUS.md) - Testing strategies for RabbitMQ
- [CONTRIBUTING.md](./CONTRIBUTING.md) - General contribution guidelines
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture overview
