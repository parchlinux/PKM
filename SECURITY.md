# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

This application runs privileged operations via `pkexec` and `pacman`.
If you discover a security vulnerability, please do NOT file a public issue.

Send details to the maintainers at **security@parchlinux.com**.

We will acknowledge receipt within 48 hours and provide a timeline
for a fix. Please do not disclose the issue publicly until we've
had a chance to address it.

## Scope

The following areas are in scope for security reports:

- Privilege escalation via the `pkexec` terminal dialog
- Injection of malicious package names
- Unauthorized kernel install/remove operations
- Information disclosure (e.g., reading system files without auth)
