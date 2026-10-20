"""Small application timing checks, not comparative experiments."""

from dataclasses import replace
import json
import math

import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator

from dequint.application_replay import ApplicationReplay, build_circuit
from dequint.config import ModelConfig


def config(**changes):
    defaults = dict(mesh_side=2, memory_t2_s=math.inf, raw_bell_fidelity=1,
                    teleport_pauli_error=0, gate_pauli_error=0)
    return replace(ModelConfig(), **(defaults | changes))


def certain(replay):
    replay.network.streams.random = lambda *key: 0.0
    return replay


@pytest.mark.parametrize("name,size,qubits", [
    ("ghz", 3, 3), ("qft", 3, 3), ("cdkm", 1, 4),
    ("quantum_volume", 2, 2),
])
def test_builders_and_logical_metrics(name, size, qubits):
    circuit = build_circuit(name, size, 23)
    mapping = {i: (i % 2, i // 2 % 2) for i in range(qubits)}
    replay = certain(ApplicationReplay(config(), circuit, mapping, 23))
    result = replay.run()
    assert circuit.num_qubits == qubits
    assert result["summary"]["completed"]
    assert result["circuit"]["input_depth"] == circuit.depth()
    assert result["circuit"]["input_count_ops"] == dict(circuit.count_ops())
    basis = replay.basis_circuit
    assert set(basis.count_ops()) <= {"u", "cx", "barrier"}
    assert result["circuit"]["basis_qasm"].startswith("OPENQASM 3.0;")
    assert Operator(basis).equiv(Operator(circuit))
    assert result["summary"]["end_to_end_state_fidelity"] is None
    assert result["summary"]["compiled_physical_circuit_depth"] is None
    assert result["summary"]["resource_leaks"] == 0
    json.dumps(result, allow_nan=False)


def test_per_qubit_dependency_order_uses_actual_finishes():
    circuit = QuantumCircuit(3)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.x(0)
    circuit.h(1)
    circuit.cx(1, 2)
    result = certain(ApplicationReplay(config(), circuit,
                     [(0, 0), (0, 1), (1, 1)], 7)).run()
    rows = result["operations"]
    assert len(rows) == 5
    for row in rows:
        assert row["completed"]
        for predecessor in row["predecessors"]:
            assert row["started_s"] >= rows[predecessor]["finished_s"]
        assert row["finished_s"] <= .2


def test_disjoint_ready_gates_really_overlap_on_distinct_core_resources():
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.x(1)
    result = ApplicationReplay(config(gate_s=.001), circuit,
                               [(0, 0), (1, 1)], 9).run()
    first, second = result["operations"]
    assert first["gate_started_s"] == second["gate_started_s"] == 0
    assert first["gate_finished_s"] == second["gate_finished_s"] == .001
    assert result["summary"]["application_makespan_s"] == .001


def test_disjoint_cnot_resource_paths_really_overlap():
    circuit = QuantumCircuit(4)
    circuit.cx(0, 1)
    circuit.cx(2, 3)
    replay = certain(ApplicationReplay(config(gate_s=.001), circuit,
                     [(0, 0), (0, 1), (1, 0), (1, 1)], 9))
    result = replay.run()
    first, second = result["operations"]
    assert first["gate_started_s"] == second["gate_started_s"]
    assert first["gate_started_s"] < second["gate_finished_s"]
    assert second["gate_started_s"] < first["gate_finished_s"]
    assert result["summary"]["completed_cnot_gates"] == 2


def test_single_qubit_gates_contend_on_same_core_and_declared_duration():
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.x(1)
    result = ApplicationReplay(config(gate_s=.003), circuit,
                               [(0, 0), (0, 0)], 9,
                               single_qubit_gate_s=.001).run()
    first, second = result["operations"]
    assert second["gate_started_s"] == first["gate_finished_s"] == .001
    assert result["summary"]["application_makespan_s"] == .002
    assert result["summary"]["quantum_queue_wait_s"] == pytest.approx(.001)
    assert result["summary"]["single_qubit_gate_s"] == .001


def test_local_and_cnot_gates_share_the_same_core_gate_resource():
    circuit = QuantumCircuit(3)
    circuit.cx(0, 1)
    circuit.x(2)
    result = ApplicationReplay(config(gate_s=.001), circuit,
                               [(0, 0)] * 3, 9).run()
    first, second = sorted(result["operations"], key=lambda row: row["gate_started_s"])
    assert first["gate_finished_s"] <= second["gate_started_s"]
    assert result["summary"]["application_makespan_s"] == .002
    assert result["summary"]["resource_leaks"] == 0


@pytest.mark.parametrize("placement", ["free", "restored"])
@pytest.mark.parametrize("classical", ["wired", "radio"])
def test_dynamic_mapping_is_used_by_following_local_and_cnot_gates(placement, classical):
    circuit = QuantumCircuit(3)
    circuit.cx(0, 1)
    circuit.x(0)
    circuit.cx(0, 2)
    initial = {0: (0, 0), 1: (0, 1), 2: (1, 1)}
    result = certain(ApplicationReplay(config(placement=placement, classical=classical), circuit,
                                       initial, 11)).run()
    first, local, last = result["operations"]
    expected = [0, 1] if placement == "free" else [0, 0]
    assert local["mapping_before"]["0"] == expected
    assert last["mapping_before"]["0"] == expected
    assert result["cnot_tasks"][1]["source"] == tuple(expected)
    assert result["summary"]["quantum_hops"] == (2 if placement == "free" else 6)
    if placement == "restored":
        assert result["final_mapping"] == {str(q): list(p) for q, p in initial.items()}
    else:
        assert result["final_mapping"] == {"0": [1, 1], "1": [0, 1], "2": [1, 1]}
    assert first["finished_s"] <= local["gate_started_s"] <= last["started_s"]
    assert result["mapping_history"]


def test_failed_predecessor_cancels_descendants_but_not_disjoint_work():
    circuit = QuantumCircuit(4)
    circuit.cx(0, 1)
    circuit.x(0)
    circuit.cx(0, 2)
    circuit.h(3)
    result = ApplicationReplay(config(source_outage_probability=1, max_attempts=1),
                               circuit, [(0, 0), (0, 1), (1, 0), (1, 1)], 17).run()
    rows = result["operations"]
    assert not result["summary"]["completed"]
    assert result["summary"]["failed_operations"] == 1
    assert result["summary"]["cancelled_operations"] == 2
    assert result["summary"]["completed_operations"] == 1
    assert sum(row["status"] == "cancelled" for row in rows) == 2
    assert all(row["started_s"] is None for row in rows if row["status"] == "cancelled")
    assert len(result["cnot_tasks"]) == 1
    assert result["cnot_tasks"][0]["terminal_reason"] == "epr_attempt_bound"
    assert result["summary"]["completed_application_makespan_s"] is None
    assert result["summary"]["end_to_end_state_fidelity"] is None
    assert result["summary"]["resource_leaks"] == 0


def test_local_deadline_failure_cancels_dependents():
    circuit = QuantumCircuit(1)
    circuit.h(0)
    circuit.x(0)
    result = ApplicationReplay(config(gate_s=.002), circuit, [(0, 0)], 1,
                               deadline_s=.001).run()
    first, second = result["operations"]
    assert first["status"] == "failed"
    assert first["finished_s"] == .001
    assert second["status"] == "cancelled"
    assert result["summary"]["resource_leaks"] == 0


def test_failure_cancels_join_immediately_without_waiting_for_other_predecessor():
    circuit = QuantumCircuit(3)
    circuit.cx(0, 1)
    circuit.x(2)
    circuit.cx(0, 2)
    result = ApplicationReplay(config(gate_s=.001, source_outage_probability=1,
                                       max_attempts=1), circuit,
                               [(0, 0), (0, 1), (1, 1)], 13).run()
    failed = next(row for row in result["operations"] if row["status"] == "failed")
    independent = next(row for row in result["operations"] if row["name"] == "u")
    cancelled = next(row for row in result["operations"] if row["status"] == "cancelled")
    assert cancelled["finished_s"] == failed["finished_s"] < independent["finished_s"]
    assert cancelled["blocked_by"] == [failed["operation_id"]]


def test_post_measurement_failure_retains_actual_location_without_running_dependents():
    circuit = QuantumCircuit(2)
    circuit.cx(0, 1)
    circuit.x(0)
    replay = certain(ApplicationReplay(config(), circuit, [(0, 0), (0, 1)], 13))
    original = replay.network.fabric.send

    def fail_correction(source, destination, bits, deadline, owner, tag):
        if tag.startswith("correction:"):
            yield replay.network.kernel.delay(1e-9)
            return False
        return (yield from original(source, destination, bits, deadline, owner, tag))

    replay.network.fabric.send = fail_correction
    result = replay.run()
    assert result["final_mapping"]["0"] == [0, 1]
    assert result["operations"][1]["status"] == "cancelled"
    assert result["failed_operand_qubits"] == [0, 1]
    assert result["summary"]["consumed_pairs"] == 1
    assert [entry["action"] for entry in result["mapping_history"]] == ["payload_measured"]
    assert result["summary"]["resource_leaks"] == 0


def test_barrier_is_a_dependency_fence_not_a_local_gate():
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.barrier()
    circuit.x(1)
    result = ApplicationReplay(config(gate_s=.001), circuit,
                               [(0, 0), (1, 1)], 1).run()
    first, barrier, last = result["operations"]
    assert barrier["name"] == "barrier"
    assert barrier["gate_started_s"] is None
    assert last["started_s"] == first["finished_s"] == .001
    assert result["summary"]["application_makespan_s"] == .002


def test_seed_reproducibility_and_policy_independent_input_identity():
    circuit = build_circuit("quantum_volume", 2, 19)
    initial = [(0, 0), (1, 1)]
    first = ApplicationReplay(config(), circuit, initial, 19).run()
    second = ApplicationReplay(config(), circuit, initial, 19).run()
    assert first == second
    other = ApplicationReplay(config(policy="midpoint"), circuit, initial, 19).run()
    assert first["circuit"] == other["circuit"]
    assert first["initial_mapping"] == other["initial_mapping"]
    assert first["summary"]["application_input_sha256"] == other["summary"]["application_input_sha256"]
    assert first["summary"]["deadline_s"] == other["summary"]["deadline_s"] == .2
    different = build_circuit("quantum_volume", 2, 20)
    assert circuit != different


def test_noisy_per_gate_quality_is_not_application_failure_or_fidelity():
    circuit = QuantumCircuit(2)
    circuit.cx(0, 1)
    circuit.x(0)
    result = certain(ApplicationReplay(config(memory_cutoff_s=.02, gate_pauli_error=.9),
                                       circuit, [(0, 0), (0, 1)], 11)).run()
    assert result["summary"]["completed"]
    assert not result["cnot_tasks"][0]["quality_qualified"]
    assert result["summary"]["end_to_end_state_fidelity"] is None


def test_rejects_unsupported_or_ambiguous_inputs_and_repeated_run():
    with pytest.raises(ValueError, match="quantum_volume"):
        build_circuit("quantum_volume", 9, 0)
    with pytest.raises(ValueError, match="Unknown"):
        build_circuit("invented", 2, 0)
    circuit = QuantumCircuit(1)
    circuit.reset(0)
    with pytest.raises(ValueError, match="Unsupported"):
        ApplicationReplay(config(), circuit, [(0, 0)], 1)
    circuit = QuantumCircuit(1, 1)
    circuit.measure(0, 0)
    with pytest.raises(ValueError, match="classical"):
        ApplicationReplay(config(), circuit, [(0, 0)], 1)
    circuit = QuantumCircuit(1)
    circuit.h(0)
    with pytest.raises(ValueError, match="mapping"):
        ApplicationReplay(config(), circuit, [], 1)
    with pytest.raises(ValueError, match="deadline"):
        ApplicationReplay(config(), circuit, [(0, 0)], 1, deadline_s=math.inf)
    replay = ApplicationReplay(config(), circuit, [(0, 0)], 1)
    replay.run()
    with pytest.raises(RuntimeError, match="once"):
        replay.run()
