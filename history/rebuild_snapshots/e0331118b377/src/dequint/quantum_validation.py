"""Exact, local-only Qiskit primitive checks, independent of scalar formulas.

No shots, provider accounts, Aer services, hardware or network execution are
used. Measurement branches are explicitly projected, normalized, corrected
and recombined. Qiskit's little-endian ordering is used throughout.
"""

from __future__ import annotations

import csv
import json
import platform
from itertools import product
from pathlib import Path

import numpy as np
import qiskit
from qiskit import QuantumCircuit, qasm3
from qiskit.quantum_info import (
    DensityMatrix, Kraus, Operator, Pauli, Statevector, SuperOp,
    average_gate_fidelity, partial_trace, process_fidelity, state_fidelity,
)

from .quantum import (
    _channel, _probability, age_channel, bbpssw, compose_pauli,
    dephasing_channel, gate_average_fidelity, gate_process_fidelity,
    identity_channel, pauli_depolarizing, werner_channel,
)


PAULIS = tuple(Operator(Pauli(label)).data for label in "IXYZ")
TOLERANCE = 1e-10


def _bell_circuit() -> QuantumCircuit:
    circuit = QuantumCircuit(2, name="Phi_plus")
    circuit.h(0)
    circuit.cx(0, 1)
    return circuit


def _bell_density(channel) -> DensityMatrix:
    probabilities = _channel(channel)
    ideal = DensityMatrix.from_instruction(_bell_circuit())
    mixed = np.zeros((4, 4), dtype=complex)
    for probability, matrix in zip(probabilities, PAULIS):
        mixed += probability * ideal.evolve(Operator(matrix), [1]).data
    return DensityMatrix(mixed)


def _branches(state: DensityMatrix, measured: list[int]):
    """Yield normalized Z-measurement branches with bits in measured-list order."""
    indices = np.arange(state.dim)
    for bits in product((0, 1), repeat=len(measured)):
        mask = np.ones(state.dim, dtype=bool)
        for qubit, bit in zip(measured, bits):
            mask &= ((indices >> qubit) & 1) == bit
        projected = state.data * np.outer(mask, mask)
        probability = float(np.trace(projected).real)
        if probability > 0:
            yield bits, probability, DensityMatrix(projected / probability)


def teleportation_density(state, channel):
    """Return Bob's density matrix and branch evidence for a noisy Bell pair.

    q0: payload, q1: Alice's Bell half, q2: Bob. Measure q0 after H and q1
    after CX; apply X^m1 then Z^m0 on q2 in every normalized branch.
    """
    payload = DensityMatrix(state)
    if payload.dim != 2 or not payload.is_valid():
        raise ValueError("payload must be a valid one-qubit state")
    combined = _bell_density(channel).tensor(payload)
    circuit = QuantumCircuit(3, name="teleport_Bell_measurement")
    circuit.cx(0, 1)
    circuit.h(0)
    measured = combined.evolve(circuit)
    output = np.zeros((2, 2), dtype=complex)
    evidence = []
    for (m0, m1), probability, branch in _branches(measured, [0, 1]):
        correction = QuantumCircuit(3)
        if m1:
            correction.x(2)
        if m0:
            correction.z(2)
        bob = partial_trace(branch.evolve(correction), [0, 1])
        output += probability * bob.data
        evidence.append({"m0": m0, "m1": m1, "probability": probability,
                         "x_correction": m1, "z_correction": m0,
                         "corrected_density": _matrix(bob.data)})
    return DensityMatrix(output), evidence


def _single_qubit_cliffords():
    """Generate the 24-element projective Clifford group from H and S."""
    h = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)
    s = np.diag([1, 1j])
    group = [np.eye(2, dtype=complex)]
    cursor = 0
    while cursor < len(group):
        for generator in (h, s):
            candidate = generator @ group[cursor]
            if not any(np.isclose(abs(np.trace(old.conj().T @ candidate)), 2,
                                  atol=1e-12, rtol=0) for old in group):
                group.append(candidate)
        cursor += 1
    if len(group) != 24:
        raise RuntimeError("single-qubit Clifford twirl must contain 24 elements")
    return group


def _isotropic_twirl(state: DensityMatrix) -> DensityMatrix:
    # q0 gets U and q1 gets U*: this preserves Phi+, unlike a generic U tensor U.
    terms = [state.evolve(Operator(np.kron(u.conj(), u))).data
             for u in _single_qubit_cliffords()]
    return DensityMatrix(np.mean(terms, axis=0))


def bbpssw_density(fidelity_a: float, fidelity_b: float | None = None):
    """Independently project the accepted bilateral-CNOT branches of two pairs."""
    a = _probability(fidelity_a, "fidelity_a")
    b = a if fidelity_b is None else _probability(fidelity_b, "fidelity_b")
    # Retain A0=q0, B0=q1; sacrifice A1=q2, B1=q3.
    combined = _bell_density(werner_channel(b)).tensor(_bell_density(werner_channel(a)))
    circuit = QuantumCircuit(4, name="BBPSSW_bilateral_CNOT")
    circuit.cx(0, 2)
    circuit.cx(1, 3)
    evolved = combined.evolve(circuit)
    accepted = np.zeros((4, 4), dtype=complex)
    acceptance = 0.0
    evidence = []
    phi_plus = Statevector.from_instruction(_bell_circuit())
    for bits, probability, branch in _branches(evolved, [2, 3]):
        keep = bits[0] == bits[1]
        reduced = partial_trace(branch, [2, 3])
        if keep:
            acceptance += probability
            accepted += probability * reduced.data
        evidence.append({"target_A": bits[0], "target_B": bits[1],
                         "accepted": keep, "probability": probability,
                         "retained_phi_plus_fidelity": float(state_fidelity(reduced, phi_plus))})
    output = DensityMatrix(accepted / acceptance)
    fidelity = float(state_fidelity(output, phi_plus))
    twirled = _isotropic_twirl(output)
    return fidelity, acceptance, output, twirled, evidence


def cnot_process_check(
    channel_a, channel_b, gate_error: float = 0, *, post_a=None, post_b=None,
):
    """Compose full Qiskit channels without using the analytical symplectic map."""
    a, b = _channel(channel_a), _channel(channel_b)
    error = _probability(gate_error, "gate_error")
    return_a = identity_channel() if post_a is None else _channel(post_a)
    return_b = identity_channel() if post_b is None else _channel(post_b)
    circuit = QuantumCircuit(2, name="ideal_CNOT")
    circuit.cx(0, 1)
    ideal = Operator(circuit)
    before, gate, after = [], [], []
    for i, j in product(range(4), repeat=2):
        matrix = np.kron(PAULIS[j], PAULIS[i])
        if a[i] * b[j] > 0:
            before.append(np.sqrt(a[i] * b[j]) * matrix)
        if return_a[i] * return_b[j] > 0:
            after.append(np.sqrt(return_a[i] * return_b[j]) * matrix)
        gate_probability = 1 - error if (i, j) == (0, 0) else error / 15
        if gate_probability > 0:
            gate.append(np.sqrt(gate_probability) * matrix)
    noisy = (SuperOp(Kraus(before)).compose(SuperOp(ideal))
             .compose(SuperOp(Kraus(gate))).compose(SuperOp(Kraus(after))))
    return {"process_fidelity": float(process_fidelity(noisy, ideal)),
            "average_fidelity": float(average_gate_fidelity(noisy, ideal)),
            "is_cptp": bool(noisy.is_cptp()),
            "factor_kraus_counts": {"input": len(before), "gate": len(gate), "return": len(after)}}


def _matrix(matrix):
    return {"real": np.asarray(matrix).real.tolist(),
            "imag": np.asarray(matrix).imag.tolist()}


def _direct_pauli_output(state, channel):
    """Matrix conjugation reference, independent of teleportation construction."""
    density = DensityMatrix(state).data
    return sum(p * matrix @ density @ matrix.conj().T
               for p, matrix in zip(_channel(channel), PAULIS))


def _evidence_circuits():
    teleport = QuantumCircuit(3, 2, name="teleportation_with_feedforward")
    teleport.h(1)
    teleport.cx(1, 2)
    teleport.cx(0, 1)
    teleport.h(0)
    teleport.measure(0, 0)
    teleport.measure(1, 1)
    with teleport.if_test((teleport.clbits[1], 1)):
        teleport.x(2)
    with teleport.if_test((teleport.clbits[0], 1)):
        teleport.z(2)
    purification = QuantumCircuit(4, 2, name="BBPSSW_accept_equal_target_bits")
    purification.h(0)
    purification.cx(0, 1)
    purification.h(2)
    purification.cx(2, 3)
    purification.cx(0, 2)
    purification.cx(1, 3)
    purification.measure(2, 0)
    purification.measure(3, 1)
    cnot = QuantumCircuit(2, name="CNOT_process_reference")
    cnot.cx(0, 1)
    return {"teleportation": teleport, "bbpssw": purification, "cnot": cnot}


def run_validation(output_dir):
    """Write JSON/CSV/resources/QASM evidence and return a JSON-safe summary.

    Exact deterministic primitive checks only. Failures remain in the evidence
    and set passed=False; missing Qiskit/import or IO failures raise normally.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows, details = [], {"teleportation": [], "bbpssw": [], "cnot": []}

    def record(name, expected, observed):
        difference = float(abs(expected - observed))
        rows.append({"check": name, "expected": float(expected),
                     "observed": float(observed), "absolute_error": difference,
                     "passed": bool(np.isfinite(difference) and difference <= TOLERANCE)})

    states = {"zero": [1, 0], "one": [0, 1],
              "plus": np.array([1, 1]) / np.sqrt(2),
              "minus": np.array([1, -1]) / np.sqrt(2),
              "plus_i": np.array([1, 1j]) / np.sqrt(2),
              "minus_i": np.array([1, -1j]) / np.sqrt(2),
              "generic": np.array([np.sqrt(0.3), np.exp(0.71j) * np.sqrt(0.7)]),
              "mixed": DensityMatrix(np.diag([0.3, 0.7]))}
    channels = {"ideal": identity_channel(), "werner": werner_channel(0.83),
                "asymmetric": np.array([0.61, 0.17, 0.13, 0.09]),
                "aged": age_channel(werner_channel(0.91), 0.7, 2.3),
                **{f"pure_{p}": np.eye(4)[i] for i, p in enumerate("XYZ", 1)}}
    for channel_name, channel in channels.items():
        for state_name, state in states.items():
            actual, branches = teleportation_density(state, channel)
            expected = _direct_pauli_output(state, channel)
            name = f"teleportation/{channel_name}/{state_name}"
            record(name, 0, np.max(np.abs(actual.data - expected)))
            record(name + "/branch_mass", 1, sum(b["probability"] for b in branches))
            # Validate each corrected branch, not just a potentially cancelling mixture.
            for branch in branches:
                matrix = branch["corrected_density"]
                branch_density = np.array(matrix["real"]) + 1j * np.array(matrix["imag"])
                record(name + f"/branch_{branch['m0']}{branch['m1']}", 0,
                       np.max(np.abs(branch_density - expected)))
            details["teleportation"].append({"channel": channel_name, "state": state_name,
                "probabilities_IXYZ": channel.tolist(), "output_density": _matrix(actual.data),
                "expected_density": _matrix(expected), "branches": branches})

    for a, b in ((1, 1), (0.5, 0.5), (0.25, 0.25), (0, 0),
                 (0.8, 0.8), (0.9, 0.65), (0.2, 0.95), (1, 0)):
        expected_f, expected_p = bbpssw(a, b)
        fidelity, acceptance, untwirled, twirled, branches = bbpssw_density(a, b)
        name = f"bbpssw/{a}/{b}"
        record(name + "/fidelity", expected_f, fidelity)
        record(name + "/acceptance", expected_p, acceptance)
        record(name + "/all_branch_mass", 1, sum(row["probability"] for row in branches))
        record(name + "/twirled_werner", 0,
               np.max(np.abs(twirled.data - _bell_density(werner_channel(fidelity)).data)))
        for branch in branches:
            if branch["accepted"]:
                record(name + f"/accepted_{branch['target_A']}{branch['target_B']}/fidelity",
                       expected_f, branch["retained_phi_plus_fidelity"])
                record(name + f"/accepted_{branch['target_A']}{branch['target_B']}/probability",
                       expected_p / 2, branch["probability"])
        details["bbpssw"].append({"fidelity_a": a, "fidelity_b": b,
            "observed_fidelity": fidelity, "observed_acceptance": acceptance,
            "untwirled_density": _matrix(untwirled.data),
            "twirled_density": _matrix(twirled.data), "branches": branches})

    identity, x, z = identity_channel(), np.eye(4)[1], np.eye(4)[3]
    operands = [(identity, identity, identity, identity),
                (x, z, identity, identity),
                (pauli_depolarizing(0.19), dephasing_channel(0.8, 1.3), identity, identity),
                (np.array([0.4, 0.3, 0.2, 0.1]), werner_channel(0.71), identity, identity),
                (x, identity, x, x), (identity, z, z, z),
                (np.array([0.5, 0.5, 0, 0]), identity,
                 np.array([0.5, 0.5, 0, 0]), np.array([0.5, 0.5, 0, 0])),
                (werner_channel(0.7), werner_channel(0.81),
                 dephasing_channel(0.9, 2), pauli_depolarizing(0.15))]
    for index, (a, b, post_a, post_b) in enumerate(operands):
        for error in (0, 0.17, 1):
            observed = cnot_process_check(a, b, error, post_a=post_a, post_b=post_b)
            name = f"cnot/{index}/{error}"
            record(name + "/process", gate_process_fidelity(a, b, error, post_a=post_a, post_b=post_b),
                   observed["process_fidelity"])
            record(name + "/average", gate_average_fidelity(a, b, error, post_a=post_a, post_b=post_b),
                   observed["average_fidelity"])
            record(name + "/cptp", 1, int(observed["is_cptp"]))
            details["cnot"].append({"channel_a": a.tolist(), "channel_b": b.tolist(),
                                     "post_a": post_a.tolist(), "post_b": post_b.tolist(),
                                     "gate_error": error, **observed})

    circuits = _evidence_circuits()
    resources = []
    for name, circuit in circuits.items():
        (output_dir / f"{name}.qasm").write_text(qasm3.dumps(circuit), encoding="utf-8")
        resources.append({"circuit": name, "qubits": circuit.num_qubits,
            "classical_bits": circuit.num_clbits, "depth": circuit.depth(),
            "operations": json.dumps(dict(circuit.count_ops()), sort_keys=True),
            "shots": 0, "execution": "exact_density_matrix_or_Kraus",
            "resource_scope": "ideal protocol skeleton; noise/twirl applied as matrices"})
    summary = {"passed": all(row["passed"] for row in rows), "checks": len(rows),
        "failed_checks": [row["check"] for row in rows if not row["passed"]],
        "max_absolute_error": max(row["absolute_error"] for row in rows),
        "tolerance": TOLERANCE, "backend": "local Qiskit exact density matrices and Kraus channels",
        "qiskit_version": qiskit.__version__, "numpy_version": np.__version__,
        "python_version": platform.python_version(), "shots": 0, "hardware": False,
        "network_execution": False, "whole_network_validated": False,
        "bell_order_IXYZ": ["Phi+", "Psi+", "Psi-", "Phi-"],
        "endianness": "q0 is least significant; tensor order high qubit to low qubit",
        "assumptions": ["independent input Pauli channels; gate errors occur after CNOT",
            "independent post-CNOT return channels; retain correlated pre-gate errors",
            "ideal operations and independent Werner inputs for BBPSSW",
            "accept equal target Z outcomes; no retries",
            "24 Clifford U tensor U* twirl preserves Phi+ fidelity and restores Werner form",
            "primitive circuit checks do not validate scheduling, links, devices or network"]}
    for name, data in (("summary.json", summary), ("details.json", details), ("checks.json", rows)):
        (output_dir / name).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    for name, data in (("checks.csv", rows), ("resources.csv", resources)):
        with (output_dir / name).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    return summary
