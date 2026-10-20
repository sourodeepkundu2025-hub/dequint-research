"""Data-derived follow-up tables and figures; never substitute timing for fidelity."""

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
POLICIES = ("hh", "midpoint", "queue", "adaptive")
COLORS = ("#4c5964", "#2c8c7e", "#946734", "#b74365")
NAMES = {"hh": "HH", "midpoint": "Minimax", "queue": "Queue", "adaptive": "Queue+quality"}


def build(output_dir):
    folder = Path(output_dir)
    data = pd.read_csv(folder / "summary.csv")
    aggregate = pd.read_csv(folder / "aggregate.csv")
    controls = pd.read_csv(folder / "paired_controls.csv")
    env = json.loads((folder / "environment.json").read_text())
    for name in ("native_mesh", "application_replay", "followup", "network", "kernel", "transport", "quantum"):
        key = f"src/dequint/{name}.py"
        if env["sources"][key] != hashlib.sha256((ROOT / key).read_bytes()).hexdigest():
            raise RuntimeError(f"Follow-up source drift: {key}")
    figures = folder / "figures"
    figures.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                         "savefig.dpi": 300, "pdf.fonttype": 42})
    circuits = ("ghz_6", "qft_6", "cdkm_2", "quantum_volume_4")
    labels = ("GHZ (6)", "QFT (6)", "Adder (6)", "QV (4)")
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.3), constrained_layout=True)
    for ax, placement in zip(axes, ("free", "restored")):
        for index, policy in enumerate(POLICIES):
            rows = aggregate[(aggregate.group == "application") & (aggregate.policy == policy)].set_index("cell")
            values = [1000*rows.loc[f"app_{circuit}_{placement}", "latency_mean_s"] for circuit in circuits]
            ax.bar(np.arange(4)+(index-1.5)*.19, values, width=.18, color=COLORS[index], label=NAMES[policy])
        ax.set(xticks=range(4), xticklabels=labels, ylabel="Completed-application mean (ms)", title=f"{placement.capitalize()} placement")
    axes[0].legend(fontsize=7, frameon=False, ncols=2)
    _save(fig, figures / "application_makespan")
    native_cells = ("native_ideal_4_free", "native_ideal_4_restored", "native_noisy_4_free", "native_noisy_4_restored")
    native_labels = ("Ideal/free", "Ideal/return", "Noisy/free", "Noisy/return")
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.3), constrained_layout=True)
    for index, policy in enumerate(POLICIES):
        rows = aggregate[(aggregate.group == "native") & (aggregate.policy == policy)].set_index("cell")
        x = np.arange(4)+(index-1.5)*.19
        axes[0].bar(x, [rows.loc[cell,"mean_process_fidelity"] for cell in native_cells],
                    width=.18, color=COLORS[index], label=NAMES[policy])
        axes[1].bar(x, [1000*rows.loc[cell,"latency_mean_s"] for cell in native_cells], width=.18, color=COLORS[index])
    axes[0].set(ylabel="Full native Choi process fidelity", ylim=(0,1.04))
    axes[0].axhline(.9, color="#4c5964", linestyle="--", linewidth=.8)
    axes[1].set(ylabel="Completed native gate latency (ms)")
    for ax in axes:
        ax.set_xticks(range(4), native_labels, rotation=15)
    axes[0].legend(fontsize=7, frameon=False, ncols=2)
    _save(fig, figures / "native_channel_checks")

    native = data[data.group == "native"]
    app = data[data.group == "application"]
    ideal = native[native.cell.str.startswith("native_ideal")]
    lines = [r"\subsection{Native Photonic Mesh Follow-up}",
        f"A separately frozen follow-up executes {len(native)} native-mesh runs covering "
        f"{int(native.requests.sum())} offered ordered-CNOT tasks on actual native photonic components. "
        f"The ideal corner-to-corner cells complete {int(ideal.completed.sum())}/{int(ideal.requests.sum())} "
        f"tasks; their minimum process fidelity is {ideal.mean_completed_process_fidelity.min():.10f}. "
        "The diagnostic Choi references remain attached across all hops, the useful gate and required "
        "return paths. Three-CNOT communication-to-data storage SWAPs consume the shared core gate resource; "
        "started and completed operations are counted separately under deadline failure. This is a stronger "
        "channel-level check than isolated single-hop output states, not a rate-equivalent validation of batch\\_v2.",
        r"\begin{figure*}[t]\centering\includegraphics[width=.92\textwidth]{../results/followup_v1/figures/native_channel_checks.pdf}\caption{Native 4x4 corner-to-corner CNOT channels, four seeds per cell. Ideal and noisy profiles use distinct declared parameters. Fidelity is the complete Choi channel, not resource-success probability.}\end{figure*}",
        "The native backend retains fixed-delay dedicated generation sidebands to respect the upstream "
        "BK emission-negotiation timing model. Payload correction and acknowledgment use the contended "
        "wired/radio fabric. Finite data/communication slots and local gate admission are addon services; "
        "the unmodified native reservation stack is not claimed. Explicit pair dephasing begins after "
        "successful heralding; in-generation spin dephasing is not microscopically simulated. Native "
        "send-qubit counts include null-encoded BK photon objects. Thus these records check implemented "
        "channels and event causality without identifying a physical operating platform.",
        r"\subsection{Dependency-Preserving Application Timing}",
        f"The follow-up also replays {len(app)} Qiskit-derived circuit-policy-seed cases. "
        "Per-qubit DAG dependencies, resource contention, failure cancellation and dynamic output "
        "mapping are preserved. The replay reuses the abstract CNOT timing path; it does not propagate "
        "an application state. No application fidelity or compiled physical depth is inferred. "
        "Table~\\ref{tab:applications} includes all completed-application counts alongside conditional "
        "makespan. Four seeds are a bounded sensitivity study, not a broad superiority result.",
        r"\begin{table*}[t]\centering\small\caption{Application timing follow-up. Each entry is completed applications out of four / conditional mean makespan in ms. NA denotes no completed application. Qubit counts refer to logical inputs.}\label{tab:applications}\begin{tabular}{llrrrr}\toprule Circuit & Placement & HH & Minimax & Queue & Queue+quality\\\midrule"]
    for circuit, label in zip(circuits, labels):
        for placement in ("free", "restored"):
            cells = []
            for policy in POLICIES:
                row = aggregate[(aggregate.cell == f"app_{circuit}_{placement}") & (aggregate.policy == policy)].iloc[0]
                completed = round(row.mean_completion_fraction * row.seeds)
                mean = f"{1000*row.latency_mean_s:.3f}" if pd.notna(row.latency_mean_s) else "NA"
                cells.append(f"{completed}/4 / {mean}")
            lines.append(f"{label} & {placement} & " + " & ".join(cells) + r"\\")
    lines += [r"\bottomrule\end{tabular}\end{table*}",
        r"\begin{figure*}[t]\centering\includegraphics[width=.92\textwidth]{../results/followup_v1/figures/application_makespan.pdf}\caption{Conditional completed-application timing. Read the completion counts in Table~\ref{tab:applications}; censored/failed applications are not silently treated as fast completions.}\end{figure*}",
        r"\subsection{Matched Resource and Purification Controls}",
        "Unlike the earlier low-capacity pooling stress cells, the follow-up compares 24 distributed "
        "link servers with a flexible pool of 24 total servers. This isolates the abstract service "
        "allocation difference, not the optical hardware/switch cost of a physical centralized source. "
        "A second matched comparison holds raw Bell fidelity at0.7 and compares zero versus one ideal "
        "purification round. The latter remains a Werner-twirled abstract network experiment, not native "
        "mesh purification. The paired mean-process-fidelity differences below use matching seeds "
        "and conditional completions; these are descriptive intervals without multiplicity correction."]
    for comparison in ("pool24-minus-perlink24", "purify1-minus-purify0"):
        for policy in ("hh", "midpoint", "adaptive"):
            row = controls[(controls.comparison == comparison) & (controls.policy == policy)
                           & (controls.metric == "mean_completed_process_fidelity")].iloc[0]
            mean = 0.0 if abs(row.mean_difference) < 1e-12 else row.mean_difference
            lines.append(f"{comparison.replace('-', ' ')} / {NAMES[policy]}: {mean:+.4f} "
                         f"[95\\% interval {row.lo95:+.4f}, {row.hi95:+.4f}], {row.seed_pairs} usable seed pairs. ")
    (ROOT / "manuscript/followup.tex").write_text("\n\n".join(lines), encoding="utf-8")
    (ROOT / "manuscript/followup_section_provenance.json").write_text(json.dumps({
        "summary_sha256": hashlib.sha256((folder / "summary.csv").read_bytes()).hexdigest(),
        "builder_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_environment_sha256": hashlib.sha256((folder / "environment.json").read_bytes()).hexdigest(),
    }, indent=2), encoding="utf-8")
    return {"native_runs": len(native), "application_runs": len(app), "source_checks": "passed"}


def _save(fig, path):
    fig.savefig(path.with_suffix(".pdf"))
    fig.savefig(path.with_suffix(".png"))
    plt.close(fig)


if __name__ == "__main__":
    print(json.dumps(build(ROOT / "results/followup_v1"), indent=2))
