<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Dependency Management Improvements - Implementation Summary

This document summarizes the improvements made to Dependabot coverage and dependency management for the CoPilot-for-Consensus project.

## Problem Statement

Prior to these changes, the project faced several dependency management challenges:

1. **Ranged dependencies** (`>=`) gave Dependabot nothing to bump in manifests
2. **Missing transitives**: Dependencies like `starlette` (via `fastapi`) weren't tracked
3. **No labels/triage**: Dependabot PRs lacked labels for filtering
4. **Supply chain risk**: Unpinned dependencies could fetch compromised releases

## Solution Overview

We implemented a comprehensive dependency management strategy using **pip-tools** for lockfiles and enhanced Dependabot configuration.

## Changes Made

### Phase 1: Enhanced Dependabot Configuration

**Updated Files:**
- `.github/dependabot.yml`
- `scripts/update-dependabot.py`

**Improvements:**
- Added labels to all Dependabot PRs:
  - `dependencies` (common label)
  - Ecosystem-specific: `python`, `javascript`, `docker`, `github-actions`
- Updated script to detect both `requirements.txt` and `requirements.in` files
- Enhanced CI workflow to validate `requirements.in` changes

**Benefits:**
- Easy filtering of dependency PRs by label
- Better visibility into what type of dependencies are being updated
- Automatic categorization for triage

### Phase 2: pip-tools Foundation

**Updated Files:**
- `requirements-dev.txt` (added pip-tools==7.5.2)
- `.github/workflows/validate-lockfiles.yml` (new CI workflow)
- `scripts/convert_to_lockfiles.py` (new helper script)

**Improvements:**
- Added pip-tools to development dependencies
- Created CI workflow to validate lockfiles are in sync with `.in` files
- Built automation to convert existing services to lockfile workflow

**Benefits:**
- Consistent tooling across development and CI
- Automated validation prevents outdated lockfiles
- Easy rollout to all services

### Phase 3: Service-Wide Lockfile Adoption

**Updated Files (per service):**
- `auth/requirements.in` (new)
- `chunking/requirements.in` (new)
- `embedding/requirements.in` (new)
- `ingestion/requirements.in` (new)
- `orchestrator/requirements.in` (new)
- `parsing/requirements.in` (new)
- `reporting/requirements.in` (new)
- `summarization/requirements.in` (new)
- Corresponding `requirements.txt` files (regenerated as lockfiles)

**Improvements:**
- Each service now has:
  - `requirements.in`: Direct dependencies with version ranges (`>=`)
  - `requirements.txt`: Auto-generated lockfile with pinned versions including ALL transitive dependencies
- Transitive dependencies now explicitly tracked (e.g., `starlette==0.50.0` via `fastapi`)

**Example - Before:**
```
# requirements.txt
fastapi==0.127.0
# starlette not tracked - invisible to Dependabot
```

**Example - After:**
```
# requirements.in
fastapi>=0.127.0

# requirements.txt (generated)
fastapi==0.128.0
starlette==0.50.0  # ← Now explicitly tracked!
```

### Phase 4: Documentation Updates

**Updated Files:**
- `CONTRIBUTING.md` (added Dependency Management section)
- `auth/README.md` (added Dependency Management section)

**Improvements:**
- Comprehensive guide on updating dependencies
- Explanation of lockfile workflow
- CI validation instructions
- Security benefits documented

## Key Benefits Achieved

### 1. Transitive Dependency Tracking

**Before:** Dependabot couldn't detect updates to `starlette` because it's not directly required
**After:** `starlette==0.50.0` is explicitly listed in all service lockfiles

This means security updates for transitive dependencies will now appear in Dependabot PRs!

### 2. Repeatable Builds

**Before:** Different environments could install different versions of dependencies
**After:** Exact versions locked in `requirements.txt` ensure identical builds everywhere

### 3. Supply Chain Security

**Before:** New releases installed automatically without review
**After:** All version changes require PR review and CI validation

### 4. Better Dependabot Integration

**Before:** Generic PRs with no labels, hard to triage
**After:** Labeled PRs that are easy to filter and prioritize

### 5. CI Validation

**Before:** No validation of dependency consistency
**After:** CI fails if lockfiles are out of sync with `.in` files

## Workflow for Developers

### Adding/Updating a Dependency

1. Edit `requirements.in` in the service directory
2. Run `pip-compile requirements.in`
3. Commit both `requirements.in` and `requirements.txt`

### Responding to Dependabot PRs

1. Dependabot updates `requirements.in` file
2. Developer reviews the PR
3. If approved, regenerate lockfile: `pip-compile requirements.in`
4. Commit the updated `requirements.txt`
5. CI validates lockfile is in sync

## Files Structure

```
auth/
├── requirements.in          # Direct dependencies with >= ranges
├── requirements.txt         # Lockfile (pip-compile output) - DO NOT EDIT MANUALLY
└── README.md               # Includes dependency management guide

chunking/
├── requirements.in
└── requirements.txt

# ... same pattern for all services
```

## CI Integration

### Workflow: validate-lockfiles.yml

- **Trigger**: On PR with changes to `requirements.in` or `requirements.txt`
- **Action**:
  1. Runs `pip-compile requirements.in`
  2. Compares output with committed `requirements.txt`
  3. Fails if they don't match
- **Matrix**: Tests all services (auth, chunking, embedding, etc.)

### Workflow: check-dependabot.yml

- **Trigger**: On PR with changes to requirements files or dependabot config
- **Action**:
  1. Regenerates `dependabot.yml` from script
  2. Compares with committed version
  3. Creates/updates issue if out of sync

## Verification

### Transitive Dependencies Now Tracked

All services now explicitly list transitive dependencies in their lockfiles:

```bash
$ grep "starlette" */requirements.txt
auth/requirements.txt:starlette==0.50.0
chunking/requirements.txt:starlette==0.50.0
embedding/requirements.txt:starlette==0.50.0
ingestion/requirements.txt:starlette==0.50.0
# ... all services
```

### Labels Applied to Dependabot PRs

The next Dependabot PRs will include:
- `dependencies` (all PRs)
- `python` (for Python dependency updates)
- `javascript` (for npm updates)
- `docker` (for Docker image updates)
- `github-actions` (for Actions updates)

## Future Enhancements

Potential next steps (not in current scope):

1. **Auto-merge**: Configure Dependabot to auto-merge patch/minor security updates
2. **Renovate Bot**: Evaluate as alternative to Dependabot with better lockfile support
3. **Separate schedules**: Different update cadences for major/minor/patch
4. **Adapter lockfiles**: Consider adding lockfiles for development/testing of adapters
5. **Automated lockfile regeneration**: Have Dependabot automatically regenerate lockfiles in PRs

## Testing

All changes have been validated:

1. ✅ Lockfile generation works for all services
2. ✅ CI workflow validates lockfile sync correctly
3. ✅ Dependabot config regeneration includes all services
4. ✅ Documentation is comprehensive and accurate
5. ✅ No breaking changes to existing workflows

## References

- **pip-tools documentation**: https://github.com/jazzband/pip-tools
- **Dependabot configuration**: https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file
- **Issue**: Alan-Jowett/CoPilot-For-Consensus (tracked in original issue)
- **Security PR**: Alan-Jowett/CoPilot-For-Consensus#791 (security updates that Dependabot missed)
