"""Focused graph/provisioning checks; no native optical/gate validation claim."""

import json
import math
from dataclasses import replace
from itertools import product

import networkx as nx
import pytest

from dequint.kernel import FifoResource, Kernel
from dequint.shortcut_probe import (
    ProbeConfig, ShortcutProbe, build_topology, compare_topologies,
    constructive_path, link_parameters, main, probe_workload, topology_cost,
)
from dequint.workload import Request, workload_hash


def request(index=0, source=(0, 0), target=(0, 1), deadline=.1, arrival=0):
    return Request(index, source, target, arrival, deadline)


def quick_config(**kwargs):
    return replace(ProbeConfig(side=2, attenuation_db_per_m=0, emission_efficiency=1,
                               detector_efficiency=1, excitation_rate_hz=1000,
                               reset_s=0, raw_bell_fidelity=1, memory_t2_s=1e30,
                               teleport_pauli_error=0, gate_pauli_error=0,
                               teleport_s=.0001, gate_s=.0002), **kwargs)


def assert_drained(result):
    for resource in result["resources"]:
        assert resource["used"] == resource["waiting_units"] == 0
        assert 0 <= resource["peak_used"] <= resource["capacity"]
        assert resource["integral_used_s"] >= 0
    for row in result["rows"]:
        assert row["attempts"] == row["completed_attempts"] + row["aborted_attempts"]
        assert row["completed_attempts"] == row["raw_pairs"] + row["failed_attempts"]
        assert row["raw_pairs"] == row["pairs_consumed"] + row["pairs_discarded"]
        assert row["quantum_hops"] <= row["pairs_consumed"]
        assert row["wait_s"] == pytest.approx(sum(row[k] for k in (
            "port_wait_s", "channel_wait_s", "generator_wait_s", "gate_wait_s")))


@pytest.mark.parametrize("side", [0, 1, 3, 6, -2, True, 4.0, "4", None])
def test_invalid_sizes(side):
    with pytest.raises(ValueError):
        build_topology(ProbeConfig(side=side))
    with pytest.raises(ValueError):
        constructive_path(side, 0, 0)


@pytest.mark.parametrize("side", [2, 4, 8])
def test_constructive_append_bits_all_pairs(side):
    graph = build_topology(ProbeConfig(side=side))
    n, m = side**2, (side**2).bit_length() - 1
    distances = dict(nx.all_pairs_shortest_path_length(graph))
    assert not graph.is_directed() and nx.number_of_selfloops(graph) == 0
    assert nx.is_connected(graph)
    assert max(dict(graph.degree()).values()) <= 8
    assert nx.diameter(graph) <= m
    for source, destination in product(range(n), repeat=2):
        path = constructive_path(side, source, destination)
        assert path[0] == source and path[-1] == destination
        assert len(path) == len(set(path))
        assert len(path) - 1 <= m
        assert distances[source][destination] <= len(path) - 1
        for a, b in zip(path, path[1:]):
            assert graph.has_edge(a, b)
            assert graph[a][b]["debruijn"]


@pytest.mark.parametrize("a,b", [(-1, 0), (0, 16), (True, 0), (1.0, 0)])
def test_constructive_invalid_nodes(a, b):
    with pytest.raises(ValueError):
        constructive_path(4, a, b)


@pytest.mark.parametrize("change", [
    {"ports_per_node": 0}, {"ports_per_node": True}, {"generator_capacity": 1.5},
    {"max_attempts": 0}, {"max_events": 0}, {"pitch_m": 0},
    {"attenuation_db_per_m": -1}, {"shortcut_insertion_loss_db": -1},
    {"shortcut_insertion_loss_db": math.inf}, {"excitation_rate_hz": math.nan},
    {"propagation_m_per_s": 0}, {"memory_t2_s": -1}, {"reset_s": -1},
    {"emission_efficiency": 1.1}, {"detector_efficiency": True},
    {"topology": "new"}, {"generator_mode": "unlimited"}, {"route_metric": "magic"},
    {"scaling": "fixed_footprint"}, {"footprint_m": .01}, {"placement": "other"},
])
def test_invalid_config(change):
    with pytest.raises(ValueError):
        replace(ProbeConfig(), **change).validate()


def test_euclidean_distance_loss_and_two_round_propagation():
    config = quick_config(side=4, pitch_m=.01, attenuation_db_per_m=1000,
                          excitation_rate_hz=20_000, reset_s=50e-9)
    graph = build_topology(config)
    for a, b, data in graph.edges(data=True):
        expected_length = math.dist(divmod(a, 4), divmod(b, 4)) * .01
        assert data["length_m"] == pytest.approx(expected_length)
        assert data["transmission"] == pytest.approx(10 ** (-1000 * expected_length / 10))
        assert data["generation_success"] == pytest.approx(.5 * data["transmission"])
        assert data["attempt_s"] == pytest.approx(2 / 20_000 + 50e-9 + 2 * expected_length / 2e8)
    short = link_parameters(config, .001)
    long = link_parameters(config, .02)
    assert long["generation_success"] < short["generation_success"]
    assert long["attempt_s"] > short["attempt_s"]
    assert long["transfer_s"] > short["transfer_s"]
    assert long["expected_time"] > short["expected_time"]


def test_insertion_once_only_for_added_physical_edges():
    base = ProbeConfig(side=4, attenuation_db_per_m=1000)
    lossy = replace(base, shortcut_insertion_loss_db=3)
    first, second = build_topology(base), build_topology(lossy)
    assert set(first.edges) == set(second.edges)
    mesh_overlap = added = 0
    for a, b, data in second.edges(data=True):
        ratio = data["generation_success"] / first[a][b]["generation_success"]
        if data["mesh"]:
            assert data["insertion_loss_db"] == 0
            assert ratio == pytest.approx(1)
            mesh_overlap += int(data["debruijn"])
        else:
            added += 1
            assert data["insertion_loss_db"] == 3
            assert ratio == pytest.approx(10 ** (-3 / 10))  # NOT per-arm or per-round twice.
        assert data["attempt_s"] == first[a][b]["attempt_s"]
    assert mesh_overlap > 0 and added > 0
    assert build_topology(replace(lossy, topology="mesh")).edges[0, 1]["insertion_loss_db"] == 0


def test_fixed_pitch_vs_fixed_footprint_and_installation_cost():
    small = ProbeConfig(side=4, pitch_m=.001, generator_capacity=16)
    large = replace(small, side=8)
    c4, c8 = topology_cost(small), topology_cost(large)
    assert c4["effective_pitch_m"] == c8["effective_pitch_m"] == .001
    assert c8["footprint_side_m"] > c4["footprint_side_m"]
    fixed4 = topology_cost(replace(small, scaling="fixed_footprint", footprint_m=.01))
    fixed8 = topology_cost(replace(large, scaling="fixed_footprint", footprint_m=.01))
    assert fixed4["footprint_side_m"] == fixed8["footprint_side_m"] == .01
    assert fixed8["effective_pitch_m"] < fixed4["effective_pitch_m"]
    overlay = build_topology(small)
    mesh = topology_cost(replace(small, topology="mesh"))
    assert mesh["edges"] == 2 * 4 * 3
    assert c4["edges"] > mesh["edges"]
    assert c4["edge_terminations"] == 2 * c4["edges"]
    assert c4["switchable_active_ports"] == mesh["switchable_active_ports"] == 16 * 2
    assert c4["total_generator_capacity"] == mesh["total_generator_capacity"] == 16
    assert c4["total_optical_length_m"] == pytest.approx(sum(d["length_m"] for _, _, d in overlay.edges(data=True)))
    assert c4["max_link_m"] == max(d["length_m"] for _, _, d in overlay.edges(data=True))
    assert c4["channel_capacity_per_physical_edge"] == 1
    assert c4["total_optical_length_m"] > mesh["total_optical_length_m"]
    per_link = topology_cost(replace(small, generator_mode="per_link", generator_capacity=2))
    assert per_link["total_generator_capacity"] == 2 * c4["edges"]


def test_workload_reproducibility_and_compare_scope():
    requests = probe_workload(2, 3, 301)
    assert requests == probe_workload(2, 3, 301)
    assert workload_hash(requests) != workload_hash(probe_workload(2, 3, 302))
    result = compare_topologies(quick_config(generator_capacity=16), requests, seed=301)
    assert result["matched_global_generation_capacity"]
    hashes = [r["workload_hash"] for r in result["runs"].values()]
    assert hashes == [workload_hash(requests)] * 2
    for run in result["runs"].values():
        assert not run["full_native_gate_validation"] and not run["hardware"]
        assert not run["topology_novelty_claim"]
        assert run["cost"]["total_generator_capacity"] == 16
        assert_drained(run)
    again = compare_topologies(quick_config(generator_capacity=16), requests, seed=301)
    assert result == again
    assert not compare_topologies(quick_config(generator_mode="per_link"), [request()])["matched_global_generation_capacity"]


@pytest.mark.parametrize("placement", ["free", "restored"])
def test_ordered_endpoint_task_accounting_and_analytic_quality(placement):
    config = quick_config(placement=placement)
    probe = ShortcutProbe(config, [request()], seed=301)
    assert isinstance(probe.kernel, Kernel)
    assert all(isinstance(p, FifoResource) for p in probe.ports.values())
    result = probe.run()
    row = result["rows"][0]
    assert row["completed"]
    assert row["quantum_hops"] == row["pairs_consumed"] == (2 if placement == "restored" else 1)
    assert row["conditional_process_fidelity"] == pytest.approx(1)
    assert row["target_position"] == 1
    assert row["control_position"] == (0 if placement == "restored" else 1)
    edge = probe.graph[0][1]
    # Round each native delay to its picosecond tick, independently.
    attempt = round(edge["attempt_s"] * 1e12) / 1e12
    transfer = round(edge["transfer_s"] * 1e12) / 1e12
    expected = row["attempts"] * attempt + row["quantum_hops"] * transfer + config.gate_s
    assert row["latency_s"] == pytest.approx(expected, abs=1e-12)
    assert row["retries"] == row["failed_attempts"]
    assert row["gate_timers_completed"] == 1
    assert_drained(result)
    with pytest.raises(ValueError):
        probe.run()


def test_shared_edge_exclusion_even_with_global16_and_two_ports():
    config = quick_config(generator_capacity=16, ports_per_node=2)
    result = ShortcutProbe(config, [request(0), request(1)], seed=301).run()
    assert all(r["completed"] for r in result["rows"])
    assert sum(r["channel_wait_s"] for r in result["rows"]) > 0
    channels = [r for r in result["resources"] if r["name"].startswith("channel:")]
    assert all(r["peak_used"] <= 1 for r in channels)
    assert_drained(result)


def test_global_capacity_is_shared_across_disjoint_edges():
    requests = [request(0), request(1, (1, 0), (1, 1))]
    result = ShortcutProbe(quick_config(generator_capacity=1), requests, seed=301).run()
    generator = next(r for r in result["resources"] if r["name"] == "generator:global")
    assert generator["peak_used"] == 1
    assert sum(r["generator_wait_s"] for r in result["rows"]) > 0
    assert_drained(result)


def test_port_capacity_serializes_different_incident_edges():
    requests = [request(0), request(1, (0, 0), (1, 0))]
    result = ShortcutProbe(quick_config(ports_per_node=1, generator_capacity=16), requests, seed=301).run()
    assert all(r["completed"] for r in result["rows"])
    assert sum(r["port_wait_s"] for r in result["rows"]) > 0
    assert_drained(result)


def test_attempt_bound_failure_retries_and_release():
    config = quick_config(source_outage_probability=1, max_attempts=3)
    result = ShortcutProbe(config, [request()], seed=301).run()
    row = result["rows"][0]
    assert not row["completed"] and row["terminal_reason"] == "attempt_bound"
    assert row["attempts"] == row["failed_attempts"] == 3
    assert row["retries"] == 2
    assert row["pairs_consumed"] == row["raw_pairs"] == 0
    assert row["conditional_process_fidelity"] is None
    assert_drained(result)


def test_deadline_mid_attempt_and_expired_queue_release():
    config = quick_config(ports_per_node=1, source_outage_probability=1)
    result = ShortcutProbe(config, [request(0, deadline=.003), request(1, deadline=.001)], seed=301).run()
    first, second = result["rows"]
    assert first["terminal_reason"] == "deadline" and first["aborted_attempts"] == 1
    assert second["terminal_reason"] == "resource_deadline" and second["attempts"] == 0
    assert second["port_wait_s"] == pytest.approx(.001)
    assert first["finished_s"] <= first["deadline_s"]
    assert_drained(result)


def test_failure_after_pair_consumption_does_not_retry_payload():
    config = quick_config(teleport_s=.1)
    result = ShortcutProbe(config, [request(deadline=.01)], seed=301).run()
    row = result["rows"][0]
    assert not row["completed"] and row["terminal_reason"] == "deadline"
    assert row["raw_pairs"] == row["pairs_consumed"] == 1
    assert row["quantum_hops"] == 0 and row["control_position"] is None
    assert row["conditional_process_fidelity"] is None
    assert_drained(result)


def test_local_task_needs_no_pair_but_has_exclusive_gate_timer():
    result = ShortcutProbe(quick_config(), [request(source=(0, 0), target=(0, 0))]).run()
    row = result["rows"][0]
    assert row["completed"] and row["latency_s"] == pytest.approx(.0002)
    assert row["attempts"] == row["pairs_consumed"] == row["planned_hops"] == 0
    assert_drained(result)


def test_local_subpicosecond_arrival_quantizes_without_negative_aging():
    config = quick_config(gate_s=0)
    result = ShortcutProbe(config, [request(source=(0, 0), target=(0, 0), arrival=.0001230000001)]).run()
    row = result["rows"][0]
    assert row["completed"] and row["latency_s"] >= 0
    assert row["conditional_process_fidelity"] == 1
    assert_drained(result)


def test_deadline_during_gate_releases_gate_lease():
    config = quick_config(gate_s=.1)
    result = ShortcutProbe(config, [request(source=(0, 0), target=(0, 0), deadline=.001)]).run()
    row = result["rows"][0]
    assert not row["completed"] and row["terminal_reason"] == "deadline"
    assert row["gate_timers_completed"] == 0
    assert row["conditional_process_fidelity"] is None
    assert_drained(result)


def test_successful_pair_at_deadline_is_discarded_not_used():
    config = quick_config()
    # First determine the reproducible accepted attempt, then set that exact tick
    # as the deadline. This is one edge, not a workload/sensitivity experiment.
    first = ShortcutProbe(config, [request()], seed=301)
    result = first.run()
    accepted = next(e for e in result["events"] if e["action"] == "attempt" and e["accepted"])
    result = ShortcutProbe(config, [request(deadline=accepted["time_s"])], seed=301).run()
    row = result["rows"][0]
    assert row["raw_pairs"] == row["pairs_discarded"] == 1
    assert row["pairs_consumed"] == 0 and not row["completed"]
    assert_drained(result)


def test_nonideal_conditional_quality_and_restored_return_penalty():
    config = quick_config(raw_bell_fidelity=.9, teleport_pauli_error=.01,
                          gate_pauli_error=.01, memory_t2_s=.1)
    free = ShortcutProbe(config, [request()], seed=301).run()["rows"][0]
    restored = ShortcutProbe(replace(config, placement="restored"), [request()], seed=301).run()["rows"][0]
    assert free["completed"] and restored["completed"]
    assert 0 < restored["conditional_process_fidelity"] < free["conditional_process_fidelity"] < 1
    assert restored["pairs_consumed"] == 2 * free["pairs_consumed"]
    assert restored["conditional_average_gate_fidelity"] == pytest.approx(
        (4 * restored["conditional_process_fidelity"] + 1) / 5)


def test_expected_time_route_uses_networkx_weights():
    config = quick_config(side=4, route_metric="expected_time", attenuation_db_per_m=1000,
                          shortcut_insertion_loss_db=3)
    req = request(source=(0, 0), target=(3, 3))
    probe = ShortcutProbe(config, [req])
    expected = nx.shortest_path(probe.graph, 0, 15, weight="expected_time")
    result = probe.run()
    assert result["rows"][0]["route"] == expected
    assert_drained(result)


@pytest.mark.parametrize("requests", [[], [request(), request()],
    [request(source=(-1, 0))], [request(target=(2, 0))],
    [request(source=(True, 0))], [request(deadline=0)],
    [request(arrival=-1)], [request(deadline=math.inf)]])
def test_invalid_workloads(requests):
    with pytest.raises(ValueError):
        ShortcutProbe(quick_config(), requests)


def test_cli_json_only_small_focused_smoke(capsys):
    main(["--side", "2", "--requests", "1", "--generator-capacity", "16",
          "--scaling", "fixed_footprint", "--footprint-m", ".01",
          "--attenuation-db-per-m", "1000", "--shortcut-insertion-loss-db", "3"])
    result = json.loads(capsys.readouterr().out)
    assert set(result["runs"]) == {"mesh", "mesh_debruijn"}
    assert result["matched_global_generation_capacity"]
    assert result["runs"]["mesh_debruijn"]["config"]["shortcut_insertion_loss_db"] == 3
