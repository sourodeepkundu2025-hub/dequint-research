"""Seed-level estimates, paired controls and data-derived vector figures."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import t


POLICIES = ("hh", "midpoint", "queue", "adaptive")
COLORS = {"hh": "#4c5964", "midpoint": "#2c8c7e", "queue": "#946734", "adaptive": "#b74365"}


def interval(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return (None, None, None)
    mean = float(values.mean())
    half = float(t.ppf(.975, len(values) - 1) * values.std(ddof=1) / np.sqrt(len(values))) if len(values) > 1 else 0
    return mean, mean - half, mean + half


def paired_interval(first, second):
    delta = np.asarray(first, dtype=float) - np.asarray(second, dtype=float)
    finite = delta[np.isfinite(delta)]
    return len(finite), *interval(finite)


def analyze(batch_dir):
    batch = Path(batch_dir)
    if (batch / "NOT_ACCEPTED.md").exists():
        raise RuntimeError("Refusing to analyze quarantined pre-review evidence")
    frozen = json.loads((batch / "environment.json").read_text())["sources"]
    root = Path(__file__).resolve().parents[2]
    for name in ("network", "config", "kernel", "transport", "routing", "workload", "quantum", "experiments"):
        path = f"src/dequint/{name}.py"
        if frozen.get(path) != hashlib.sha256((root / path).read_bytes()).hexdigest():
            raise RuntimeError(f"Simulation source drift since execution: {path}")
    data = pd.read_csv(batch / "summary.csv")
    data["quality_fraction"] = data.quality_qualified / data.requests
    data["completion_fraction"] = data.completed / data.requests
    data["mean_latency_ms"] = data.mean_completed_latency_s * 1000
    data["p95_latency_ms"] = data.p95_completed_latency_s * 1000
    data["pairs_per_completed_gate"] = data.consumed_pairs / data.completed.replace(0, np.nan)
    data["attempts_per_offered_gate"] = data.attempts / data.requests
    for (_, seed), rows in data.groupby(["cell", "seed"]):
        if rows.workload_sha256.nunique() != 1:
            raise RuntimeError(f"Unpaired workloads for seed {seed}")
    if data.resource_leaks.any():
        raise RuntimeError("Resource-leak acceptance check failed")
    metrics = ["quality_fraction", "completion_fraction", "mean_latency_ms", "p95_latency_ms",
               "mean_completed_process_fidelity", "pairs_per_completed_gate", "attempts_per_offered_gate",
               "quality_gate_rate_s", "raw_pair_rate_s", "quantum_queue_wait_s", "classical_wait_s", "wall_time_s"]
    aggregate = []
    for (cell, policy), rows in data.groupby(["cell", "config_policy"]):
        result = {"cell": cell, "policy": policy, "seeds": len(rows), "offered_requests": int(rows.requests.sum())}
        for metric in metrics:
            mean, low, high = interval(rows[metric])
            result.update({f"{metric}_mean": mean, f"{metric}_lo95": low, f"{metric}_hi95": high})
            result[f"{metric}_usable_seeds"] = int(np.isfinite(rows[metric]).sum())
        aggregate.append(result)
    table = pd.DataFrame(aggregate)
    table.to_csv(batch / "aggregate.csv", index=False)
    paired = []
    for cell, rows in data.groupby("cell"):
        for baseline in ("hh", "midpoint", "queue"):
            first = rows[rows.config_policy == "adaptive"].set_index("seed")
            other = rows[rows.config_policy == baseline].set_index("seed")
            common = first.index.intersection(other.index)
            if not len(common):
                continue
            for metric in metrics[:5]:
                count, mean, low, high = paired_interval(first.loc[common, metric], other.loc[common, metric])
                paired.append({"cell": cell, "comparison": f"adaptive-minus-{baseline}",
                               "metric": metric, "seed_pairs": count, "mean_difference": mean,
                               "lo95": low, "hi95": high})
    pd.DataFrame(paired).to_csv(batch / "paired_differences.csv", index=False)
    figure_dir = batch / "figures"
    figure_dir.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                         "savefig.dpi": 300, "pdf.fonttype": 42})
    fig, axes = plt.subplots(2, 2, figsize=(8, 5), constrained_layout=True)
    for ax, placement, rate in zip(axes.flat, ["free", "free", "restored", "restored"], [1000, 10000, 1000, 10000]):
        rows = table[table.cell == f"primary_{placement}_{rate}"].set_index("policy").reindex(POLICIES)
        y = rows.quality_fraction_mean.to_numpy()
        ax.bar(range(4), y, color=[COLORS[p] for p in POLICIES], width=.65)
        ax.errorbar(range(4), y, yerr=[y - rows.quality_fraction_lo95, rows.quality_fraction_hi95 - y],
                    fmt="none", ecolor="black", capsize=3, linewidth=.8)
        ax.set(xticks=range(4), xticklabels=["HH", "Minimax", "Queue", "Q+quality"], ylim=(0, 1),
               title=f"{placement.capitalize()} placement; {rate:,} requests/s", ylabel="Quality-qualified fraction")
    _save(fig, figure_dir / "quality_by_task")
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.1), constrained_layout=True)
    for ax, placement in zip(axes, ["free", "restored"]):
        rows = table[table.cell == f"primary_{placement}_10000"].set_index("policy").reindex(POLICIES)
        y = rows.mean_latency_ms_mean.to_numpy()
        ax.bar(range(4), y, color=[COLORS[p] for p in POLICIES], width=.65)
        ax.errorbar(range(4), y, yerr=[y - rows.mean_latency_ms_lo95, rows.mean_latency_ms_hi95 - y],
                    fmt="none", ecolor="black", capsize=3, linewidth=.8)
        ax.set(xticks=range(4), xticklabels=["HH", "Minimax", "Queue", "Q+quality"],
               title=f"{placement.capitalize()} placement", ylabel="Conditional mean gate latency (ms)")
    _save(fig, figure_dir / "latency_by_task")
    fig, ax = plt.subplots(figsize=(6.5, 3.2), constrained_layout=True)
    labels = ["radio", "short_memory", "packet_loss", "source_outage", "purification", "pool_1", "pool_4"]
    for index, policy in enumerate(("hh", "midpoint", "adaptive")):
        rows = table[table.policy == policy].set_index("cell").reindex(labels)
        ax.bar(np.arange(len(labels)) + (index - 1) * .25, rows.quality_fraction_mean,
               width=.24, color=COLORS[policy], label=policy)
    ax.set(xticks=range(len(labels)), xticklabels=["Radio", "Short T2", "Pkt loss", "Outage", "BBPSSW", "Pool 1", "Pool 4"],
           ylabel="Quality-qualified fraction", ylim=(0, 1))
    ax.legend(ncols=3, frameon=False)
    _save(fig, figure_dir / "stress_tests")
    receipt = {"runs": len(data), "offered_requests": int(data.requests.sum()),
               "paired_workload_checks": "passed", "resource_leaks": int(data.resource_leaks.sum()),
               "uncertainty_unit": "independent seed; two-sided Student-t 95% interval",
               "summary_sha256": hashlib.sha256((batch / "summary.csv").read_bytes()).hexdigest(),
               "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "claim": "finite-batch prospective simulation; no hardware or global optimality"}
    (batch / "analysis_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def _save(fig, stem):
    fig.savefig(stem.with_suffix(".pdf"))
    fig.savefig(stem.with_suffix(".png"))
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("batch")
    print(json.dumps(analyze(parser.parse_args().batch), indent=2))
