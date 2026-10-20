# Security and Responsible Reporting

This is offline research software, not a hardened multi-tenant service. No cloud
credentials or hardware access are required for the documented experiments.
Treat downloaded notebooks, circuits and data as untrusted input.

## Reporting

For a credential exposure or vulnerability, use GitHub's private vulnerability
reporting option if enabled. Otherwise contact the maintainer through the GitHub
profile and share only a non-sensitive summary until a private channel is agreed.
Do not post a token, private key, exploit payload containing secrets or confidential
research documents in a public issue.

## Supported Scope

Only the current repository version is maintained. Historical prototypes and
checkpoint snapshots are retained for inspection, not supported deployments.
Experiments can be CPU/memory intensive; run in an isolated environment with
bounded parameters. Dependencies have their own security and license policies.

Do not execute historical/private document builders on untrusted TeX/ZIP inputs.
No runner should require disabling verification, sharing passwords or embedding
an authentication token in a command, URL, result file or issue.
