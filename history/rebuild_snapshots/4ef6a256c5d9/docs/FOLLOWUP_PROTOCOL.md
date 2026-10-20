# EXP-NATIVE-APP-01: native mesh and application follow-up

This is a separately registered follow-up, not a replacement or favorable rerun of
accepted batch_v2. Its simulation source and results will be frozen separately.

## Native mesh

Implement actual SeQUeNCe single-atom Memory/Photon/QuantumChannel/Detector/BSM and
two-round Barrett-Kok generation over nearest-neighbor links. Use native
TeleportProtocol payload measurements and bit corrections, native density-matrix
state tracking and actual CNOT/SWAP circuits. Existing FIFO resources schedule
finite communication/data slots, link BSM and gates. Classical generation control
uses dedicated native fixed-delay sidebands because upstream BK emission negotiation
assumes that channel timing model; payload feedforward/acknowledgment uses contended
wired/radio service. This is not the same profile or rate model as batch_v2.

Test the entire ordered CNOT channel using passive Choi diagnostic references;
preserve the joint quantum state across all hops, gate and return paths. Diagnostic
references are not counted as implemented physical hardware. Retain density matrices
and corrections; quantum amplitudes never occur in transmitted classical messages.
Coherence during native optical generation is not microscopically modeled; explicit
local dephasing applies to stored payloads and successfully heralded pairs. Pair
cutoff uses first herald time. Do not call this a calibrated physical device model.

Validation cells: noiseless 2x2 and4x4 meshes, HH/minimax/queue/adaptive, free/restored
placement, opposite corners, seeds201--204. Four contemporaneous independent gates
on4x4 test resource sharing. Additional rawF0.99 and finite-T2 case, detector outage,
very short cutoff, and dropped payload-correction cases test failure/quality
boundaries. Primary correctness target: complete ideal Choi fidelity1 within1e-9,
correct final placement, single-use pairs, bounded failures and zero resource leaks.
Observed success rates remain finite-sample diagnostics, not performance superiority.

## Application timing replay

Use Qiskit-generated GHZ, QFT, CDKM ripple-carry and quantum-volume circuits,
transpiled to an explicit basis. Preserve per-qubit dependencies, real start/finish
events, gate resource use and dynamic free/restored placement across operations.
First comparisons: HH/minimax/queue/adaptive, both placement contracts, seeds201--204,
bounded circuit sizes4--8 total qubits, one fixed mapping per circuit/seed, global
deadline0.2s. Report makespan, completed/canceled operations, teleportations and EPR
cost; logical input depth is not a compiled physical depth or a routing gain.

Timing replay does not propagate a whole application quantum state. End-to-end
application fidelity is unavailable, not an average of reset gate fidelities.
Dependent operations cancel on failed predecessors. Paired comparisons use the same
circuit/QASM hash, initial mapping and deadline. Four seeds form a bounded follow-up,
not sufficient evidence for a broad superiority claim or post-hoc tuning.

## Matched controls and readiness

Add equal-total-server pooling and identical-low-raw-fidelity purification/no-
purification checks as separate controls, not retroactive causal interpretations
of batch_v2 stress cells. Preserve null/negative outcomes. Before manuscript
promotion require independent code/evidence review and regenerated figures/tables.
No hardware, thermal, area or O(logN) result is manufactured by this extension.
