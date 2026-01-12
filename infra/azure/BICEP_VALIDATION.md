# Bicep Template Validation

This directory contains Azure Bicep infrastructure-as-code templates with comprehensive CI validation.

## Validation Layers

The CI pipeline validates Bicep templates through multiple layers to catch errors early:

### 1. Syntax Validation (`az bicep build`)
- **What it does**: Transpiles Bicep to ARM JSON, catching syntax errors
- **When it runs**: On every PR and push to main
- **Blocks PR**: Yes (fails if syntax is invalid)
- **Requires Azure credentials**: No

### 2. Bicep Linting (`az bicep lint`)
- **What it does**: Enforces best practices and coding standards using `bicepconfig.json`
- **Checks**: All 16 module files + main.bicep + core.bicep
- **When it runs**: On every PR and push to main
- **Blocks PR**: Yes (fails on errors, warns on issues)
- **Requires Azure credentials**: No

### 3. Parameter File Validation
- **What it does**: Validates JSON syntax for all 6 parameter files
- **When it runs**: On every PR and push to main
- **Blocks PR**: Yes (fails if JSON is malformed)
- **Requires Azure credentials**: No

### 4. ARM-TTK Best Practices
- **What it does**: Runs Azure Resource Manager Template Toolkit tests on generated ARM templates
- **When it runs**: On every PR and push to main
- **Blocks PR**: No (informational only, reports issues in logs)
- **Requires Azure credentials**: No

### 5. Azure Deployment Validation (`az deployment group validate`)
- **What it does**: Validates template against Azure API without deploying
- **When it runs**: Only when Azure OIDC credentials are configured
- **Blocks PR**: Yes (if credentials are available)
- **Requires Azure credentials**: Yes

### 6. What-If Analysis (`az deployment group what-if`)
- **What it does**: Shows what resources would be created/modified/deleted
- **When it runs**: Only when Azure OIDC credentials are configured
- **Blocks PR**: No (informational only, helps reviewers understand impact)
- **Requires Azure credentials**: Yes

## Bicep Linter Configuration

The `bicepconfig.json` file configures the Bicep linter with the following rules:

**Critical (Error Level)**:
- `secure-parameter-default`: Prevent default values for secure parameters
- `protect-commandtoexecute-secrets`: Prevent secrets in command execution
- `outputs-should-not-contain-secrets`: Prevent secrets in outputs

**Best Practices (Warning Level)**:
- `no-unused-params`: Detect unused parameters
- `no-unused-vars`: Detect unused variables
- `prefer-interpolation`: Prefer string interpolation over concat()
- `simplify-interpolation`: Simplify unnecessary string interpolation
- And more...

## Running Validation Locally

### Prerequisites
```bash
# Install Azure CLI (includes Bicep)
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Or on macOS
brew install azure-cli

# Verify installation
az --version
bicep --version
```

### Run Syntax Check
```bash
cd infra/azure

# Check main templates
az bicep build --file main.bicep
az bicep build --file core.bicep

# Check all modules
for module in modules/*.bicep; do
  echo "Building $module..."
  az bicep build --file "$module"
done
```

### Run Linter
```bash
cd infra/azure

# Lint main templates (uses bicepconfig.json automatically)
az bicep lint --file main.bicep
az bicep lint --file core.bicep

# Lint all modules
for module in modules/*.bicep; do
  echo "Linting $module..."
  az bicep lint --file "$module"
done
```

### Validate Parameters
```bash
cd infra/azure

# Validate all parameter files
for param_file in parameters*.json; do
  echo "Validating $param_file..."
  python3 -m json.tool "$param_file" > /dev/null && echo "✓ Valid" || echo "✗ Invalid"
done
```

### Run ARM-TTK (Optional)
```bash
# Clone ARM-TTK
git clone https://github.com/Azure/arm-ttk.git /tmp/arm-ttk

# Build ARM template
cd infra/azure
az bicep build --file main.bicep --outfile /tmp/main.json

# Run ARM-TTK (requires PowerShell)
pwsh -Command "
  Import-Module /tmp/arm-ttk/arm-ttk/arm-ttk.psd1
  Test-AzTemplate -TemplatePath /tmp/main.json
"
```

### Run Azure Validation (Requires Credentials)
```bash
cd infra/azure

# Validate against Azure (requires login and resource group)
az login
az deployment group validate \
  --resource-group <your-rg> \
  --template-file core.bicep \
  --parameters parameters.core.dev.json

# Run what-if analysis
az deployment group what-if \
  --resource-group <your-rg> \
  --template-file core.bicep \
  --parameters parameters.core.dev.json
```

## CI Workflow

The validation workflow (`.github/workflows/bicep-validate.yml`) runs automatically on:
- Pull requests that modify `infra/azure/**`
- Pushes to `main` branch that modify `infra/azure/**`
- Manual workflow dispatch

### Job Dependency Graph
```
bicep-lint (always runs)
├── arm-ttk-validation (runs after lint)
└── validate-template (runs after lint, only if Azure credentials available)
    └── what-if analysis

comment-results (always runs on PR, waits for all jobs)
```

## Fail-Fast Philosophy

The validation is designed to fail fast:
1. **Syntax errors** are caught by `bicep build` (0-10 seconds)
2. **Linting issues** are caught by `bicep lint` (10-30 seconds)
3. **Parameter issues** are caught by JSON validation (1-5 seconds)
4. **ARM best practices** are reported by ARM-TTK (non-blocking)
5. **Azure validation** only runs if needed (requires credentials, takes 60+ seconds)

This approach ensures developers get fast feedback without waiting for full Azure deployment.

## Troubleshooting

### Linting Warnings
If you see warnings from the Bicep linter:
- Review the warning message and fix if appropriate
- Check `bicepconfig.json` if you need to adjust rule levels
- Warnings don't block PR merge, but should be addressed

### ARM-TTK Issues
ARM-TTK tests are informational only:
- Review the test results in the CI logs
- Some tests may not apply to your use case
- Tests can be skipped in the workflow using `-Skip` parameter

### Azure Validation Fails
If Azure validation fails but syntax is valid:
- Check if resources referenced in template exist (e.g., Key Vault, resource groups)
- Verify parameter values are appropriate for your environment
- Ensure OIDC credentials have correct permissions

## Best Practices

1. **Always run local validation** before pushing changes
2. **Fix all linting errors** (warnings can be addressed separately)
3. **Keep bicepconfig.json strict** to maintain code quality
4. **Use parameter files** for environment-specific values
5. **Review what-if output** before deploying to production
6. **Document complex templates** with comments and metadata

## References

- [Bicep Documentation](https://learn.microsoft.com/azure/azure-resource-manager/bicep/)
- [Bicep Linter Rules](https://learn.microsoft.com/azure/azure-resource-manager/bicep/linter)
- [ARM-TTK](https://github.com/Azure/arm-ttk)
- [Azure Deployment Validation](https://learn.microsoft.com/azure/azure-resource-manager/templates/template-tutorial-use-template-reference?tabs=CLI)
