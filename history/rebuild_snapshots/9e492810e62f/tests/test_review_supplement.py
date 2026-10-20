"""Pairing, trace accounting, and raw integrity for the additive supplement."""

from dataclasses import replace
import importlib.util
from pathlib import Path

import pytest

from dequint.network import Network
from dequint.workload import make_workload, workload_hash


SPEC = importlib.util.spec_from_file_location("review_supplement", Path(__file__).resolve().parents[1] /
                                              "tools/run_review_supplement.py")
supplement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(supplement)


def test_design_and_matched_workloads():
    plan = supplement.design()
    assert len(plan) == 48
    assert len({p["run_id"] for p in plan}) == 48
    for seed in supplement.SEEDS:
        endpoints = []
        for load in supplement.LOADS:
            group = [p for p in plan if p["seed"] == seed and p["offered_rate_s"] == load]
            requests = [make_workload(4, 24, load, seed, p["config"]["deadline_s"]) for p in group]
            assert len(group) == 8
            assert len({workload_hash(rr) for rr in requests}) == 1
            endpoints.append([(r.source, r.destination) for r in requests[0]])
            assert all(r.deadline_s - r.arrival_s == pytest.approx(.005) for r in requests[0])
        assert endpoints[0] == endpoints[1]
    assert {p["config"]["memory_t2_s"] for p in plan} == {.01}
    assert {p["config"]["memory_cutoff_s"] for p in plan} == {.02}
    assert {p["config"]["placement"] for p in plan} == {"free"}


def saved_run(tmp_path, config):
    requests = make_workload(4, 24, 100_000, 701, config.deadline_s)
    result = Network(config, requests, 701, "test", trace=True).run()
    supplement.write_json(tmp_path / "requests.json", result["requests"])
    supplement.write_trace(tmp_path / "events.jsonl", result["events"])
    supplement.write_json(tmp_path / "summary.json", result["summary"])
    supplement.write_json(tmp_path / "audit.json", supplement.audit_trace(result["requests"], result["events"]))
    supplement.write_json(tmp_path / "raw_sha256.json", {name: supplement.sha(tmp_path / name)
                          for name in ("requests.json", "events.jsonl", "summary.json", "audit.json")})
    return result


@pytest.mark.parametrize("fabric", ["wired", "radio"])
def test_summary_counts_raw_sha_and_failed_pair_cost(tmp_path, fabric):
    # A separate accounting stress fixture, not a tuning change to the frozen design.
    cfg = replace(supplement.config(20_000, "hh", fabric), deadline_s=.0005)
    result = saved_run(tmp_path, cfg)
    summary, rows, audit = supplement.reconcile_run(tmp_path)
    assert summary["requests"] == len(rows) == 24
    assert sum(audit["terminal_outcomes_mutually_exclusive"].values()) == 24
    assert sum(audit["terminal_failure_reasons_exact"].values()) == 24 - summary["completed"]
    assert audit["payload_pairs_consumed_failed_requests"] == sum(r["consumed_pairs"] for r in rows if not r["completed"])
    assert audit["payload_pairs_consumed_failed_requests"] > 0
    assert audit["stages_overlapping"]["terminal"]["events"] == 24
    assert len(result["events"]) > 24
    with (tmp_path / "requests.json").open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="Raw SHA mismatch"):
        supplement.reconcile_run(tmp_path)


def test_summary_tamper_detected_even_with_rehashed_summary(tmp_path):
    saved_run(tmp_path, supplement.config(2_000_000, "midpoint", "wired"))
    summary = supplement.read_json(tmp_path / "summary.json")
    summary["completed"] += 1
    # Deliberately replace only temporary test artifacts, not actual batch files.
    (tmp_path / "summary.json").unlink()
    supplement.write_json(tmp_path / "summary.json", summary)
    hashes = supplement.read_json(tmp_path / "raw_sha256.json")
    hashes["summary.json"] = supplement.sha(tmp_path / "summary.json")
    (tmp_path / "raw_sha256.json").unlink()
    supplement.write_json(tmp_path / "raw_sha256.json", hashes)
    with pytest.raises(AssertionError):
        supplement.reconcile_run(tmp_path)


def test_exclusive_writes_and_missing_latency(tmp_path):
    supplement.write_json(tmp_path / "one.json", {"null": None})
    with pytest.raises(FileExistsError):
        supplement.write_json(tmp_path / "one.json", {})
    assert supplement.paired_interval([None, None, None]) == {"n_seeds": 0, "mean": None, "ci95": None}
    assert supplement.paired_interval([0, 0, 0])["ci95"] == [0, 0]


def test_unobserved_stages_not_invented():
    cfg = replace(supplement.config(20_000, "hh", "wired"), source_outage_probability=1, max_attempts=1)
    result = Network(cfg, make_workload(4, 24, 1000, 701, .005), 701, trace=True).run()
    audit = supplement.audit_trace(result["requests"], result["events"])
    assert audit["stages_overlapping"]["payload_bell_measurement"]["events"] == 0
    assert audit["stages_overlapping"]["purification_decision"]["events"] == 0
    assert audit["terminal_outcomes_mutually_exclusive"] == {"failed:epr_attempt_bound": 24}


def test_source_inventory_recursive_and_drift(tmp_path):
    for name in (supplement.PROTOCOL, supplement.HARNESS, supplement.TESTS,
                 "pyproject.toml", "requirements-lock-windows-py312.txt", "src/dequint/nested/helper.py"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("source", encoding="utf-8")
    hashes = supplement.frozen_sources(tmp_path)
    assert "src/dequint/nested/helper.py" in hashes
    supplement.check_sources({"source_sha256": hashes}, tmp_path)
    (tmp_path / "src/dequint/nested/helper.py").write_text("drift", encoding="utf-8")
    with pytest.raises(RuntimeError, match="drift"):
        supplement.check_sources({"source_sha256": hashes}, tmp_path)
