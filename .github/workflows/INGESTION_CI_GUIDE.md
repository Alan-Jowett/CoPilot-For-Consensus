# Ingestion Service CI Workflow

## Overview

The `ingestion-ci.yml` GitHub Actions workflow automatically tests the ingestion service on every push and pull request.

## Workflow Triggers

The workflow runs when:
- Code is pushed to `main` branches (with changes in `ingestion/` directory)
- A pull request is made to `main` (with changes in `ingestion/` directory)
- The workflow file itself is modified

## Jobs

### 1. **test** (Python 3.11 and 3.12)
- Installs dependencies from `requirements.txt`
- Runs all tests with pytest
- Generates coverage reports (XML, HTML, terminal)
- Uploads results as artifacts
- Uploads coverage to Codecov

**Status**: ✅ All 42+ tests must pass

### 2. **lint** (Python 3.11)
- Runs pylint for code quality analysis
- Runs flake8 for style checking
- Non-blocking (continues on error)

**Status**: ⚠️ Warnings allowed, continues pipeline

### 3. **build-docker** (Ubuntu latest)
- Builds Docker image for the ingestion service
- Uses GitHub Actions cache for efficiency
- Doesn't push to registry (test build only)

**Status**: ✅ Docker image must build successfully

### 4. **test-local** (Python 3.11)
- Depends on: `test` job
- Tests local archive ingestion
- Creates temporary directories and files
- Verifies deduplication and event publishing

**Status**: ✅ Must pass to confirm local functionality

### 5. **code-quality** (Python 3.11)
- Depends on: `test` job
- Runs bandit for security analysis
- Verifies all imports are resolvable
- Non-blocking (continues on error)

**Status**: ⚠️ Security warnings reported but doesn't block

### 6. **summary** (Aggregation)
- Depends on: all other jobs
- Runs regardless of other job status
- Summarizes overall CI status
- Fails pipeline if critical jobs failed

## Artifacts

The workflow generates and stores:

### Test Results
- `test-results-3.11.xml` - JUnit format test results (Python 3.11)
- `test-results-3.12.xml` - JUnit format test results (Python 3.12)

### Coverage Reports
- `coverage-report-3.11/` - HTML coverage report (Python 3.11)
- `coverage-report-3.12/` - HTML coverage report (Python 3.12)

## Coverage

Coverage is automatically uploaded to Codecov (if configured). The workflow tracks:
- Line coverage
- Branch coverage
- Function coverage

## Python Version Matrix

Tests run against:
- Python 3.11 (minimum supported version)
- Python 3.12 (latest stable version)

This ensures compatibility across versions.

## Success Criteria

The workflow is successful when:
1. ✅ All tests pass on both Python versions
2. ✅ Docker image builds successfully
3. ✅ Local ingestion test passes
4. ✅ Code imports all resolve

The following are non-blocking but reported:
- 🟡 Lint warnings
- 🟡 Code quality issues
- 🟡 Security warnings

## Failure Scenarios

The workflow will fail if:
- ❌ Any test fails
- ❌ Docker build fails
- ❌ Local ingestion test fails
- ❌ Critical code issues found

## Viewing Results

### In GitHub UI
1. Go to "Actions" tab in the repository
2. Click on "Ingestion Service CI"
3. Click the specific workflow run
4. View detailed logs and artifacts

### Download Artifacts
1. Click on the workflow run
2. Scroll to "Artifacts" section
3. Download test results and coverage reports

### View Coverage
1. Download the coverage report artifact
2. Extract and open `index.html` in a browser
3. View detailed coverage statistics

## Local Development

To run the same tests locally:

```bash
cd ingestion

# Install dependencies
pip install -r requirements.txt pytest pytest-cov

# Run tests (same as CI)
pytest tests/ -v --tb=short

# Generate coverage (same as CI)
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html
```

## Troubleshooting

### Tests fail in CI but pass locally
- Check Python version: `python --version`
- Ensure all dependencies installed: `pip install -r requirements.txt`
- Check for platform differences (Windows vs. Linux)

### Coverage drops after changes
- New code needs test coverage
- Check coverage report: `coverage-report-*/index.html`
- See which files need more tests

### Docker build fails
- Check `ingestion/Dockerfile` for syntax errors
- Verify all dependencies in `requirements.txt`
- Check file paths in COPY commands

### Import errors in CI
- Verify imports work locally: `python -c "from app.config import ..."`
- Check for missing `__init__.py` files
- Ensure all modules are properly structured

## Maintenance

### Adding new tests
1. Add test file to `ingestion/tests/`
2. Name it `test_*.py`
3. Run locally: `pytest tests/ -v`
4. Push and CI will run automatically

### Updating dependencies
1. Update `ingestion/requirements.txt`
2. CI will automatically install updated versions
3. Check for compatibility issues in CI logs

### Changing Python versions
1. Edit the `matrix` section in the `test` job
2. Add/remove version numbers
3. CI will run tests against all listed versions

## Performance

Typical workflow runtime:
- **test job**: ~2-3 minutes (per Python version)
- **lint job**: ~30 seconds
- **build-docker job**: ~1-2 minutes
- **test-local job**: ~30 seconds
- **code-quality job**: ~1 minute
- **Total**: ~8-10 minutes

## Security

The workflow:
- ✅ Never stores secrets in artifacts
- ✅ Runs in isolated GitHub-hosted runners
- ✅ Uses official actions only
- ✅ Performs security scanning (bandit)
- ✅ No external network calls in sensitive areas

## Future Enhancements

Potential additions:
- [ ] Performance benchmarks
- [ ] Memory profiling
- [ ] Integration test with real RabbitMQ
- [ ] SonarQube integration
- [ ] Artifact upload to releases
- [ ] Automated package publishing
