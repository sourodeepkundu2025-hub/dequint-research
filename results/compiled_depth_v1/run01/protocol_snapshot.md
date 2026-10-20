# Compiled Depth Protocol CD-01 (predeclared)

## Question and Scope

Does endpoint delivery or midpoint rendezvous change the compiled gate depth
of the SAME ideal remote CNOT, including both operands returned to their home
data slots? No latency, hop count, or elapsed time is converted to circuit depth.
This is a bounded synthetic gate-connected experiment, NOT photonic-network,
fault-tolerant, QEC, application-replay, or hardware depth evidence.

Only `src/dequint/compiled_depth.py`, `tests/test_compiled_depth.py`,
`tools/run_compiled_depth.py`, this protocol, and `results/compiled_depth_v1/**`
may be written. Existing modules, accepted results, and manuscripts are read-only.
No installs, cloud jobs, credential access, or Git commits are required.

## Frozen Design Before Execution

- Three core graphs: line of 3 cores (distance 2), square 2x2 (opposite corners,
  distance 2), and line of 5 cores (distance 4). Node order, XY routes and midpoint
  tie breaks are deterministic, not chosen after observing depth.
- Every core has two data slots and one communication qubit. Local connectivity
  is a bidirectional clique; adjacent cores connect ONLY their communication
  qubits. Both policies and the SWAP control get exactly the same physical graph.
  These cross-core CX edges are a deterministic Bell-generation SURROGATE, not
  an assertion that an optical link implements a deterministic physical CX.
- Logical control starts at core 0 data slot 0; target starts at the last core
  data slot 0. All other qubits start in zero. The channel is a CNOT on arbitrary
  two-qubit input, including reference entanglement, with outputs at those same
  physical slots. All non-output work qubits must end in zero.
- Endpoint delivery moves the control to the target core. Rendezvous moves both
  operands to the XY path midpoint. The useful CNOT is executed locally. Reverse
  paths restore both operands; no free final placement or uncounted state return.
- Each adjacent teleport hop explicitly resets vacant communication/destination
  slots, prepares H+CX Bell resource, applies CX+H Bell measurement, measures two
  bits, applies conditional X then Z to receiver communication qubit, transfers
  into destination storage using a three-CX SWAP, and resets vacated qubits.
  Distinct classical bits per hop are retained in exported dynamic circuits.
- Communication is serialized when physical communication qubits are shared.
  Independent gates may overlap on disjoint qubits. No global hop barriers or
  artificial endpoint serialization. Per-operand paths are causally ordered;
  correction and transfer precede reuse. A second resource schedule allows only
  one primitive operation per core, reflecting the native mesh gate constraint.
- Qiskit 2.2.3 basis `u,cx`, identity physical placement, optimization level 0,
  routing method `none` for already placed teleportation circuits. All nested
  control-flow gates must obey the declared physical graph. Count both CX
  orientations as legal; no calibrated direction or pulse durations are assumed.
- A separate physical nearest-neighbour SABRE control routes the same logical
  CNOT on the same graph, identity initial placement, optimization level 0,
  seeds 201,202,203,204. Preserve routing SWAPs, then append their reverse sequence
  to restore the complete placement. Decompose all SWAPs into the same `u,cx`
  basis with no further routing or cancellation. This is not teleportation.
  Four seeds describe compiler variation, not a population confidence interval.
  The constructed teleportation policies are deterministic and run once/case.

## Endpoints and Acceptance

Report counts of basis gates recursively through `if_else`, measurements,
resets, qubits, used qubits, classical bits, Bell resources, BSMs, correction
bits, storage CXs, routing SWAPs and state-return overhead. Conditional X/Z
gates count as reserved upper-envelope gates (both correction slots), NOT an
average executed count. Bell H+CX gates are included, not free preshared EPRs.

Do NOT use `QuantumCircuit.depth()` on dynamic control flow as evidence.
Publish a transparent dependency scheduler with:

1. Quantum-gate layers: `u,cx` weight one; measure/reset weight zero, while still
   preserving their wire/classical dependencies. Conditional corrections depend
   on measurement bits. This is an ideal zero-duration nonunitary boundary.
2. Primitive-instrument layers: gates, measures and resets each weight one;
   classical dependencies still enforced, classical propagation weight zero.
3. Both metrics under disjoint-qubit and one-operation-per-core concurrency.
4. CX-only dependency layers as a secondary diagnostic, not time or QEC depth.

All conditional branches in this experiment contain one positive correction;
the worst-case correction reservation is feasible, but is not hardware timing.
No feedback round trip, ACK, packet contention, reset duration, detector,
photon loss, probabilistic heralding/retry, purification, decoherence, or code
cycle is compressed into these layer counts. Optical resource costs remain
unknown, not zero. Conditional dependencies are counted but transport duration
is not. Correction count is an upper envelope, not an unconditional unitary.

Check the compiled circuits, not just a high-level routing formula. Exact
numerical ideal-corner checks use the two-input Choi state (two references),
projective measurement branches, explicit conditional corrections and reset.
A small active-wire density-matrix interpreter discards known-zero spectators
and merges branches only after classical bits have no future uses. This is
deterministic density-matrix channel evaluation, not finite-shot sampling.
Report numerical residual, trace, fidelity, maximum active width, branch count,
and work-qubit zero-state error. Require max Choi error and trace/cleanup error
below 1e-9 for EVERY compiled circuit. Include mutation tests removing a
correction or state return to prove the checker rejects incorrect channels.
An independent exhaustive four-outcome single-hop check is also required.

Bounds: 6 teleportation circuits plus 12 SABRE circuits, <=15 physical qubits
(plus two mathematical reference qubits), four compiler seeds; no search for
favourable layouts, no application-wide or noisy simulation. Save all outcomes,
including ties, regressions and failures. Stop on failed equivalence/connectivity.
Focused tests may use additional small fixtures, not broaden the experiment.

## Provenance and Delivery

The runner must save protocol/code/source hashes and runtime/package versions
BEFORE compiling the first case, UTC start/end, per-case wall time, seed,
layout, graph, raw QASM 3 circuits, dependency schedules, resource ledger,
channel checks, all seed results, aggregate ranges and a claim-boundary report.
Refuse a nonempty run output; permit a fresh named subdirectory under the owned
result root. Rehash source inputs after the run and report drift rather than
silently certifying stale provenance. Tests use `-B` and no pytest cache outside
the owned results tree. No promotion or manuscript editing is part of this run.

Relevant read-only sources: `application_replay.py` explicitly excludes physical
routing depth; `native_mesh.py` implements Bell measurement, correction, storage
SWAP and restored placement; `followup.py` declares application configurations
GHZ-6, QFT-6, CDKM-2, QV-4 on a 4x4 mesh. This small same-CNOT experiment is NOT
a compiled replay of those applications or the queue-aware adaptive selector.

Official references inspected for semantics:
- https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.2/transpiler
- https://quantum.cloud.ibm.com/docs/en/api/qiskit/quantum_info
- https://quantum.cloud.ibm.com/docs/en/guides/represent-quantum-computers
- https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.1/qiskit.circuit.QuantumCircuit
  (control-flow depth warning; installed-version behavior is verified locally).

Paper permission: only a claim conditional on these exact ideal gate-link
graphs, basis, return contract, and concurrency assumptions, after tests pass.
No general DEQUINT depth advantage, photonic or QEC depth reduction, hardware
speedup, application-fidelity improvement, or latency-to-depth inference follows.
