import sys
import pathlib

# Add all adapters to path
repo_root = pathlib.Path(__file__).parent
adapters_root = repo_root / "adapters"
for adapter_dir in sorted(adapters_root.glob("copilot_*")):
    sys.path.insert(0, str(adapter_dir))

# Add reporting module
reporting_root = repo_root / "reporting"
sys.path.insert(0, str(reporting_root))

# Add root
sys.path.insert(0, str(repo_root))

import pytest
sys.exit(pytest.main([
    "adapters/copilot_storage/tests/test_azure_cosmos_document_store.py",
    "parsing/tests/test_service_error_handling.py",
    "-v"
]))
