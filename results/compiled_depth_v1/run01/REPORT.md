# CD-01 Results

Local exact-numerical ideal gate-link evidence only.

Quantum depths reserve both conditional correction slots. All states return home.

| Graph | Method | Quantum depth (qubit) | Quantum depth (core) | Instrument depth (qubit) | CX |
|---|---|---:|---:|---:|---:|
| line3 | endpoint | 32 | 37 | 44 | 21 |
| line3 | rendezvous | 26 | 31 | 38 | 21 |
| line3 | sabre_swap | 13-19 | 13-19 | 13-19 | 19 |
| line5 | endpoint | 64 | 73 | 88 | 41 |
| line5 | rendezvous | 42 | 49 | 60 | 41 |
| line5 | sabre_swap | 19-25 | 19-25 | 19-25 | 31 |
| square2 | endpoint | 32 | 37 | 44 | 21 |
| square2 | rendezvous | 26 | 31 | 38 | 21 |
| square2 | sabre_swap | 13-19 | 13-19 | 13-19 | 19 |

## Interpretation

Same-task differences are conditional on graph, compilation and resource model. All negative results, ties and four SABRE seeds are retained. Seed ranges are compiler sensitivity, not confidence intervals or optimality proofs.

Bell resources use counted deterministic H+CX surrogates. They are not a model of Barrett-Kok photons, detector success, heralding, retry, optical latency, classical packet delivery or QEC. Their network costs are unknown. Classical measurement dependencies are enforced, but no feedback duration is assigned. Instrument layers give resets and measurements one abstract layer, not calibrated duration.

This experiment is one restored remote CNOT, not GHZ/QFT/CDKM/QV application execution, and does not test adaptive queue-aware rendezvous. Two data slots/core and one comm qubit/core are this study's fixed resources, not the native follow-up memory configuration.

Permissible paper wording: We compiled ideal deterministic gate-link implementations of a restored remote CNOT on the specified small graphs, including explicit Bell-resource preparation, BSM, conditional corrections, storage SWAPs and state return. We report basis-gate and primitive-instrument dependency depths under declared concurrency rules and a separately identified nearest-neighbour SABRE SWAP control. These results do not establish photonic-network, QEC, hardware or full-application depth reduction.

All 18 compiled circuits passed reference-entangled Choi and work-qubit cleanup checks; maximum elementwise Choi residual 2.81513e-16.

Independent mathematical checks: exhaustive four-outcome single-hop Kraus completeness; full physical-unitary comparison for line3 SABRE controls in tests; missing-correction and missing-return mutation tests. No independent external reviewer has approved promotion.

See protocol_snapshot.md, pre_run.json, receipt.json, resource_ledger.csv, per-circuit QASM/channel/schedule JSON and aggregate.json for reproducible evidence.
