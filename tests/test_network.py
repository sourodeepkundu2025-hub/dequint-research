from dataclasses import replace
import math

import pytest

from dequint.config import ModelConfig
from dequint.network import EPRGenTable, Job, Network, Operand
from dequint.quantum import identity_channel
from dequint.workload import Request, make_workload


def ideal(**kwargs):
    return replace(ModelConfig(), raw_bell_fidelity=1, memory_t2_s=math.inf,
                   teleport_pauli_error=0, gate_pauli_error=0, deadline_s=.1, **kwargs)


@pytest.mark.parametrize("policy", ["hh", "midpoint", "queue", "adaptive", "paper_midpoint"])
@pytest.mark.parametrize("placement", ["free", "restored"])
def test_same_gate_task_and_exact_pair_counts(policy, placement):
    request = Request(0, (0, 0), (3, 2), 0, .1)
    result = Network(ideal(policy=policy, placement=placement), [request], 31, trace=True).run()
    row = result["requests"][0]
    assert row["completed"] and row["quality_qualified"]
    assert row["quantum_hops"] == row["consumed_pairs"] == (5 if placement == "free" else 10)
    assert row["process_fidelity"] == pytest.approx(1)
    assert row["raw_pairs"] == row["consumed_pairs"]
    assert sum(e["action"] == "two_qubit_gate" for e in result["events"]) == 1
    assert result["summary"]["resource_leaks"] == 0


def test_generation_outage_charges_attempts_and_never_measures_input():
    result = Network(ideal(source_outage_probability=1, max_attempts=3),
                     [Request(0, (0, 0), (0, 1), 0, .01)], 9, trace=True).run()
    row = result["requests"][0]
    assert not row["completed"] and row["epr_attempts"] == 3
    assert row["terminal_reason"] == "epr_attempt_bound"
    assert row["quantum_hops"] == 0
    assert not any(e["action"] == "payload_measured" for e in result["events"])


def test_contention_and_deadlines_remain_in_denominator():
    requests = [Request(i, (0, 0), (0, 1), 0, .00015) for i in range(12)]
    result = Network(ideal(communication_memories=1), requests, 19).run()
    assert result["summary"]["requests"] == 12
    assert result["summary"]["completed"] < 12
    assert result["summary"]["quantum_queue_wait_s"] > 0
    assert all(r["finished_s"] <= r["deadline_s"] + 1e-11 for r in result["requests"])
    assert result["summary"]["resource_leaks"] == 0


def test_post_measurement_failure_cannot_restart_payload():
    network = Network(ideal(), [Request(0, (0, 0), (0, 1), 0, .1)], 12, trace=True)
    original_send = network.fabric.send

    def drop_correction(source, destination, bits, deadline, owner, tag):
        if tag.startswith("correction:"):
            yield network.kernel.delay(1e-9)
            return False
        return (yield from original_send(source, destination, bits, deadline, owner, tag))

    network.fabric.send = drop_correction
    result = network.run()
    row = result["requests"][0]
    assert not row["completed"] and row["consumed_pairs"] == 1
    assert row["terminal_reason"].startswith("classical_unconfirmed:correction:")
    assert sum(e["action"] == "payload_measured" for e in result["events"]) == 1


def test_purification_consumes_and_accounts_for_extra_resources():
    config = replace(ideal(), raw_bell_fidelity=.7, purification_rounds=1)
    result = Network(config, [Request(0, (0, 0), (0, 1), 0, .1)], 25, trace=True).run()
    row = result["requests"][0]
    assert row["completed"]
    assert row["purification_attempts"] >= 1
    assert row["purification_accepts"] == 1
    assert row["raw_pairs"] == 2 * row["purification_attempts"]
    assert row["consumed_pairs"] == 1
    assert any(e["action"] == "ideal_werner_input_twirl" for e in result["events"])


def test_quality_is_not_availability():
    config = replace(ideal(), memory_t2_s=3.3e-6)
    result = Network(config, [Request(0, (0, 0), (0, 1), 0, .1)], 13).run()
    row = result["requests"][0]
    assert row["completed"] and not row["quality_qualified"]
    assert row["process_fidelity"] < .9


def test_policy_independent_workload_and_reproducibility():
    config = ideal(policy="adaptive")
    workload = make_workload(4, 10, 3000, 17, .02)
    first = Network(config, workload, 17).run()
    second = Network(config, workload, 17).run()
    for rows in (first["requests"], second["requests"]):
        for row in rows:
            row.pop("controller_wall_s")
    assert first["requests"] == second["requests"]
    assert first["summary"]["workload_sha256"] == second["summary"]["workload_sha256"]
    assert all(r["predicted_process_fidelity"] is not None for r in first["requests"])


def test_pair_identifier_is_single_use_not_verification():
    table = EPRGenTable()
    pair = table.allocate(identity_channel(), 0, "job")
    table.consume(pair, "job")
    with pytest.raises(RuntimeError):
        table.consume(pair, "job")


@pytest.mark.parametrize("rounds", [0, 1])
def test_expired_resources_cannot_teleport(rounds):
    config = replace(ideal(), memory_cutoff_s=1e-12,
                     raw_bell_fidelity=.7, purification_rounds=rounds)
    network = Network(config, [Request(0, (0, 0), (0, 1), 0, .1)], 12, trace=True)
    network.streams.random = lambda *args: 0.0
    result = network.run()
    assert not result["requests"][0]["completed"]
    assert not any(e["action"] == "payload_measured" for e in result["events"])
    assert result["summary"]["resource_leaks"] == 0


def test_pair_expiry_during_teleport_local_operation():
    config = ideal(memory_cutoff_s=.00006, teleport_s=.00002)
    network = Network(config, [Request(0, (0, 0), (0, 1), 0, .1)], 12, trace=True)
    network.streams.random = lambda *args: 0.0
    result = network.run()
    assert result["requests"][0]["terminal_reason"] == "pair_expired"
    assert result["requests"][0]["consumed_pairs"] == 0


@pytest.mark.parametrize("placement", ["free", "restored"])
def test_predictor_includes_gate_duration_dephasing(placement):
    config = replace(ideal(placement=placement), gate_s=.01, memory_t2_s=.001,
                     excitation_rate_hz=1e12, teleport_s=0)
    request = Request(0, (0, 0), (0, 1), 0, .1)
    network = Network(config, [request], 12)
    job = Job(request, [Operand("a", request.source, identity_channel(), 0),
                        Operand("b", request.destination, identity_channel(), 0)])
    _, predicted = network._estimate(job, request.destination)
    assert predicted < .251
