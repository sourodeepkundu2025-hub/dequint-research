# Compiled Depth CD-01 Delivery

## Outcome

Actual placed Qiskit circuits, not latency/hop-derived depth. Six deterministic
dynamic teleportation skeletons and twelve SABRE SWAP controls, all on the same
declared gate-link graphs with outputs restored to their original physical data
slots. All 18 reference-entangled channel checks pass, with maximum elementwise
Choi error 2.8151321594260327e-16 and zero reported work-qubit population error.
The 18 focused tests pass. Run time was 6.73 seconds locally (not a performance
comparison). No hardware, finite-shot or paid-cloud evidence is claimed.

| Core graph | Endpoint quantum layers | Rendezvous quantum layers | SABRE quantum layers (four seeds) | Endpoint/rendezvous CX | SABRE CX |
|---|---:|---:|---:|---:|---:|
| Line 3, distance 2 | 32 | 26 | 13-19 | 21 / 21 | 19 |
| Line 5, distance 4 | 64 | 42 | 19-25 | 41 / 41 | 31 |
| Square 2x2, distance 2 | 32 | 26 | 13-19 | 21 / 21 | 19 |

These are disjoint-qubit, zero-feedback-duration, conditional-correction reserved
gate layers in basis `u,cx`, NOT physical elapsed time. Under one-operation/core,
endpoint/rendezvous depths are 37/31, 73/49, and 37/31 respectively. All six depth
metrics, including measurement/reset instrument layers and CX layers, are saved
per circuit. Instrument layers are abstract unit weights, not calibrated times.

**Adverse comparator result:** every tested physical nearest-neighbour SABRE
control is shallower AND has fewer CX gates than either teleportation skeleton.
Rendezvous improves only on this endpoint-delivery construction. No superiority
over routed unitary circuits is supported. SABRE seed ranges describe four
compiler runs, not a confidence interval, exhaustive search, or optimality proof.

## Exact Scope and Assumptions

- One remote CNOT on arbitrary two-qubit input, certified with a Choi input and
  two entangled mathematical references; no GHZ/QFT/CDKM/QV application execution.
- Two physical data slots and one communication qubit per core; local clique
  coupling and adjacent communication-qubit gate links; both CX directions legal.
- Bell H+CX preparation, two-bit BSM, conditional X/Z correction, three-CX
  communication-to-storage transfer, reset, and full outbound/return paths counted.
- The deterministic cross-core CX used for Bell preparation is a gate-link
  surrogate. It is NOT a physical model of a photonic connection or its success.
- Feedback dependencies are explicit. Optical heralding/retry, photons,
  detectors, loss, ACKs, classical transport/queue time and QEC cycles are NOT
  represented. Their physical costs remain unknown, not zero-cost evidence.
- Quantum layers exclude nonunitary duration; instrument layers count each
  measure/reset as one abstract layer. Corrections reserve the positive branch
  gates, not average executed gates. No control-flow `QuantumCircuit.depth()` is
  used for the dynamic circuits.
- Scheduling uses a fixed instruction-order ASAP construction, not an optimal
  scheduler. Shared communication qubits serialize use; the core-serialized
  schedule is an additional conservative resource model, not full native timing.
- The XY-path midpoint tie break is fixed and may differ from the existing
  lexicographic minimax meeting. Adaptive queue-aware selection is not tested.
- Mathematical cross-checks do not constitute independent external review or
  manuscript/release approval. Human scientific review is still needed.

## What the Paper May Say

"For ideal deterministic gate-link implementations of a restored remote CNOT,
the declared midpoint-rendezvous construction used fewer compiled quantum-gate
layers than endpoint delivery on the three tested small graphs, with equal
teleportation resource/gate counts. The matched physical SWAP controls were
shallower and used fewer CX gates. These are conditional circuit-skeleton results,
not photonic-network, QEC, hardware or application-level depth reductions."

Any broader sentence asserting DEQUINT physical depth advantage, quantum speedup,
network-teleportation depth, or QEC-cycle savings remains unsupported. Existing
application timing replay results remain timing evidence only.

## Files and Reproduction

Only these new source paths and this result subtree were written:
`src/dequint/compiled_depth.py`, `tests/test_compiled_depth.py`,
`tools/run_compiled_depth.py`, `docs/COMPILED_DEPTH_PROTOCOL.md`, and
`results/compiled_depth_v1/**`. Frozen modules, accepted records and manuscript
files were not edited. No Git commit was made.

Using the requested Python executable:

```powershell
$python = '<LOCAL_HOME>\AppData\Local\CodexResearch\venvs\dequint-py312\Scripts\python.exe'
& $python -B -m pytest tests/test_compiled_depth.py -p no:cacheprovider --basetemp=results/compiled_depth_v1/pytest_tmp_recheck --junitxml=results/compiled_depth_v1/tests_recheck.xml -q
& $python -B tools/run_compiled_depth.py --run-name fresh_run_name
& $python -B results/compiled_depth_v1/audit_saved_evidence.py
```

The audit targets the preserved `run01`, validates its hashes and all 108 saved
schedules against a separate dependency-graph calculation, and independently
reconstructs the CNOT Choi target from bit indices. It does not import the project
implementation. The runner refuses nonempty evidence destinations. Preserve
`run01/pre_run.json`, `protocol_snapshot.md`, `receipt.json`, `manifest.json`,
`resource_ledger.csv`, raw QASM and per-circuit channel/schedule JSON together.
