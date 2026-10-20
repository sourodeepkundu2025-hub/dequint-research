# Simulation and quantum contracts

Time is seconds internally and native event ticks are picoseconds. Coordinates are integer (x,y), 0 <= x,y < mesh_side. Raw events include run_id, seed, request_id, time_s and action; resource/node IDs appear on their relevant component events. The action identifies the component category, not a separate mandatory component field. This records the actual retained batch_v2 schema rather than promising absent fields. Reported latency uses simulation time; wall time is a separate execution-cost metric.

## Quantum module ownership and API

Agent-owned files: src/dequint/quantum.py, src/dequint/quantum_validation.py, tests/test_quantum.py. Other files belong to the integrating agent.

Pauli channels are numpy arrays of four probabilities in I,X,Y,Z order. They describe conditional noise on an accepted state, never probability of resource availability. Bell-diagonal probabilities use the Bell basis induced by those Pauli errors on Phi+.

- identity_channel() -> ndarray[4].
- werner_channel(fidelity: float) -> ndarray[4]. Phi+ weight F, other weights (1-F)/3.
- compose_pauli(first, second) -> ndarray[4]. Phase-ignored Pauli convolution.
- dephasing_channel(duration_s: float, t2_s: float) -> ndarray[4]. Coherence exp(-duration/T2); t2 can be infinity; reject negative time or nonpositive t2.
- age_channel(channel, duration_s, t2_s) -> ndarray[4]. Apply local memory dephasing. Aging both Bell endpoints for t seconds uses total duration 2t.
- pauli_depolarizing(error_probability: float) -> ndarray[4]. Identity 1-e, each nonidentity e/3. Input is a Pauli error probability, not average gate infidelity.
- bbpssw(fidelity_a: float, fidelity_b: float | None = None) -> (conditional_fidelity, acceptance_probability). Explicit ideal-operation Werner-input assumption, no hidden retry.
- gate_process_fidelity(channel_a, channel_b, gate_error: float = 0, *, post_a=None, post_b=None) -> float. Independent operand Pauli channels followed by ideal CNOT and a two-qubit Pauli error with total mass gate_error uniformly distributed among fifteen nonidentity errors, then independent optional post channels. Pre-gate errors remain correlated after CNOT. This is entanglement/process fidelity relative to the ideal gate, not output-state fidelity. Include possible Pauli cancellation.
- gate_average_fidelity(...) -> float. Dimension-four average fidelity (4 F_process + 1)/5 under the stated trace-preserving model.

quantum_validation.py must provide a callable run_validation(output_dir) that writes machine-readable independent Qiskit checks of ideal teleportation, noisy teleportation channel agreement on representative states, BBPSSW accepted branch fidelity/probability, and two-qubit channel/process fidelity. Use actual circuits/density matrices, including classical corrections or explicit normalized measurement branches. No network/cloud execution.

## Network semantics

On-demand generation retries heralded Bell resource preparation. Optical success probability includes the chosen complete-attempt definition and is charged once. Two detection rounds, local reset and classical herald messages are explicit costs. No unknown payload is measured before its accepted resource exists. Detector inefficiency changes preparation success, not automatically conditional fidelity.

Local teleportation consumes one accepted Bell pair and contributes a specified Pauli channel. Local deterministic gate noise is separate from heralded success. Pair IDs are single-use. FIFO/shared-server queues and finite communication-memory capacities must affect timings. Both operands wait and age while other jobs or classical messages occupy resources.

Radio traffic shares explicit capacity and token/service costs; wired traffic shares directed links with stated link width, clock and router cycles. Classical messages contain control data and two measurement bits with headers, never unknown quantum amplitudes.

The primary reported success endpoint is a completed gate meeting its deadline and quality threshold. Rejected, timed-out and low-quality requests stay in the denominator. Physical fidelity cannot be certified from one unknown payload: channel quality here is model-derived and independently checked at primitive level.

## Native mesh and application follow-up

run_native_mesh() uses actual native photons/detectors, BK generation and
TeleportProtocol measurements/corrections. It retains diagnostic Choi references
across the complete routed CNOT/return process. Finite data slots and native
three-CNOT storage SWAPs are charged, including failed partial operations. Payload
Bell measurements, storage SWAPs and useful gates share each core's gate resource.
BK optical control uses dedicated native fixed-delay sidebands; payload correction
and ACK use contended FIFO/radio. Native reservation-stack execution, microscopic
in-generation dephasing, purification and pooled generation are not claimed for
this backend. Its native send_qubit counter includes null-encoded BK photon objects.

ApplicationReplay uses the unchanged abstract Network execution path for CNOT task
timing. It preserves Qiskit DAG dependencies and dynamic logical-qubit locations,
including predecessor failure cancellation. Single-qubit operations share core
gate capacity. It does not propagate an application quantum state, so end-to-end
application fidelity and compiled physical circuit depth must remain null. Source
and unplaced basis depth are separately named logical circuit properties.

## Additive Quantum-Overlay and Reviewer-Closure Evidence

The quantum-shortcut probe uses a mesh union undirected binary shift-and-append
edges; only square power-of-two side lengths are implemented. Its constructive
logarithmic graph-hop bound is separate from expected latency. The probe has
matched global active generation and finite active ports, but unequal installed
links/cabling, abstract optics, analytic Pauli quality and an uncontended direct
classical sideband. Do not substitute native-mesh backend semantics into it.

The compiled-depth supplement is a separate deterministic gate-link experiment:
same arbitrary-input restored CNOT, explicit dynamic teleportation construction,
fixed u,cx basis and physical graph, with independently checked Choi/cleanup.
Quantum-gate layers, primitive-instrument layers and qubit/core serialization
are separately named. Optical retries/loss and classical durations are absent,
not measured zero. SABRE controls on the same gate-link graph outperform both
teleportation skeletons; preserve this adverse result. ApplicationReplay's
physical-depth/null contract is unchanged by this separate small experiment.

The transport supplement runs the unchanged Network model with a predeclared
factorial profile. All offered terminal outcomes remain in denominators; paired
latency deltas use the common-completion intersection. Trace actions support
overlapping observations, not a nine-disjoint-stage timing partition or a causal
fault tree. The final recorded job reason is not necessarily the first cause.
