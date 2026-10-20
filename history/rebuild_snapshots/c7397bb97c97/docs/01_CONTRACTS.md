# Simulation and quantum contracts

Time is seconds internally. Coordinates are integer (x,y), 0 <= x,y < mesh_side. Every raw event includes run_id, seed, request_id, simulation timestamp, component, action, and resource IDs. Reported latency uses simulation time; wall time is a separate execution-cost metric.

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
- gate_process_fidelity(channel_a, channel_b, gate_error: float = 0) -> float. Independent operand Pauli channels followed by ideal CNOT and a two-qubit Pauli error with total mass gate_error uniformly distributed among fifteen nonidentity errors. This is entanglement/process fidelity relative to the ideal gate, not output-state fidelity. Include possible Pauli cancellation.
- gate_average_fidelity(...) -> float. Dimension-four average fidelity (4 F_process + 1)/5 under the stated trace-preserving model.

quantum_validation.py must provide a callable run_validation(output_dir) that writes machine-readable independent Qiskit checks of ideal teleportation, noisy teleportation channel agreement on representative states, BBPSSW accepted branch fidelity/probability, and two-qubit channel/process fidelity. Use actual circuits/density matrices, including classical corrections or explicit normalized measurement branches. No network/cloud execution.

## Network semantics

On-demand generation retries heralded Bell resource preparation. Optical success probability includes the chosen complete-attempt definition and is charged once. Two detection rounds, local reset and classical herald messages are explicit costs. No unknown payload is measured before its accepted resource exists. Detector inefficiency changes preparation success, not automatically conditional fidelity.

Local teleportation consumes one accepted Bell pair and contributes a specified Pauli channel. Local deterministic gate noise is separate from heralded success. Pair IDs are single-use. FIFO/shared-server queues and finite communication-memory capacities must affect timings. Both operands wait and age while other jobs or classical messages occupy resources.

Radio traffic shares explicit capacity and token/service costs; wired traffic shares directed links with stated link width, clock and router cycles. Classical messages contain control data and two measurement bits with headers, never unknown quantum amplitudes.

The primary reported success endpoint is a completed gate meeting its deadline and quality threshold. Rejected, timed-out and low-quality requests stay in the denominator. Physical fidelity cannot be certified from one unknown payload: channel quality here is model-derived and independently checked at primitive level.
