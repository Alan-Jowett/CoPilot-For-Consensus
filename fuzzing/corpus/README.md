<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Fuzzing Corpus

This directory contains seed inputs for fuzzing tests. These files help guide the fuzzer toward interesting code paths and edge cases.

## Directory Structure

```
corpus/
├── adversarial_text/   # Adversarial text inputs for semantic search
│   ├── prompt_injection.txt
│   ├── sql_injection.txt
│   ├── xss_injection.txt
│   ├── command_injection.txt
│   ├── unicode_homograph.txt
│   ├── zero_width.txt
│   ├── rtl_override.txt
│   ├── null_byte.txt
│   ├── path_traversal.txt
│   └── very_long.txt
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

## Adversarial Text Corpus

Test cases for semantic search API fuzzing:

- **prompt_injection.txt**: Prompt injection attempt for LLM-based systems
- **sql_injection.txt**: SQL injection attempt (`' OR '1'='1`)
- **xss_injection.txt**: Cross-site scripting attempt (`<script>alert('XSS')</script>`)
- **command_injection.txt**: Command injection attempt (`; rm -rf /`)
- **unicode_homograph.txt**: Unicode homograph attack (visually similar characters)
- **zero_width.txt**: Zero-width character exploitation
- **rtl_override.txt**: Right-to-left override character attack
- **null_byte.txt**: Embedded null byte
- **path_traversal.txt**: Path traversal attempt (`../../../etc/passwd`)
- **very_long.txt**: Very long input for DoS testing (1000+ characters)

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
- Injection attacks (SQL, XSS, command, prompt)
- Unicode edge cases and attacks
- DoS-inducing inputs

**DO NOT** use these patterns in production code or treat them as safe inputs.
