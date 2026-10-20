"""Separately frozen native-mesh, application-timing and matched-control study."""

import argparse
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
import pandas as pd
from scipy.stats import t

from .application_replay import ApplicationReplay, build_circuit
from .config import ModelConfig
from .experiments import environment
from .native_mesh import run_native_mesh
from .network import Network
from .workload import make_workload, Request


SEEDS = tuple(range(201, 205))
POLICIES = ("hh", "midpoint", "queue", "adaptive")


def _safe(value):
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        raise ValueError("Undefined NaN is not valid evidence; use null explicitly")
    return value


def _json(path, value):
    path.write_text(json.dumps(_safe(value), indent=2, allow_nan=False), encoding="utf-8")


def native_cases():
    base = replace(ModelConfig(), emission_efficiency=1, detector_efficiency=1,
                   attenuation_db_per_m=0, raw_bell_fidelity=1, memory_t2_s=math.inf,
                   teleport_pauli_error=0, gate_pauli_error=0)
    for side in (2, 4):
        for placement in ("free", "restored"):
            for policy in POLICIES:
                yield f"native_ideal_{side}_{placement}", replace(base, mesh_side=side, policy=policy, placement=placement), "corner"
    for policy in POLICIES:
        yield "native_concurrent_4", replace(base, policy=policy, communication_memories=2), "concurrent"
    for placement in ("free", "restored"):
        for policy in POLICIES:
            yield f"native_noisy_4_{placement}", replace(ModelConfig(), policy=policy, placement=placement), "corner"
    for label, changes in {
        "native_detector_outage": {"detector_efficiency": 0, "max_attempts": 3},
        "native_short_cutoff": {"memory_cutoff_s": 1e-12},
        "native_correction_loss": {"packet_loss": 1, "max_attempts": 2},
    }.items():
        yield label, replace(base, mesh_side=2, **changes), "adjacent"


def control_cases():
    base = ModelConfig()
    for policy in ("hh", "midpoint", "adaptive"):
        for pool in (0, 24):
            yield f"equal_capacity_{pool}", replace(base, policy=policy, pooled_servers=pool)
        for rounds in (0, 1):
            yield f"matched_purification_{rounds}", replace(base, policy=policy, raw_bell_fidelity=.7,
                                                           purification_rounds=rounds)


def _native_requests(config, kind):
    if kind == "concurrent":
        return [Request(i, (0, i % 2), (3, 3-i % 2), 0, .02) for i in range(4)]
    destination = (0, 1) if kind == "adjacent" else (config.mesh_side-1, config.mesh_side-1)
    return [Request(0, (0, 0), destination, 0, .02)]


def run_followup(output_dir, groups=("native", "applications", "controls")):
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise RuntimeError("Preserve previous follow-up evidence; select a fresh output directory")
    output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    env = environment(root)
    protocol = root / "docs/FOLLOWUP_PROTOCOL.md"
    env["followup_protocol_sha256"] = hashlib.sha256(protocol.read_bytes()).hexdigest()
    path = output / "environment.json"
    if path.exists():
        previous = json.loads(path.read_text())
        if previous["sources"] != env["sources"] or previous["followup_protocol_sha256"] != env["followup_protocol_sha256"]:
            raise RuntimeError("Follow-up source/protocol drift; use a fresh output directory")
    _json(path, env)
    _json(output / "plan.json", {"protocol": "EXP-NATIVE-APP-01", "seeds": SEEDS, "groups": groups,
        "native_cases": [{"cell": cell, "config": config.to_dict(), "kind": kind}
                         for cell, config, kind in native_cases()],
        "application_circuits": [["ghz", 6], ["qft", 6], ["cdkm", 2], ["quantum_volume", 4]],
        "application_placements": ["free", "restored"], "policies": POLICIES,
        "controls": [{"cell": cell, "config": config.to_dict()} for cell, config in control_cases()]})
    rows, started = [], time.perf_counter()

    def record(group, cell, policy, seed, result):
        directory = output / "runs" / f"{cell}_{policy}_s{seed}"
        directory.mkdir(parents=True, exist_ok=True)
        _json(directory / "result.json", result)
        summary = dict(result["summary"], group=group, cell=cell, policy=policy, seed=seed)
        if group == "application":
            summary["application_completed"] = bool(summary["completed"])
            summary["completed"] = int(summary["completed"])
            summary["requests"] = 1
        if "config" in summary:
            config = summary.pop("config")
            summary.update({f"config_{key}": value for key, value in config.items()})
        _json(directory / "summary.json", summary)
        rows.append(summary)

    if "native" in groups:
        for cell, config, kind in native_cases():
            for seed in SEEDS:
                result = run_native_mesh(config, _native_requests(config, kind), seed,
                                         run_id=f"{cell}_{config.policy}_s{seed}", trace=True,
                                         data_slots_per_core=4 if kind == "concurrent" else 8)
                record("native", cell, config.policy, seed, result)
            print(f"Native {cell}/{config.policy}: {len(rows)} runs", flush=True)
    if "applications" in groups:
        for name, size in (("ghz", 6), ("qft", 6), ("cdkm", 2), ("quantum_volume", 4)):
            for placement in ("free", "restored"):
                for policy in POLICIES:
                    for seed in SEEDS:
                        circuit = build_circuit(name, size, seed)
                        rng = np.random.default_rng(np.random.SeedSequence([seed, 314159]))
                        sites = rng.choice(16, size=circuit.num_qubits, replace=False)
                        mapping = [divmod(int(site), 4) for site in sites]
                        result = ApplicationReplay(replace(ModelConfig(), policy=policy, placement=placement),
                                                   circuit, mapping, seed, deadline_s=.2).run()
                        record("application", f"app_{name}_{size}_{placement}", policy, seed, result)
                    print(f"Application {name}/{placement}/{policy}: {len(rows)} runs", flush=True)
    if "controls" in groups:
        for cell, config in control_cases():
            for seed in SEEDS:
                requests = make_workload(4, 48, 10000, seed, config.deadline_s)
                result = Network(config, requests, seed, f"{cell}_{config.policy}_s{seed}", trace=seed == SEEDS[0]).run()
                record("control", cell, config.policy, seed, result)
            print(f"Control {cell}/{config.policy}: {len(rows)} runs", flush=True)
    pd.DataFrame(rows).to_csv(output / "summary.csv", index=False)
    receipt = {"runs": len(rows), "groups": groups, "elapsed_wall_s": time.perf_counter()-started,
               "summary_sha256": hashlib.sha256((output / "summary.csv").read_bytes()).hexdigest(),
               "resource_leaks": sum(row["resource_leaks"] for row in rows),
               "native_gates_offered": sum(row.get("requests", 0) for row in rows if row["group"] == "native"),
               "applications_offered": sum(row["group"] == "application" for row in rows),
               "control_gates_offered": sum(row.get("requests", 0) for row in rows if row["group"] == "control")}
    _json(output / "receipt.json", receipt)
    return receipt


def analyze_followup(output_dir):
    output = Path(output_dir)
    data = pd.read_csv(output / "summary.csv")
    for (cell, seed), rows in data.groupby(["cell", "seed"]):
        column = "application_input_sha256" if rows.group.iloc[0] == "application" else "workload_sha256"
        if rows[column].nunique() != 1:
            raise RuntimeError(f"Unpaired follow-up cell: {cell}/{seed}")
    records = []
    for (group, cell, policy), rows in data.groupby(["group", "cell", "policy"]):
        metric = "completed_application_makespan_s" if group == "application" else "mean_completed_latency_s"
        values = rows[metric].dropna().to_numpy(float)
        mean = float(values.mean()) if len(values) else None
        half = float(t.ppf(.975, len(values)-1)*values.std(ddof=1)/np.sqrt(len(values))) if len(values) > 1 else None
        if group == "application":
            completion = float(rows.completed.mean())
            quality = None
        else:
            completion = float((rows.completed/rows.requests).mean())
            quality = float((rows.quality_qualified/rows.requests).mean())
        records.append({"group": group, "cell": cell, "policy": policy, "seeds": len(rows),
                        "mean_completion_fraction": completion, "mean_quality_fraction": quality,
                        "latency_metric": metric, "usable_latency_seeds": len(values),
                        "latency_mean_s": mean, "latency_lo95_s": mean-half if half is not None else None,
                        "latency_hi95_s": mean+half if half is not None else None,
                        "mean_process_fidelity": float(rows.mean_completed_process_fidelity.dropna().mean())
                            if group != "application" and rows.mean_completed_process_fidelity.notna().any() else None})
    pd.DataFrame(records).to_csv(output / "aggregate.csv", index=False)
    # Controls must be compared at the same capacity/raw fidelity, not to batch_v2 stress profiles.
    paired = []
    for policy in ("hh", "midpoint", "adaptive"):
        for name, first_cell, second_cell in (("pool24-minus-perlink24", "equal_capacity_24", "equal_capacity_0"),
                                               ("purify1-minus-purify0", "matched_purification_1", "matched_purification_0")):
            first = data[(data.cell == first_cell) & (data.policy == policy)].set_index("seed")
            second = data[(data.cell == second_cell) & (data.policy == policy)].set_index("seed")
            common = first.index.intersection(second.index)
            if not len(common):
                continue
            for metric in ("mean_completed_latency_s", "mean_completed_process_fidelity", "raw_pair_rate_s"):
                delta = (first.loc[common, metric]-second.loc[common, metric]).dropna().to_numpy(float)
                mean = float(delta.mean()) if len(delta) else None
                half = float(t.ppf(.975,len(delta)-1)*delta.std(ddof=1)/np.sqrt(len(delta))) if len(delta)>1 else None
                paired.append({"comparison": name, "policy": policy, "metric": metric, "seed_pairs": len(delta),
                               "mean_difference": mean, "lo95": mean-half if half is not None else None,
                               "hi95": mean+half if half is not None else None})
    pd.DataFrame(paired).to_csv(output / "paired_controls.csv", index=False)
    return {"groups": sorted(data.group.unique().tolist()), "runs": len(data), "pairing": "passed"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--groups", nargs="+", choices=["native", "applications", "controls"],
                        default=["native", "applications", "controls"])
    args = parser.parse_args()
    print(json.dumps(run_followup(args.output, args.groups), indent=2))
    print(json.dumps(analyze_followup(args.output), indent=2))
