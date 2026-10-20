from dataclasses import replace
import math

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from dequint.config import ModelConfig
from dequint.native_mesh import ideal_cnot_choi, run_native_mesh
from dequint.quantum import compose_pauli, gate_process_fidelity, identity_channel, werner_channel
from dequint.routing import manhattan, minimax_meeting
from dequint.workload import Request


def ideal(**changes):
    return replace(ModelConfig(), emission_efficiency=1, detector_efficiency=1,
                   attenuation_db_per_m=0, raw_bell_fidelity=1, memory_t2_s=math.inf,
                   teleport_pauli_error=0, gate_pauli_error=0, **changes)


def test_choi_target_matches_independent_qiskit_qubit_order():
    circuit = QuantumCircuit(4)
    circuit.h(0)
    circuit.h(1)
    circuit.cx(0, 2)
    circuit.cx(1, 3)
    circuit.cx(2, 3)
    expected = np.asarray(Statevector(circuit)).reshape((2,)*4).transpose(3, 2, 1, 0).flatten()
    assert np.allclose(ideal_cnot_choi(), expected)


@pytest.mark.parametrize("policy", ["hh", "midpoint", "queue", "adaptive"])
@pytest.mark.parametrize("placement", ["free", "restored"])
def test_native_4x4_entire_channel_and_real_components(policy, placement):
    request = Request(0, (0, 0), (3, 3), 0, .02)
    result = run_native_mesh(ideal(policy=policy, placement=placement), [request], 201)
    row, summary = result["requests"][0], result["summary"]
    assert row["completed"] and row["process_fidelity"] == pytest.approx(1, abs=1e-9)
    assert row["consumed_pairs"] == row["quantum_hops"] == (6 if placement == "free" else 12)
    assert row["storage_swap_cnot"] == 3*row["quantum_hops"]
    assert summary["native_quantum_cores"] == 16 and summary["native_bsm_nodes"] == 24
    assert summary["native_photon_emissions"] >= 4*row["raw_pairs"]
    assert summary["native_detector_notifications"] > 0
    assert summary["resource_leaks"] == 0 and not summary["hardware"]
    if placement == "restored":
        assert row["final_positions"] == [request.source, request.destination]


@pytest.mark.parametrize("policy", ["hh", "midpoint"])
@pytest.mark.parametrize("placement", ["free", "restored"])
def test_native_noisy_bell_channel_matches_verified_pauli_semantics(policy, placement):
    request = Request(0, (0, 0), (1, 1), 0, .02)
    config = replace(ideal(mesh_side=2, policy=policy, placement=placement), raw_bell_fidelity=.8)
    result = run_native_mesh(config, [request], 202)
    row = result["requests"][0]
    assert row["completed"]
    meeting = request.destination if policy == "hh" else minimax_meeting(request.source, request.destination, 2)
    inputs = []
    for start in (request.source, request.destination):
        channel = identity_channel()
        for _ in range(manhattan(start, meeting)):
            channel = compose_pauli(channel, werner_channel(.8))
        inputs.append(channel)
    posts = inputs if placement == "restored" else [identity_channel(), identity_channel()]
    expected = gate_process_fidelity(*inputs, post_a=posts[0], post_b=posts[1])
    assert row["process_fidelity"] == pytest.approx(expected, abs=1e-9)
    matrix = np.array(row["choi_density_real"]) + 1j*np.array(row["choi_density_imag"])
    assert np.trace(matrix) == pytest.approx(1)
    assert np.linalg.eigvalsh(matrix).min() > -1e-9
    reference_marginal = np.trace(matrix.reshape(4, 4, 4, 4), axis1=1, axis2=3)
    assert np.allclose(reference_marginal, np.eye(4)/4, atol=1e-9)


def test_native_detector_outage_does_not_measure_payload():
    config = replace(ideal(mesh_side=2), detector_efficiency=0, max_attempts=2)
    result = run_native_mesh(config, [Request(0, (0, 0), (0, 1), 0, .01)], 201)
    row = result["requests"][0]
    assert not row["completed"] and row["epr_attempts"] == 2 and row["quantum_hops"] == 0
    assert not any(e["action"] == "native_payload_measured" for e in result["events"])


def test_native_short_cutoff_rejects_pair_before_destructive_use():
    result = run_native_mesh(ideal(mesh_side=2, memory_cutoff_s=1e-12),
                             [Request(0, (0, 0), (0, 1), 0, .01)], 201)
    row = result["requests"][0]
    assert not row["completed"] and row["quantum_hops"] == 0
    assert row["terminal_reason"] == "pair_expired_during_native_generation"


def test_native_correction_loss_never_retries_the_unknown_input():
    result = run_native_mesh(ideal(mesh_side=2, packet_loss=1, max_attempts=2),
                             [Request(0, (0, 0), (0, 1), 0, .01)], 201)
    row = result["requests"][0]
    assert not row["completed"] and row["quantum_hops"] == row["raw_pairs"] == 1
    assert row["terminal_reason"] == "native_correction_unconfirmed"


def test_native_radio_and_stored_payload_dephasing():
    config = replace(ideal(mesh_side=2, classical="radio"), memory_t2_s=.001)
    result = run_native_mesh(config, [Request(0, (0, 0), (1, 1), 0, .01)], 201)
    assert result["requests"][0]["completed"]
    assert .25 <= result["requests"][0]["process_fidelity"] < 1
    assert result["summary"]["radio_busy_s"] > 0


def test_native_shared_mesh_retains_multiple_independent_choi_channels():
    requests = [Request(i, (0, i % 2), (3, 3-i % 2), 0, .02) for i in range(4)]
    result = run_native_mesh(ideal(policy="midpoint", communication_memories=2), requests, 203,
                             data_slots_per_core=4)
    assert all(row["completed"] for row in result["requests"])
    assert all(row["process_fidelity"] == pytest.approx(1, abs=1e-9) for row in result["requests"])
    assert result["summary"]["quantum_queue_wait_s"] > 0


def test_native_storage_cnots_hold_the_shared_core_gate():
    config = ideal(mesh_side=2, gate_s=.001)
    requests = [Request(i, (0, 0), (1, 1), 0, .03) for i in range(2)]
    result = run_native_mesh(config, requests, 201)
    starts = [e for e in result["events"] if e["action"] == "native_storage_cnot_started"]
    assert starts and all(e["gate_resource_used"] == 1 for e in starts)
    for core in {tuple(e["core"]) for e in starts}:
        times = sorted(e["time_s"] for e in starts if tuple(e["core"]) == core)
        assert all(b-a >= .001-1e-12 for a, b in zip(times, times[1:]))
    assert all(row["completed"] for row in result["requests"])


def test_partial_native_swap_counts_completed_and_started_cnots():
    result = run_native_mesh(ideal(mesh_side=2, gate_s=.001),
                             [Request(0, (0, 0), (0, 1), 0, .0016)], 201)
    row = result["requests"][0]
    assert not row["completed"]
    completed = sum(e["action"] == "native_storage_cnot_completed" for e in result["events"])
    started = sum(e["action"] == "native_storage_cnot_started" for e in result["events"])
    assert 0 < completed < started
    assert row["storage_swap_cnot"] == completed
    assert row["storage_swap_cnot_started"] == started
    assert result["summary"]["storage_swap_cnot_completed"] == completed
