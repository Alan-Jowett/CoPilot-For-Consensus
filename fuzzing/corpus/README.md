<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Fuzzing Corpus

This directory contains seed inputs for fuzzing tests. These files help guide the fuzzer toward interesting code paths and edge cases.

## Directory Structure

```
corpus/
├── filenames/          # Malicious and edge-case filenames
│   ├── path_traversal_unix.txt
│   ├── path_traversal_windows.txt
│   ├── absolute_unix.txt
│   ├── absolute_windows.txt
│   ├── valid_mbox.txt
│   ├── valid_targz.txt
│   ├── hidden_file.txt
│   ├── double_extension.txt
│   └── null_byte.txt
└── mbox/               # Mbox file samples
    ├── valid_mbox.mbox
    ├── invalid_mbox.mbox
    ├── malformed_from.mbox
    └── empty.mbox
```

## Filename Corpus

Test cases for filename sanitization:

- **path_traversal_unix.txt**: Unix path traversal attempt (`../../../etc/passwd`)
- **path_traversal_windows.txt**: Windows path traversal attempt (`..\..\..\windows\system32\config\sam`)
- **absolute_unix.txt**: Unix absolute path (`/etc/passwd`)
- **absolute_windows.txt**: Windows absolute path (`C:\Windows\System32\cmd.exe`)
- **valid_mbox.txt**: Valid mbox filename (`test.mbox`)
- **valid_targz.txt**: Valid tar.gz filename (`archive.tar.gz`)
- **hidden_file.txt**: Hidden file (`.hidden_file`)
- **double_extension.txt**: Double extension attempt (`test.mbox.exe`)
- **null_byte.txt**: Filename with embedded null byte

## Mbox Corpus

Test cases for mbox parsing:

- **valid_mbox.mbox**: Well-formed mbox with two messages
- **invalid_mbox.mbox**: Invalid mbox (plain text, no structure)
- **malformed_from.mbox**: Malformed "From " separator
- **empty.mbox**: Empty file

## Adding New Corpus Files

When adding new test cases:

1. Use descriptive filenames that indicate what they test
2. Keep files small (< 10KB) for fast fuzzing
3. Focus on edge cases and known attack patterns
4. Document the purpose of each file in this README

## Security Note

These files contain **intentionally malicious patterns** used for security testing:
- Path traversal attempts
- Null byte injections
- Malformed data structures

**DO NOT** use these patterns in production code or treat them as safe inputs.
