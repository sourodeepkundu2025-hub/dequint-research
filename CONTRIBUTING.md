# Contributing

## Report a Reproducibility Issue

Use the reproduction issue template. Include the commit, Python/OS/dependency
versions, command, backend/profile, seed, run ID and a minimal non-sensitive
example. Distinguish an installation failure from a numerical disagreement.
Do not attach confidential reviews, access tokens or private source archives.

## Propose a Change

1. Open an issue explaining the observable problem or hypothesis.
2. Create a focused feature branch; do not mix protocol changes with refactoring.
3. Keep current scientific contracts and backend distinctions explicit.
4. Add focused tests for behavior changes and run the existing suite.
5. Submit a pull request using the template, with commands and actual outcomes.

## Evidence Rules

- Never edit frozen raw records to make a new implementation pass an old result.
- Use a fresh output directory, protocol version and source/environment record.
- Compare matched tasks, placement, workloads and active resource budgets.
- Retain failed, unqualified and adverse cases; report the full offered denominator.
- Do not turn graph hops, circuit skeletons or simulated noise into hardware claims.
- Update the relevant protocol and result lineage when a scientific contract changes.

The public snapshot verifier intentionally reports changes to distributed files.
A development branch changing source must record a new manifest only as a new
version, not pretend the old snapshot is unchanged. Rights for proposed code must
be clear; do not import third-party implementations without their license/notice.
