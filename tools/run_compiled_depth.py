"""Run CD-01 locally; output is restricted to results/compiled_depth_v1."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import statistics
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qiskit import qasm3  # noqa: E402
from dequint.compiled_depth import (  # noqa: E402
    BASIS, SEEDS, build_teleport, cases, compile_teleport, hop_branch_check,
    resources, schedule, swap_control, verify_channel,
)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def source_hashes():
    paths = ["docs/COMPILED_DEPTH_PROTOCOL.md", "src/dequint/compiled_depth.py",
             "tests/test_compiled_depth.py", "tools/run_compiled_depth.py",
             "src/dequint/application_replay.py", "src/dequint/native_mesh.py",
             "src/dequint/followup.py", "src/dequint/network.py", "src/dequint/routing.py",
             "src/dequint/config.py", "docs/FOLLOWUP_PROTOCOL.md", "pyproject.toml",
             "requirements-lock-windows-py312.txt", "results/followup_v1/plan.json"]
    return {name: digest(ROOT / name) for name in paths}


def run(run_name):
    if not run_name or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                           for char in run_name):
        raise ValueError("run name must be a simple alphanumeric/underscore/hyphen identifier")
    base = (ROOT / "results/compiled_depth_v1").resolve()
    output = (base / run_name).resolve()
    if output.parent != base:
        raise ValueError("output escaped owned result root")
    if output.exists() and any(output.iterdir()):
        raise RuntimeError("refusing to overwrite nonempty experiment evidence")
    output.mkdir(parents=True, exist_ok=True)
    before = source_hashes()
    started = time.perf_counter()
    graphs = list(cases())
    environment = {"protocol": "CD-01", "start_utc": now(), "executable": sys.executable,
        "python": sys.version, "platform": platform.platform(), "sources_before": before,
        "packages": {name: version(name) for name in ("qiskit", "qiskit-aer", "numpy", "pytest")},
        "basis": BASIS, "optimization_level": 0, "seeds_sabre": SEEDS,
        "cases": [{"name": g.name, "nodes": g.nodes, "core_links": g.links,
                   "physical_edges_directed": g.edges, "home_data_qubits": g.homes,
                   "physical_qubits": g.num_qubits} for g in graphs],
        "physical_qpu": False, "paid_cloud": False, "shots": 0,
        "evidence_class": "local exact-numerical ideal deterministic gate-link skeleton",
        "independent_external_review": "not performed; mathematical and mutation-test cross-checks only"}
    # This declaration is persisted before any experiment circuit is compiled.
    save_json(output / "pre_run.json", environment)
    (output / "protocol_snapshot.md").write_bytes((ROOT / "docs/COMPILED_DEPTH_PROTOCOL.md").read_bytes())
    hop = hop_branch_check()
    save_json(output / "single_hop_instrument.json", hop)
    if not hop["passed"]:
        raise RuntimeError("single-hop instrument failed")
    rows = []
    for graph in graphs:
        requests = [(policy, None) for policy in ("endpoint", "rendezvous")]
        requests.extend(("sabre_swap", seed) for seed in SEEDS)
        for policy, seed in requests:
            case_start = time.perf_counter()
            label = f"{graph.name}_{policy}" + (f"_s{seed}" if seed is not None else "")
            directory = output / label
            directory.mkdir()
            if policy == "sabre_swap":
                compiled, raw, metadata = swap_control(graph, seed)
            else:
                raw, metadata = build_teleport(graph, policy)
                compiled = compile_teleport(graph, raw)
            (directory / "source.qasm").write_text(qasm3.dumps(raw), encoding="utf-8")
            (directory / "compiled.qasm").write_text(qasm3.dumps(compiled), encoding="utf-8")
            check = verify_channel(compiled, graph.homes)
            save_json(directory / "channel.json", check)
            save_json(directory / "metadata.json", metadata)
            row = {"case": label, "graph": graph.name, "policy": policy,
                   "seed": seed, **resources(compiled)}
            for core_serial in (False, True):
                for metric in ("quantum", "instrument", "cx"):
                    result = schedule(compiled, core_serial=core_serial, metric=metric)
                    key = f"{metric}_{'core' if core_serial else 'qubit'}"
                    row[f"depth_{key}"] = result["depth"]
                    save_json(directory / f"schedule_{key}.json", result)
            row.update({key: metadata.get(key, 0) for key in (
                "hops", "bell_pairs", "bsm", "correction_bits", "storage_cx",
                "out_hops", "return_hops", "routing_swaps", "return_swaps")})
            row.update({key: check[key] for key in (
                "passed", "max_choi_error", "trace", "process_fidelity",
                "work_qubit_one_probability_sum", "max_active_qubits_including_references")})
            row["wall_s"] = time.perf_counter() - case_start
            save_json(directory / "result.json", row)
            rows.append(row)
            print(f"{label}: depth={row['depth_quantum_qubit']} core={row['depth_quantum_core']} "
                  f"CX={row['cx_count']} Choi error={check['max_choi_error']:.3g}", flush=True)
            if not check["passed"]:
                save_json(output / "FAILED.json", {"failed_case": label, "completed_rows": rows})
                raise RuntimeError(f"channel or work-qubit restoration failed: {label}")
    with (output / "resource_ledger.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    aggregate = []
    for graph in graphs:
        for policy in ("endpoint", "rendezvous", "sabre_swap"):
            subset = [r for r in rows if r["graph"] == graph.name and r["policy"] == policy]
            entry = {"graph": graph.name, "policy": policy, "runs": len(subset)}
            for metric in ("depth_quantum_qubit", "depth_quantum_core", "depth_instrument_qubit",
                           "depth_instrument_core", "cx_count"):
                values = [r[metric] for r in subset]
                entry[metric] = {"min": min(values), "median": statistics.median(values), "max": max(values)}
            aggregate.append(entry)
    save_json(output / "aggregate.json", aggregate)
    after = source_hashes()
    drift = [name for name in before if before[name] != after[name]]
    receipt = {"protocol": "CD-01", "start_utc": environment["start_utc"], "end_utc": now(),
        "wall_s": time.perf_counter() - started, "circuits": len(rows),
        "all_channels_passed": all(r["passed"] for r in rows), "source_drift": drift,
        "sources_after": after, "max_choi_error": max(r["max_choi_error"] for r in rows),
        "read_only_source_integrity": not drift, "accepted_records_modified_by_runner": False}
    save_json(output / "receipt.json", receipt)
    lines = ["# CD-01 Results", "", "Local exact-numerical ideal gate-link evidence only.", "",
             "Quantum depths reserve both conditional correction slots. All states return home.", "",
             "| Graph | Method | Quantum depth (qubit) | Quantum depth (core) | Instrument depth (qubit) | CX |",
             "|---|---|---:|---:|---:|---:|"]
    for entry in aggregate:
        def span(key):
            value = entry[key]
            return str(value["min"]) if value["min"] == value["max"] else f"{value['min']}-{value['max']}"
        lines.append(f"| {entry['graph']} | {entry['policy']} | {span('depth_quantum_qubit')} | "
                     f"{span('depth_quantum_core')} | {span('depth_instrument_qubit')} | {span('cx_count')} |")
    lines.extend(["", "## Interpretation", "",
        "Same-task differences are conditional on graph, compilation and resource model. "
        "All negative results, ties and four SABRE seeds are retained. Seed ranges are compiler "
        "sensitivity, not confidence intervals or optimality proofs.", "",
        "Bell resources use counted deterministic H+CX surrogates. They are not a model of "
        "Barrett-Kok photons, detector success, heralding, retry, optical latency, classical packet "
        "delivery or QEC. Their network costs are unknown. Classical measurement dependencies "
        "are enforced, but no feedback duration is assigned. Instrument layers give resets and "
        "measurements one abstract layer, not calibrated duration.", "",
        "This experiment is one restored remote CNOT, not GHZ/QFT/CDKM/QV application execution, "
        "and does not test adaptive queue-aware rendezvous. Two data slots/core and one comm "
        "qubit/core are this study's fixed resources, not the native follow-up memory configuration.", "",
        "Permissible paper wording: We compiled ideal deterministic gate-link implementations "
        "of a restored remote CNOT on the specified small graphs, including explicit Bell-resource "
        "preparation, BSM, conditional corrections, storage SWAPs and state return. We report "
        "basis-gate and primitive-instrument dependency depths under declared concurrency rules "
        "and a separately identified nearest-neighbour SABRE SWAP control. These results do not "
        "establish photonic-network, QEC, hardware or full-application depth reduction.", "",
        f"All {len(rows)} compiled circuits passed reference-entangled Choi and work-qubit cleanup "
        f"checks; maximum elementwise Choi residual {receipt['max_choi_error']:.6g}.", "",
        "Independent mathematical checks: exhaustive four-outcome single-hop Kraus completeness; "
        "full physical-unitary comparison for line3 SABRE controls in tests; missing-correction "
        "and missing-return mutation tests. No independent external reviewer has approved promotion.", "",
        "See protocol_snapshot.md, pre_run.json, receipt.json, resource_ledger.csv, per-circuit "
        "QASM/channel/schedule JSON and aggregate.json for reproducible evidence.", ""])
    (output / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    manifest = {str(path.relative_to(output)).replace("\\", "/"): digest(path)
                for path in sorted(output.rglob("*")) if path.is_file()}
    save_json(output / "manifest.json", manifest)
    if drift:
        raise RuntimeError(f"source drift during run: {drift}")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.run_name), indent=2))
