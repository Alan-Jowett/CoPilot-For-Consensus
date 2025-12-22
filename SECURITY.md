<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability in this project, please report it by:

1. **Opening a GitHub Security Advisory** in the repository
2. **Emailing the maintainers** (see [GOVERNANCE.md](./GOVERNANCE.md) for contact information)

Please do **not** report security vulnerabilities through public GitHub issues.

---

## Supply Chain Security

### GitHub Actions Pinning

To mitigate supply-chain risks, all GitHub Actions in this repository are pinned to specific commit SHAs rather than mutable tags.

**Policy:**
- All third-party GitHub Actions must reference a commit SHA (e.g., `actions/checkout@8e8c483db84b4bee98b60c0593521ed34d9990e8`)
- A comment with the version tag is included for readability (e.g., `# v6`)
- Actions are periodically reviewed and updated to newer versions when security patches or important features are released

**Current Pinned Actions:**

| Action | Version | Commit SHA |
|--------|---------|------------|
| `actions/checkout` | v6 | `8e8c483db84b4bee98b60c0593521ed34d9990e8` |
| `actions/github-script` | v8 | `ed597411d8f924073f98dfc5c65a23a2325f34cd` |
| `actions/setup-python` | v6 | `83679a892e2d95755f2dac6acb0bfd1e9ac5d548` |
| `actions/upload-artifact` | v6 | `b7c566a772e6b6bfb58ed0dc250532a479d7789f` |
| `coverallsapp/github-action` | v2 | `5cbfd81b66ca5d10c19b062c04de0199c215fb6e` |
| `docker/build-push-action` | v6 | `263435318d21b8e681c14492fe198d362a7d2c83` |
| `docker/setup-buildx-action` | v3 | `e468171a9de216ec08956ac3ada2f0791b6bd435` |
| `dorny/paths-filter` | v3 | `de90cc6fb38fc0963ad72b210f1f284cd68cea36` |
| `dorny/test-reporter` | v2 | `43cde22af577b469ce7aabe9acddd813dcd380bb` |

**For Contributors:**

When adding new GitHub Actions to workflows:

1. Find the commit SHA for the desired version:
   ```bash
   git ls-remote https://github.com/<owner>/<repo>.git refs/tags/<version>
   ```

2. Use the SHA in the workflow with a version comment:
   ```yaml
   - uses: owner/action@<commit-sha> # <version>
   ```

3. Verify the SHA matches the official release on GitHub

---

## Dependency Management

- Python dependencies are managed via `requirements.txt` files
- Dependabot is configured to monitor and propose updates for dependencies
- Security vulnerabilities in dependencies are addressed promptly

---

## Code Security

- All code changes go through pull request reviews
- Automated security scans (bandit) run on Python code in CI
- No secrets or credentials should ever be committed to the repository
- Use environment variables or secure secret management for sensitive data

---

## Authentication Security

### First User Auto-Promotion

**Risk:** The authentication system includes a feature that can auto-promote the first user to admin when no admins exist. If enabled in production, an attacker could authenticate first and gain admin privileges.

**Mitigation (Default):** Auto-promotion is **disabled by default** via `AUTH_FIRST_USER_AUTO_PROMOTION_ENABLED=false`.

**Production Recommendations:**
- Keep auto-promotion disabled (default setting)
- Use bootstrap tokens to assign the initial admin role
- Only enable auto-promotion in completely isolated development/testing environments
- Monitor all admin role assignments through audit logs

**See also:** [documents/AUTH_IMPLEMENTATION_SUMMARY.md](./documents/AUTH_IMPLEMENTATION_SUMMARY.md#security-considerations) for detailed security considerations.

---

## License Headers

All source files must include the appropriate license header:

```python
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors
```

This is enforced by automated checks in CI.

---

For more information about contributing securely, see [CONTRIBUTING.md](./CONTRIBUTING.md).
