"""Frozen, separately scoped topology/Pauli provisioning sensitivity study."""

from dataclasses import asdict, replace
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from scipy.stats import t

from dequint.shortcut_probe import (ProbeConfig, ShortcutProbe, build_topology,
                                    probe_workload, topology_cost)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results/shortcut_v1"
PROFILES = {
    "fixed_footprint_ideal_loss": dict(scaling="fixed_footprint", footprint_m=.01,
                                      attenuation_db_per_m=0, shortcut_insertion_loss_db=0),
    "fixed_footprint_lossy": dict(scaling="fixed_footprint", footprint_m=.01,
                                 attenuation_db_per_m=1000, shortcut_insertion_loss_db=3),
    "fixed_pitch_lossy": dict(scaling="fixed_pitch", pitch_m=.001,
                             attenuation_db_per_m=1000, shortcut_insertion_loss_db=3),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")


def run():
    if OUTPUT.exists():
        raise RuntimeError("Preserve the existing batch; use a separately frozen version")
    OUTPUT.mkdir(parents=True)
    plan = []
    for profile, fields in PROFILES.items():
        for side in (4, 8, 16):
            for placement in ("free", "restored"):
                for route in ("hops", "expected_time"):
                    for seed in range(301, 307):
                        for topology in ("mesh", "mesh_debruijn"):
                            config = ProbeConfig(side=side, placement=placement, route_metric=route,
                                                 topology=topology, generator_mode="global",
                                                 generator_capacity=16, ports_per_node=2,
                                                 max_attempts=100, **fields)
                            plan.append({"profile": profile, "seed": seed, "config": asdict(config),
                                         "requests": 32, "arrival_rate_s": 1000, "relative_deadline_s": .05,
                                         "quality_threshold": .9})
    sources = [ROOT / "src/dequint/shortcut_probe.py", ROOT / "tests/test_shortcut_probe.py",
               Path(__file__), ROOT / "docs/SHORTCUT_EXTENSION_PROTOCOL.md"]
    dump(OUTPUT / "plan.json", plan)
    dump(OUTPUT / "environment.json", {
        "python": sys.version, "platform": platform.platform(),
        "packages": {p: version(p) for p in ("sequence", "networkx", "numpy", "scipy", "pandas")},
        "sources": {p.relative_to(ROOT).as_posix(): sha(p) for p in sources},
        "plan_sha256": sha(OUTPUT / "plan.json"), "hardware": False,
        "scope": "native event kernel; abstract distance-sensitive provisioning and analytic Pauli CNOT; not native optics"})
    census, edge_rows = [], []
    for profile, fields in PROFILES.items():
        for side in (2, 4, 8, 16, 32):
            for topology in ("mesh", "mesh_debruijn"):
                config = ProbeConfig(side=side, topology=topology, generator_capacity=16, **fields)
                graph = build_topology(config)
                distances = [d for a, lengths in nx.all_pairs_shortest_path_length(graph)
                             for b, d in lengths.items() if a != b]
                cost = topology_cost(config, graph)
                diameter = max(distances)
                if topology == "mesh_debruijn" and diameter > (side**2).bit_length() - 1:
                    raise RuntimeError("Constructive logarithmic diameter bound violated")
                if topology == "mesh_debruijn" and cost["max_degree"] > 8:
                    raise RuntimeError("Degree bound violated")
                census.append({"profile": profile, "side": side, "topology": topology,
                               **cost, "diameter": diameter, "mean_distinct_pair_hops": np.mean(distances)})
                edge_rows.extend({"profile": profile, "side": side, "topology": topology,
                                  "source": a, "destination": b, **attrs}
                                 for a, b, attrs in graph.edges(data=True))
    pd.DataFrame(census).to_csv(OUTPUT / "topology_census.csv", index=False)
    pd.DataFrame(edge_rows).to_csv(OUTPUT / "edges.csv", index=False)
    records, hashes = [], {}
    started = time.perf_counter()
    for index, item in enumerate(plan):
        config = ProbeConfig(**item["config"])
        requests = probe_workload(config.side, item["requests"], item["seed"],
                                  item["arrival_rate_s"], item["relative_deadline_s"])
        result = ShortcutProbe(config, requests, item["seed"]).run()
        key = (item["profile"], config.side, config.placement, config.route_metric, item["seed"])
        if key in hashes and hashes[key] != result["workload_hash"]:
            raise RuntimeError("Topology workloads are not paired")
        hashes[key] = result["workload_hash"]
        run_id = f"{item['profile']}_n{config.side**2}_{config.placement}_{config.route_metric}_{config.topology}_s{item['seed']}"
        folder = OUTPUT / "runs" / run_id
        folder.mkdir(parents=True)
        dump(folder / "result.json", result)
        rows = pd.DataFrame(result["rows"])
        rows.to_csv(folder / "requests.csv", index=False)
        completed = rows[rows.completed]
        record = {"run_id": run_id, "profile": item["profile"], "side": config.side,
                  "topology": config.topology, "placement": config.placement, "route_metric": config.route_metric,
                  "seed": item["seed"], **result["summary"],
                  "workload_hash": result["workload_hash"],
                  "completion_fraction": len(completed)/len(rows),
                  "quality_qualified": int((completed.conditional_process_fidelity >= .9).sum()),
                  "quality_fraction": float((completed.conditional_process_fidelity >= .9).sum()/len(rows)),
                  "conditional_latency_s": completed.latency_s.mean(),
                  "conditional_process_fidelity": completed.conditional_process_fidelity.mean(),
                  "offered_mean_planned_hops": rows.planned_hops.mean(),
                  "resource_leaks": sum(r["used"] + r["waiting_units"] for r in result["resources"])}
        records.append(record)
        if (index+1) % 72 == 0:
            print(f"Completed {index+1}/{len(plan)} shortcut sensitivity runs", flush=True)
    data = pd.DataFrame(records)
    data.to_csv(OUTPUT / "summary.csv", index=False)
    dump(OUTPUT / "receipt.json", {"runs": len(data), "offered_tasks": int(data.requests.sum()),
         "resource_leaks": int(data.resource_leaks.sum()), "paired_workloads": True,
         "elapsed_s": time.perf_counter()-started, "summary_sha256": sha(OUTPUT / "summary.csv")})
    analyze()


def analyze():
    data = pd.read_csv(OUTPUT / "summary.csv")
    keys = ["profile", "side", "placement", "route_metric"]
    paired = []
    for key, group in data.groupby(keys):
        for metric in ("completion_fraction", "quality_fraction", "conditional_latency_s", "conditional_process_fidelity"):
            table = group.pivot(index="seed", columns="topology", values=metric)
            if len(table) != 6 or set(table.columns) != {"mesh", "mesh_debruijn"}:
                raise RuntimeError("Missing seed/arm")
            differences = (table.mesh_debruijn - table.mesh).dropna()
            n = len(differences)
            if n and not np.isfinite(differences).all():
                raise RuntimeError("Non-finite paired metric")
            mean = differences.mean() if n else None
            margin = t.ppf(.975,n-1)*differences.std(ddof=1)/np.sqrt(n) if n>1 else None
            paired.append(dict(zip(keys,key)) | {"metric":metric,"seed_pairs":n,
                          "mean_difference":mean,"lo95":mean-margin if margin is not None else None,
                          "hi95":mean+margin if margin is not None else None})
    pd.DataFrame(paired).to_csv(OUTPUT / "paired_differences.csv", index=False)
    figures = OUTPUT / "figures"
    figures.mkdir(exist_ok=True)
    census = pd.read_csv(OUTPUT / "topology_census.csv")
    fig, axes = plt.subplots(1,2,figsize=(7.2,2.8),layout="constrained")
    for topology, color, label in (("mesh","#426781","Mesh"),("mesh_debruijn","#248470","Quantum overlay")):
        rows = census[(census.profile=="fixed_pitch_lossy") & (census.topology==topology)].sort_values("nodes")
        axes[0].plot(rows.nodes,rows.diameter,"o-",color=color,label=label)
        axes[1].plot(rows.nodes,rows.total_optical_length_m,"o-",color=color,label=label)
    axes[0].set(xscale="log",xlabel="Cores N",ylabel="Exact quantum-graph diameter")
    axes[1].set(xscale="log",yscale="log",xlabel="Cores N",ylabel="Euclidean link-length sum (m)")
    axes[0].legend(frameon=False,fontsize=8)
    for ax in axes:
        ax.grid(alpha=.2)
    fig.savefig(figures/"shortcut_bounds_cost.pdf",bbox_inches="tight")
    fig.savefig(figures/"shortcut_bounds_cost.png",dpi=220,bbox_inches="tight")
    plt.close(fig)
    lines = [r"\paragraph{Executed bounded investigation.}",
             f"The separate prospective probe executes {len(data)} topology-policy-seed cases "
             f"with {int(data.requests.sum())} offered endpoint-CNOT tasks, using matched "
             "global generation capacity16 and two switchable active optical ports per core. "
             "Each physical link has exclusive service. Installed edge terminations and total "
             "optical length are additional, unequal costs, not free resources. Optical switches, "
             "transducers and contention in the classical fabric are not calibrated here. "
             "The event kernel is native SeQUeNCe; photon generation and CNOT quality use "
             "declared Bernoulli and Pauli abstractions, not the native photonic backend.",
             r"\begin{figure}[!t]\centering\includegraphics[width=\columnwidth]{../results/shortcut_v1/figures/shortcut_bounds_cost.pdf}\caption{Exact graph diameter and Euclidean optical-length lower bound at fixed1mm pitch. Cabling and installed terminations increase with the quantum overlay; logical edges are not a physical layout.}\label{fig:shortcut_cost}\end{figure}"]
    for profile in PROFILES:
        cells = data[(data.profile==profile)&(data.side==16)&(data.placement=="free")&(data.route_metric=="hops")]
        parts=[]
        for topology in ("mesh","mesh_debruijn"):
            rows=cells[cells.topology==topology]
            mean_latency=rows.conditional_latency_s.mean()
            latency_text=f"{1000*mean_latency:.3f}ms" if pd.notna(mean_latency) else "not estimable"
            parts.append(f"{topology.replace('_',' ')}: {int(rows.completed.sum())}/{int(rows.requests.sum())} completed, "
                         f"{int(rows.quality_qualified.sum())}/{int(rows.requests.sum())} quality-qualified, "
                         f"{latency_text} conditional mean latency")
        lines.append(profile.replace('_',' ')+" at256 cores, free placement and hop routing: "+"; ".join(parts)+".")
    lines.append("All profiles, restored-placement cells and expected-service routing controls are retained "
                 "in the accompanying raw records and paired seed intervals. Conditional means can use "
                 "different survivor subsets. This small sensitivity does not establish unconditional "
                 "latency scaling, fabricated hardware or compiled-application depth reduction.")
    (ROOT/"manuscript_existing_patch/shortcut_results.tex").write_text("\n\n".join(lines)+"\n",encoding="utf-8")


if __name__ == "__main__":
    run()
