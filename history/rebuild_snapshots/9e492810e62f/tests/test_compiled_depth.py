"""Tests confined to the separately versioned compiled-depth experiment."""

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator

from dequint.compiled_depth import (
    assert_connectivity, build_teleport, cases, compile_teleport, events,
    hop_branch_check, resources, schedule, swap_control, verify_channel,
)


@pytest.mark.parametrize("graph", list(cases()), ids=lambda graph: graph.name)
@pytest.mark.parametrize("policy", ["endpoint", "rendezvous"])
def test_compiled_full_channel_and_return(graph, policy):
    source, metadata = build_teleport(graph, policy)
    circuit = compile_teleport(graph, source)
    result = verify_channel(circuit, graph.homes)
    assert result["passed"], result
    assert metadata["final_slots"] == graph.homes
    assert metadata["out_hops"] == metadata["return_hops"]
    counts = resources(circuit)
    assert counts["cx_count"] == 5 * metadata["hops"] + 1
    assert counts["conditional_u_slots"] == 2 * metadata["hops"]
    assert counts["measure_count"] == 2 * metadata["hops"]
    assert counts["reset_count"] == 6 * metadata["hops"]
    assert counts["u_count"] == 4 * metadata["hops"]
    assert result["max_active_qubits_including_references"] <= 10


def test_four_outcome_single_hop_instrument():
    check = hop_branch_check()
    assert check["passed"], check
    assert len(check["branches"]) == 4


def test_missing_correction_fails_choi_check():
    graph = next(cases())
    source, _ = build_teleport(graph, "endpoint")
    compiled = compile_teleport(graph, source)
    corrupted = compiled.copy()
    first_condition = next(i for i, inst in enumerate(corrupted.data)
                           if inst.operation.name == "if_else")
    del corrupted.data[first_condition]
    check = verify_channel(corrupted, graph.homes)
    assert not check["passed"]
    assert check["process_fidelity"] < .99


def test_missing_return_fails_same_physical_output_contract():
    graph = next(cases())
    source, _ = build_teleport(graph, "rendezvous", restore=False)
    check = verify_channel(compile_teleport(graph, source), graph.homes)
    assert not check["passed"]


@pytest.mark.parametrize("seed", [201, 202, 203, 204])
def test_swap_control_unitary_and_exact_restoration(seed):
    graph = next(cases())
    compiled, routed, metadata = swap_control(graph, seed)
    expected = QuantumCircuit(graph.num_qubits)
    expected.cx(*graph.homes)
    # A different, full-unitary oracle includes arbitrary spectator states.
    assert Operator(compiled).equiv(Operator(expected))
    assert verify_channel(compiled, graph.homes)["passed"]
    assert metadata["routing_swaps"] == metadata["return_swaps"]
    assert routed.count_ops().get("swap", 0) > 0


def test_wire_layers_match_qiskit_for_plain_unitary():
    graph = next(cases())
    compiled, _, _ = swap_control(graph, 201)
    assert schedule(compiled)["depth"] == compiled.depth()
    assert schedule(compiled, metric="instrument")["depth"] == compiled.depth()


def test_feedback_dependency_and_core_serialization():
    circuit = QuantumCircuit(6, 1)
    circuit.cx(0, 1)
    circuit.measure(1, 0)
    with circuit.if_test((circuit.clbits[0], True)):
        circuit.u(np.pi, 0, np.pi, 5)
    circuit.u(.1, 0, 0, 3)
    schedule_result = schedule(circuit)
    assert schedule_result["events"][2]["start"] == 1
    assert schedule_result["depth"] == 2
    assert schedule(circuit, metric="instrument")["depth"] == 3
    assert schedule(circuit, core_serial=True)["depth"] == 3


def test_unmodelled_nonlocal_gate_is_rejected():
    graph = next(cases())
    circuit = QuantumCircuit(graph.num_qubits)
    circuit.cx(*graph.homes)
    with pytest.raises(ValueError, match="nonlocal"):
        assert_connectivity(circuit, graph)


def test_both_policies_same_resource_graph_and_counts():
    for graph in cases():
        compiled = [compile_teleport(graph, build_teleport(graph, policy)[0])
                    for policy in ("endpoint", "rendezvous")]
        assert resources(compiled[0]) == resources(compiled[1])
        for circuit in compiled:
            assert all(e["name"] in {"u", "cx", "measure", "reset"} for e in events(circuit))
            for metric in ("quantum", "instrument", "cx"):
                assert schedule(circuit, metric=metric, core_serial=True)["depth"] >= schedule(
                    circuit, metric=metric)["depth"]


def test_invalid_inputs_are_not_silent():
    graph = next(cases())
    with pytest.raises(ValueError):
        build_teleport(graph, "adaptive")
    with pytest.raises(ValueError):
        schedule(QuantumCircuit(1), metric="latency")
    with pytest.raises(ValueError):
        verify_channel(QuantumCircuit(2), [0, 0])
