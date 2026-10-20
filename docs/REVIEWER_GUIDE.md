# Guide for Editors, Reviewers and Replicators

This repository accompanies DEQUINT research on decentralised quantum
interconnects. Its purpose is inspection and reproduction, not a claim of
editorial acceptance, hardware readiness or universal superiority.

## Suggested Reading Order

1. [README](../README.md): scope, experiment map and main limitations.
2. [Architecture](ARCHITECTURE.md): backend distinctions and source ownership.
3. [Results](RESULTS.md): accepted/quarantined records and quantitative index.
4. [Getting Started](GETTING_STARTED.md): install, verify, test and fresh reruns.
5. [Scientific contracts](01_CONTRACTS.md): units, common task and fidelity semantics.
6. [Claim map](CLAIM_IMPLEMENTATION_MAP.md): implemented versus unvalidated claims.

## Evidence Navigation

| Review question | Code | Evidence |
| --- | --- | --- |
| Preparation retries and memory aging | `network.py`, `quantum.py` | `batch_v2`, event traces and request rows |
| Native swapping/teleportation and fidelity | `native_reference.py`, `native_mesh.py` | `native_reference`, native records in `followup_v1` |
| Common ordered-CNOT task and restored outputs | `network.py`, `native_mesh.py`, `compiled_depth.py` | Protocols and saved Choi channels |
| Finite queues, BSM/gate resources and radio contention | `kernel.py`, `transport.py`, `network.py` | `review_supplement_v1` raw event/audit files |
| Quantum-hop scaling and installation costs | `shortcut_probe.py` | `shortcut_v1/topology_census.csv` and edge-level records |
| Matched compiled controls | `compiled_depth.py` | `compiled_depth_v1/run01` QASM, schedules and channel matrices |
| Pipeline-to-result provenance | Experiment runners and verifier | Final lineage ledger, original/public provenance and public hashes |

All code paths above are relative to `src/dequint/` unless otherwise specified.

## Important Qualifications

- A low preparation-success probability can coexist with high accepted-state
  fidelity. Both must be reported, with retry and failure costs retained.
- Modeled quality or a pair identifier is not an in-service physical
  entanglement-verification measurement on an unknown payload.
- Overlapping event/wait counters are not disjoint timing stages or a causal
  failure tree. Conditional latency has a declared completion subset.
- A quantum overlay changes the quantum-link graph. A classical radio shortcut
  alone cannot establish logarithmic EPR hop scaling for a mesh.
- Source checkpoints and old XML receipts are historical evidence. A fresh clone
  must execute its own current checks before claiming a replication.
- The repository retains adverse findings. Please do not infer that purification,
  radio, rendezvous or a quality term always improves the same metric.

## What Is Not Public Here

The manuscript and confidential point-by-point reviewer correspondence remain in
the private author submission package. Patent/IDF/TRL documents, source archives,
third-party full-text papers, Wiley templates/fonts and unrelated projects are
not part of this repository. No private reviewer identity or editorial email is
required to reproduce the scientific implementation.

Questions about a result should identify the commit, backend/profile, run ID,
placement, offered denominator and exact metric. The issue templates request
these fields to make numerical questions actionable.
