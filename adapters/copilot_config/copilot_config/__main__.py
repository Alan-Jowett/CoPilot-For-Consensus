# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Module entry point for running copilot_config tools."""

import sys

if __name__ == "__main__":
    # Check which subcommand to run
    if len(sys.argv) > 1 and sys.argv[1] == "check_compat":
        # Remove the subcommand from argv so argparse works correctly
        sys.argv.pop(1)
        from .check_compat import main
        main()
    else:
        print("Usage: python -m copilot_config check_compat --old <old_schema> --new <new_schema>")
        sys.exit(1)
