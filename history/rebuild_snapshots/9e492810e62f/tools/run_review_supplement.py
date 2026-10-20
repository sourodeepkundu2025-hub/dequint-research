"""Frozen, bounded matched supplement using the existing Network unchanged."""

import argparse
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import statistics
import sys

from scipy.stats import t

from dequint.config import ModelConfig
from dequint.network import Network
from dequint.workload import make_workload, workload_hash


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results/review_supplement_v1"
SEEDS = (701, 702, 703)
REQUESTS = 24
EXCITATIONS = (20_000, 2_000_000)
LOADS = (1_000, 100_000)
POLICIES = ("hh", "midpoint")
FABRICS = ("wired", "radio")
PROTOCOL = "docs/REVIEW_SUPPLEMENT_PROTOCOL.md"
HARNESS = "tools/run_review_supplement.py"
TESTS = "tests/test_review_supplement.py"

# These are overlapping request observations, not a latency partition.
STAGES = {
    "arrival": ("request_arrived",),
    "route_selection": ("route_decision",),
    "resource_admission": ("resource_admission",),
    "epr_attempt_completed": ("complete_epr_attempt",),
    "pair_available": ("pair_ready",),
    "purification_decision": ("purification",),
    "payload_bell_measurement": ("payload_measured",),
    "correction_confirmed": ("pauli_frame_confirmed",),
    "local_gate_attempt": ("two_qubit_gate",),
    "terminal": ("request_terminal",),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_trace(path, events):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        for event in events:
            stream.write(json.dumps(event, sort_keys=True, allow_nan=False) + "\n")


def read_trace(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def config(excitation, policy, fabric):
    return replace(ModelConfig(), policy=policy, classical=fabric,
                   placement="free", excitation_rate_hz=excitation,
                   deadline_s=.005, memory_t2_s=.01, memory_cutoff_s=.02,
                   profile="prospective_reviewer_supplement_v1",
                   max_attempts=1000, max_events=500_000)


def design():
    runs = []
    for excitation in EXCITATIONS:
        for load in LOADS:
            for policy in POLICIES:
                for fabric in FABRICS:
                    for seed in SEEDS:
                        runs.append({"run_id": f"e{excitation}_l{load}_{policy}_{fabric}_s{seed}",
                                     "excitation_hz": excitation, "offered_rate_s": load,
                                     "policy": policy, "fabric": fabric, "seed": seed,
                                     "config": config(excitation, policy, fabric).to_dict()})
    return runs


def frozen_sources(root=ROOT):
    paths = [p for p in (root / "src").rglob("*") if p.is_file()
             and "__pycache__" not in p.parts and p.suffix != ".pyc"]
    paths += [root / name for name in (PROTOCOL, HARNESS, TESTS, "pyproject.toml",
                                      "requirements-lock-windows-py312.txt")]
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(paths)}


def protected_results(root=ROOT):
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted((root / "results").rglob("*"))
            if p.is_file() and "review_supplement_v1" not in p.relative_to(root / "results").parts}


def check_sources(freeze, root=ROOT):
    if frozen_sources(root) != freeze["source_sha256"]:
        raise RuntimeError("Frozen source/protocol/harness drift; no further runs permitted")


def freeze_batch(output=OUTPUT):
    output = Path(output)
    if (output / "freeze.json").exists() or (output / "runs").exists():
        raise FileExistsError("Refusing to replace an existing frozen supplement")
    output.mkdir(parents=True, exist_ok=True)
    sources = frozen_sources()
    plan = design()
    workloads = {}
    for load in LOADS:
        for seed in SEEDS:
            requests = make_workload(4, REQUESTS, load, seed, .005)
            relative = f"workloads/l{load}_s{seed}.json"
            write_json(output / relative, [r.to_dict() for r in requests])
            workloads[f"{load}:{seed}"] = {"path": relative, "raw_sha256": sha(output / relative),
                                           "workload_sha256": workload_hash(requests)}
    write_json(output / "run_plan.json", plan)
    # The freeze is committed to disk before Network is constructed for any run.
    record = {"frozen_at_utc": utc(), "source_sha256": sources,
              "source_exclusions": ["__pycache__", "*.pyc"],
              "protocol_sha256": sha(ROOT / PROTOCOL), "plan_sha256": sha(output / "run_plan.json"),
              "protected_result_sha256": protected_results(), "workloads": workloads,
              "python": sys.version, "executable": sys.executable, "platform": platform.platform(),
              "packages": {name: importlib.metadata.version(name)
                           for name in ("sequence", "numpy", "scipy", "pytest")},
              "physical_measurement": False, "runs": len(plan), "requests_per_run": REQUESTS,
              "trace_all_runs": True}
    write_json(output / "freeze.json", record)
    print(f"Frozen {len(plan)} runs / {len(plan) * REQUESTS} offered requests", flush=True)
    return record


def outcome(row):
    if row["completed"]:
        return "completed_qualified" if row["quality_qualified"] else "completed_unqualified"
    return "failed:" + (row["terminal_reason"] or "unclassified_recorded_reason")


def audit_trace(rows, events):
    counts = Counter(e["action"] for e in events)
    by_request = defaultdict(list)
    for event in events:
        by_request[str(event["request_id"])].append(event)
    stages = {}
    for name, actions in STAGES.items():
        observed = [e for e in events if e["action"] in actions]
        stages[name] = {"actions": list(actions), "events": len(observed),
                        "requests_observed": len({str(e["request_id"]) for e in observed})}
    categories = Counter(outcome(row) for row in rows)
    raw_reasons = Counter(row["terminal_reason"] for row in rows if not row["completed"])
    consumption = Counter(e["reason"] for e in events if e["action"] == "pair_consumed")
    payload_failed = 0
    all_consumed_failed = 0
    for row in rows:
        observed = by_request[str(row["request_id"])]
        terminals = [e for e in observed if e["action"] == "request_terminal"]
        assert len(terminals) == 1, "Each recorded row must have exactly one terminal event"
        terminal = terminals[0]
        assert terminal["completed"] == row["completed"]
        assert terminal["quality_qualified"] == row["quality_qualified"]
        if not row["completed"]:
            assert terminal["reason"] == row["terminal_reason"]
        consumed = [e for e in observed if e["action"] == "pair_consumed"]
        payload = sum(e["reason"] == "payload_bell_measurement" for e in consumed)
        assert payload == row["consumed_pairs"] == row["quantum_hops"]
        assert payload == sum(e["action"] == "payload_measured" for e in observed)
        assert row["raw_pairs"] == sum(e["action"] == "complete_epr_attempt" and e["accepted"] for e in observed)
        assert row["epr_attempts"] >= sum(e["action"] == "complete_epr_attempt" for e in observed)
        if not row["completed"]:
            payload_failed += payload
            all_consumed_failed += len(consumed)
    assert sum(categories.values()) == len(rows)
    tags = Counter(f"{e['action']}:{e['tag'].split(':')[0]}" for e in events
                   if e["action"] in ("classical_wired", "classical_radio"))
    admissions = Counter(f"{e['resource'].split(':')[0]}:{'admitted' if e['admitted'] else 'denied'}"
                         for e in events if e["action"] == "resource_admission")
    completed_attempts = counts["complete_epr_attempt"]
    return {"action_counts": dict(counts), "stages_overlapping": stages,
            "terminal_outcomes_mutually_exclusive": dict(categories),
            "terminal_failure_reasons_exact": dict(raw_reasons),
            "pair_consumed_by_reason": dict(consumption),
            "payload_pairs_consumed_failed_requests": payload_failed,
            "all_pairs_consumed_failed_requests": all_consumed_failed,
            "classical_action_tag_counts": dict(tags), "resource_admission_counts": dict(admissions),
            "completed_epr_attempts": completed_attempts,
            "started_not_completed_epr_attempts": sum(r["epr_attempts"] for r in rows) - completed_attempts,
            "local_gate_events_completed": sum(e["action"] == "two_qubit_gate" and e["completed"] for e in events),
            "radio_service_outcomes_completed": sum(e["action"] == "classical_radio" and e["completed"] for e in events),
            "radio_service_outcomes_incomplete": sum(e["action"] == "classical_radio" and not e["completed"] for e in events)}


def run_batch(output=OUTPUT):
    output = Path(output)
    freeze = read_json(output / "freeze.json")
    assert sha(output / "run_plan.json") == freeze["plan_sha256"]
    check_sources(freeze)
    if (output / "runs").exists():
        raise FileExistsError("No automatic reruns/resume: existing raw runs are immutable")
    (output / "runs").mkdir()
    for index, item in enumerate(read_json(output / "run_plan.json"), 1):
        check_sources(freeze)
        directory = output / "runs" / item["run_id"]
        directory.mkdir()
        requests = make_workload(4, REQUESTS, item["offered_rate_s"], item["seed"], .005)
        saved = freeze["workloads"][f"{item['offered_rate_s']}:{item['seed']}"]
        assert sha(output / saved["path"]) == saved["raw_sha256"]
        assert workload_hash(requests) == saved["workload_sha256"]
        network = Network(ModelConfig(**item["config"]), requests, item["seed"], item["run_id"], trace=True)
        write_json(directory / "started.json", {"started_at_utc": utc(), "freeze_sha256": sha(output / "freeze.json")})
        try:
            result = network.run()
        except Exception as error:
            write_json(directory / "partial_requests.json", network.rows)
            write_trace(directory / "partial_events.jsonl", network.events)
            write_json(directory / "run_error.json", {"type": type(error).__name__, "message": str(error),
                       "offered": REQUESTS, "terminal_rows": len(network.rows),
                       "administratively_censored_without_terminal": REQUESTS - len(network.rows),
                       "note": "No synthetic terminal events or inferred failure causes; batch stopped."})
            raise
        audit = audit_trace(result["requests"], result["events"])
        write_json(directory / "requests.json", result["requests"])
        write_trace(directory / "events.jsonl", result["events"])
        write_json(directory / "summary.json", {**result["summary"], "design": item})
        write_json(directory / "audit.json", audit)
        write_json(directory / "raw_sha256.json", {name: sha(directory / name)
                   for name in ("requests.json", "events.jsonl", "summary.json", "audit.json", "started.json")})
        print(f"{index}/48 {item['run_id']}: {result['summary']['completed']}/24 completed; "
              f"{result['summary']['quality_qualified']}/24 qualified", flush=True)
    check_sources(freeze)


def mean_or_null(values):
    return statistics.mean(values) if values else None


def paired_interval(values):
    values = [v for v in values if v is not None]
    if len(values) < 2:
        return {"n_seeds": len(values), "mean": mean_or_null(values), "ci95": None}
    mean = statistics.mean(values)
    half = float(t.ppf(.975, len(values) - 1)) * statistics.stdev(values) / len(values)**.5
    return {"n_seeds": len(values), "mean": mean, "ci95": [mean - half, mean + half]}


def reconcile_run(directory):
    directory = Path(directory)
    for name, expected in read_json(directory / "raw_sha256.json").items():
        if sha(directory / name) != expected:
            raise ValueError(f"Raw SHA mismatch: {directory.name}/{name}")
    rows = read_json(directory / "requests.json")
    summary = read_json(directory / "summary.json")
    events = read_trace(directory / "events.jsonl")
    audit = audit_trace(rows, events)
    assert audit == read_json(directory / "audit.json")
    assert len(rows) == summary["requests"] == REQUESTS
    assert len({r["request_id"] for r in rows}) == REQUESTS
    assert summary["completed"] == sum(r["completed"] for r in rows)
    assert summary["quality_qualified"] == sum(r["quality_qualified"] for r in rows)
    assert all(not r["quality_qualified"] or r["completed"] for r in rows)
    assert summary["attempts"] == sum(r["epr_attempts"] for r in rows)
    assert summary["consumed_pairs"] == sum(r["consumed_pairs"] for r in rows)
    cfg = summary["config"]
    assert all(r["finished_s"] <= r["deadline_s"] + 1e-11 for r in rows)
    assert all(r["quality_qualified"] == bool(r["completed"] and
               r["process_fidelity"] >= cfg["minimum_process_fidelity"]) for r in rows)
    completed = [r for r in rows if r["completed"]]
    expected_mean = mean_or_null([r["latency_s"] for r in completed])
    assert (summary["mean_completed_latency_s"] is None if expected_mean is None else
            math.isclose(summary["mean_completed_latency_s"], expected_mean, rel_tol=1e-12, abs_tol=1e-15))
    assert summary["resource_leaks"] == 0
    return summary, rows, audit


def verify_batch(output=OUTPUT):
    output = Path(output)
    freeze = read_json(output / "freeze.json")
    check_sources(freeze)
    assert sha(output / "run_plan.json") == freeze["plan_sha256"]
    for relative, expected in freeze["protected_result_sha256"].items():
        assert sha(ROOT / relative) == expected, f"Protected result drift: {relative}"
    plan = read_json(output / "run_plan.json")
    assert plan == design() and len(plan) == 48
    records = []
    for item in plan:
        summary, rows, audit = reconcile_run(output / "runs" / item["run_id"])
        started = read_json(output / "runs" / item["run_id"] / "started.json")
        assert started["freeze_sha256"] == sha(output / "freeze.json")
        assert started["started_at_utc"] >= freeze["frozen_at_utc"]
        assert summary["design"] == item and summary["config"] == item["config"]
        assert summary["seed"] == item["seed"] and summary["run_id"] == item["run_id"]
        saved = freeze["workloads"][f"{item['offered_rate_s']}:{item['seed']}"]
        assert sha(output / saved["path"]) == saved["raw_sha256"]
        expected_requests = read_json(output / saved["path"])
        for row, request in zip(rows, expected_requests):
            assert all(row[key] == request[key] for key in request)
        assert summary["workload_sha256"] == saved["workload_sha256"]
        records.append((summary, rows, audit))
    groups = defaultdict(list)
    for summary, _, _ in records:
        d = summary["design"]
        groups[(d["excitation_hz"], d["offered_rate_s"], d["policy"], d["seed"])].append(summary)
    for paired in groups.values():
        assert len(paired) == 2 and {s["config"]["classical"] for s in paired} == set(FABRICS)
        assert {k: v for k, v in paired[0]["config"].items() if k != "classical"} == {
            k: v for k, v in paired[1]["config"].items() if k != "classical"}
    return records


def aggregate(records):
    cells = defaultdict(list)
    for summary, rows, audit in records:
        d = summary["design"]
        cells[(d["excitation_hz"], d["offered_rate_s"], d["policy"], d["fabric"])].append((summary, rows, audit))
    table = []
    for key, group in sorted(cells.items()):
        rows = [r for _, rr, _ in group for r in rr]
        complete = [r for r in rows if r["completed"]]
        reasons = Counter(outcome(r) for r in rows)
        table.append({"excitation_hz": key[0], "offered_rate_s": key[1], "policy": key[2], "fabric": key[3],
                      "seeds": len(group), "offered": len(rows), "completed": len(complete),
                      "qualified": sum(r["quality_qualified"] for r in rows),
                      "failed": len(rows) - len(complete), "administratively_censored": 0,
                      "deadline_or_resource_deadline_failures": sum(not r["completed"] and
                          r["terminal_reason"] in ("deadline", "resource_deadline") for r in rows),
                      "mean_completed_latency_s": mean_or_null([r["latency_s"] for r in complete]),
                      "mean_completed_process_fidelity": mean_or_null([r["process_fidelity"] for r in complete]),
                      "epr_attempts": sum(r["epr_attempts"] for r in rows),
                      "complete_epr_attempt_events": sum(a["completed_epr_attempts"] for _, _, a in group),
                      "started_not_completed_epr_attempts": sum(a["started_not_completed_epr_attempts"] for _, _, a in group),
                      "accepted_raw_pairs": sum(r["raw_pairs"] for r in rows),
                      "payload_pairs_all_offered": sum(r["consumed_pairs"] for r in rows),
                      "payload_pairs_failed": sum(a["payload_pairs_consumed_failed_requests"] for _, _, a in group),
                      "all_pair_consumption_events": sum(sum(a["pair_consumed_by_reason"].values()) for _, _, a in group),
                      "all_pair_consumption_events_failed": sum(a["all_pairs_consumed_failed_requests"] for _, _, a in group),
                      "terminal_outcomes_mutually_exclusive": dict(reasons),
                      "quantum_resource_wait_sum_s": sum(s["quantum_queue_wait_s"] for s, _, _ in group),
                      "classical_wait_sum_s": sum(s["classical_wait_s"] for s, _, _ in group),
                      "native_events": sum(s["native_events"] for s, _, _ in group)})
    indexed = {(s["design"]["excitation_hz"], s["design"]["offered_rate_s"],
                s["design"]["policy"], s["design"]["fabric"], s["seed"]): (s, rows) for s, rows, _ in records}
    comparisons = []
    def compare(label, fixed, left_keys, right_keys):
        qualified, completed, latency, common_counts = [], [], [], []
        for left_key, right_key in zip(left_keys, right_keys):
            a, ar = indexed[left_key]
            b, br = indexed[right_key]
            assert a["workload_sha256"] == b["workload_sha256"]
            qualified.append((b["quality_qualified"] - a["quality_qualified"]) / REQUESTS)
            completed.append((b["completed"] - a["completed"]) / REQUESTS)
            common = [y["latency_s"] - x["latency_s"] for x, y in zip(ar, br)
                      if x["completed"] and y["completed"]]
            latency.append(mean_or_null(common))
            common_counts.append(len(common))
        comparisons.append({"comparison": label, **fixed, "direction": "right_minus_left",
                            "qualified_fraction_delta": paired_interval(qualified),
                            "completion_fraction_delta": paired_interval(completed),
                            "common_completed_latency_delta_s": paired_interval(latency),
                            "common_completed_requests_per_seed": common_counts,
                            "latency_selection": "Only requests completing on both arms; not all-offered latency."})
    for excitation in EXCITATIONS:
        for load in LOADS:
            for policy in POLICIES:
                compare("radio_minus_wired", {"excitation_hz": excitation, "offered_rate_s": load, "policy": policy},
                        [(excitation, load, policy, "wired", s) for s in SEEDS],
                        [(excitation, load, policy, "radio", s) for s in SEEDS])
            for fabric in FABRICS:
                compare("minimax_minus_hh", {"excitation_hz": excitation, "offered_rate_s": load, "fabric": fabric},
                        [(excitation, load, "hh", fabric, s) for s in SEEDS],
                        [(excitation, load, "midpoint", fabric, s) for s in SEEDS])
    for load in LOADS:
        for policy in POLICIES:
            for fabric in FABRICS:
                compare("2MHz_minus_20kHz", {"offered_rate_s": load, "policy": policy, "fabric": fabric},
                        [(20_000, load, policy, fabric, s) for s in SEEDS],
                        [(2_000_000, load, policy, fabric, s) for s in SEEDS])
    crossover = []
    for load in LOADS:
        for policy in POLICIES:
            contrasts = [next(c for c in comparisons if c["comparison"] == "radio_minus_wired"
                             and c["excitation_hz"] == excitation and c["offered_rate_s"] == load
                             and c["policy"] == policy)["common_completed_latency_delta_s"] for excitation in EXCITATIONS]
            means = [c["mean"] for c in contrasts]
            reversal = None if any(v is None for v in means) else means[0] * means[1] < 0
            excludes_zero = [c["ci95"] is not None and c["ci95"][0] * c["ci95"][1] > 0 for c in contrasts]
            crossover.append({"offered_rate_s": load, "policy": policy,
                              "excitation_hz_order": list(EXCITATIONS),
                              "radio_minus_wired_common_latency_means_s": means,
                              "descriptive_sign_reversal": reversal,
                              "both_exploratory_intervals_exclude_zero": all(excludes_zero),
                              "supported_reversal_in_these_cells": bool(reversal and all(excludes_zero)),
                              "physical_crossover_established": False})
    return {"cells": table, "paired_comparisons": comparisons, "crossover_assessment": crossover,
            "inference": "Descriptive paired seed Student-t 95% intervals; n=3, no multiplicity correction; not confirmatory."}


def analyze_batch(output=OUTPUT):
    output = Path(output)
    records = verify_batch(output)
    result = aggregate(records)
    write_json(output / "analysis.json", result)
    lines = ["# Reviewer 2/3 Supplement v1", "", "Prospective finite-batch model, not measured physical hardware.",
             "Same ordered CNOT, free placement, fixed memory/deadline contract; all 48 runs retained.", "",
             "| Excitation Hz | Offered /s | Policy | Fabric | Completed/offered | Qualified/offered | Payload pairs (failed) | Mean completed latency us |",
             "|---:|---:|---|---|---:|---:|---:|---:|"]
    for cell in result["cells"]:
        value = cell["mean_completed_latency_s"]
        latency = "null" if value is None else f"{value * 1e6:.3f}"
        lines.append(f"| {cell['excitation_hz']} | {cell['offered_rate_s']} | {cell['policy']} | {cell['fabric']} | "
                     f"{cell['completed']}/{cell['offered']} | {cell['qualified']}/{cell['offered']} | "
                     f"{cell['payload_pairs_all_offered']} ({cell['payload_pairs_failed']}) | {latency} |")
    lines += ["", "## Wired/radio contrasts", "", "Positive delta favors wired for latency, radio for fractions.",
              "Intervals are exploratory seed-level t intervals (3 seeds); no multiplicity correction.", "",
              "| Excitation Hz | Offered /s | Policy | Qualified delta | Completion delta | Common-completion latency delta us [95% CI] |",
              "|---:|---:|---|---:|---:|---|"]
    for comparison in result["paired_comparisons"]:
        if comparison["comparison"] != "radio_minus_wired":
            continue
        latency = comparison["common_completed_latency_delta_s"]
        rendered = "null" if latency["ci95"] is None else (
            f"{latency['mean'] * 1e6:.4f} [{latency['ci95'][0] * 1e6:.4f}, {latency['ci95'][1] * 1e6:.4f}]")
        lines.append(f"| {comparison['excitation_hz']} | {comparison['offered_rate_s']} | {comparison['policy']} | "
                     f"{comparison['qualified_fraction_delta']['mean']:.6f} | "
                     f"{comparison['completion_fraction_delta']['mean']:.6f} | {rendered} |")
    lines += ["", "Crossover screening at fixed load/policy:"]
    for assessment in result["crossover_assessment"]:
        lines.append(f"- {assessment['offered_rate_s']}/s, {assessment['policy']}: "
                     f"sign reversal={assessment['descriptive_sign_reversal']}; "
                     f"both exploratory intervals exclude zero={assessment['both_exploratory_intervals_exclude_zero']}; "
                     f"supported reversal in tested cells={assessment['supported_reversal_in_these_cells']}.")
    lines += ["", "## Interpretation Boundaries", "",
              "Generation-rate contrasts and minimax/HH contrasts, full failure reasons, pair accounting, and intervals are in analysis.json.",
              "Do not infer classical-service dominance from generation-rate sensitivity or treat a sign change alone as an established crossover.",
              "A wired/radio latency crossover requires a reversal of paired common-completion latency signs across excitation profiles; intervals spanning zero are inconclusive.",
              "The trace has no complete service-start/end partition. No nine-disjoint-stage timing, physical crossover threshold, steady-state capacity, or entanglement-witness runtime result is established.",
              "Terminal deadline failures remain in all-offered denominators; incomplete latency/fidelity is not imputed.",
              "Consumed payload pairs on failures are included. All pair_consumed events also include discarded resources and are reported separately.",
              "No manuscript edits are made. This report supports only the stated prospective parameter cells."]
    path = output / "REPORT.md"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines) + "\n")
    totals = {"runs": len(records), "offered": sum(s["requests"] for s, _, _ in records),
              "completed": sum(s["completed"] for s, _, _ in records),
              "qualified": sum(s["quality_qualified"] for s, _, _ in records),
              "failed": sum(s["requests"] - s["completed"] for s, _, _ in records),
              "administratively_censored": 0, "resource_leaks": 0,
              "freeze_sha256": sha(output / "freeze.json"),
              "analysis_sha256": sha(output / "analysis.json"), "report_sha256": sha(path),
              "verified_at_utc": utc(), "protected_results_unchanged": True,
              "independent_review": "Not supplied by this receipt; reconciliation is local deterministic verification."}
    write_json(output / "receipt.json", totals)
    return totals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "analyze", "verify"))
    args = parser.parse_args()
    if args.action == "freeze":
        freeze_batch()
    elif args.action == "run":
        run_batch()
    elif args.action == "analyze":
        print(json.dumps(analyze_batch(), indent=2))
    else:
        records = verify_batch()
        assert aggregate(records) == read_json(OUTPUT / "analysis.json")
        receipt = read_json(OUTPUT / "receipt.json")
        assert sha(OUTPUT / "analysis.json") == receipt["analysis_sha256"]
        assert sha(OUTPUT / "REPORT.md") == receipt["report_sha256"]
        assert sha(OUTPUT / "freeze.json") == receipt["freeze_sha256"]
        print(f"Verified {len(records)} runs, raw SHA, paired workloads, counts, analysis and protected results")


if __name__ == "__main__":
    main()
