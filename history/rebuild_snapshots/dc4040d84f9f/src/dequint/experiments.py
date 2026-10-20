"""Reproducible finite-batch experiments; all offered requests remain inspectable."""

import argparse
from dataclasses import replace
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import time

import pandas as pd

from .config import ModelConfig
from .network import Network
from .workload import make_workload


def scenarios():
    base = ModelConfig()
    output = []
    for placement in ("free", "restored"):
        for rate in (1000, 10000):
            for policy in ("hh", "midpoint", "queue", "adaptive"):
                output.append((f"primary_{placement}_{rate}", rate,
                               replace(base, policy=policy, placement=placement)))
    for label, changes in {
        "radio": {"classical": "radio"},
        "short_memory": {"memory_t2_s": 3.3e-6, "profile": "short_T2_sensitivity"},
        "packet_loss": {"packet_loss": .1},
        "source_outage": {"source_outage_probability": 1},
        "purification": {"raw_bell_fidelity": .7, "purification_rounds": 1},
        "pool_1": {"pooled_servers": 1},
        "pool_4": {"pooled_servers": 4},
    }.items():
        for policy in ("hh", "midpoint", "adaptive"):
            output.append((label, 10000, replace(base, policy=policy, **changes)))
    for side in (2, 8, 16):
        for policy in ("hh", "midpoint", "adaptive"):
            output.append((f"scale_{side}", 625 * side**2,
                           replace(base, policy=policy, mesh_side=side)))
    return output


def source_hashes(root):
    paths = sorted((root / "src" / "dequint").glob("*.py"))
    paths += [root / "docs" / "EXPERIMENT_PROTOCOL.md", root / "pyproject.toml"]
    return {str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths if path.exists()}


def environment(root):
    packages = {}
    for name in ("sequence", "qiskit", "qiskit-aer", "numpy", "scipy", "pandas", "matplotlib", "pytest"):
        packages[name] = importlib.metadata.version(name)
    upstream = next((candidate for candidate in [root / "SeQUeNCe", root, *root.parents]
                     if (candidate / "sequence" / "kernel" / "timeline.py").exists()), None)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=upstream, text=True).strip() if upstream else None
    return {"python": platform.python_version(), "platform": platform.platform(),
            "packages": packages, "upstream_head": commit,
            "upstream_base": "88f92cca8aaa6dbf82bccc6a759465120afbdd34",
            "sources": source_hashes(root), "hardware_claim": False}


def run_batch(output_dir, seeds=range(101, 111), requests=48, only=None):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    env = environment(root)
    manifest_path = output / "environment.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text())["sources"] != env["sources"]:
        raise RuntimeError("Source drift: use a fresh result directory")
    manifest_path.write_text(json.dumps(env, indent=2), encoding="utf-8")
    selected = [item for item in scenarios() if only is None or item[0] in only]
    plan = {"seeds": list(seeds), "requests_per_seed": requests,
            "scenarios": [{"cell": label, "arrival_rate": rate, "config": config.to_dict()}
                          for label, rate, config in selected]}
    (output / "run_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    summaries = []
    start = time.perf_counter()
    for label, rate, config in selected:
        for seed in seeds:
            run_id = f"{label}_{config.policy}_s{seed}"
            directory = output / "runs" / run_id
            directory.mkdir(parents=True, exist_ok=True)
            result_file = directory / "summary.json"
            workload = make_workload(config.mesh_side, requests, rate, seed, config.deadline_s)
            if result_file.exists():
                summary = json.loads(result_file.read_text())
                if summary["config"] != config.to_dict() or summary["requests"] != requests:
                    raise RuntimeError("Conflicting existing run")
            else:
                result = Network(config, workload, seed, run_id, trace=seed == min(seeds)).run()
                summary = result["summary"]
                summary.update(cell=label, arrival_rate=rate)
                pd.DataFrame(result["requests"]).to_csv(directory / "requests.csv", index=False)
                (directory / "workload.json").write_text(json.dumps([r.to_dict() for r in workload], indent=2), encoding="utf-8")
                if result["events"]:
                    (directory / "events.jsonl").write_text("\n".join(json.dumps(e) for e in result["events"]), encoding="utf-8")
                result_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            summaries.append(summary)
        print(f"Completed {label}/{config.policy}; {len(summaries)} runs; {time.perf_counter()-start:.1f}s", flush=True)
    flat = [{**{k: v for k, v in s.items() if k != "config"}, **{f"config_{k}": v for k, v in s["config"].items()}}
            for s in summaries]
    pd.DataFrame(flat).to_csv(output / "summary.csv", index=False)
    receipt = {"runs": len(summaries), "requests": sum(s["requests"] for s in summaries),
               "elapsed_wall_s": time.perf_counter() - start, "resource_leaks": sum(s["resource_leaks"] for s in summaries),
               "summary_sha256": hashlib.sha256((output / "summary.csv").read_bytes()).hexdigest()}
    (output / "batch_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--requests", type=int, default=48)
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args()
    print(json.dumps(run_batch(args.output, range(101, 101 + args.seeds), args.requests, args.only), indent=2))


if __name__ == "__main__":
    main()
