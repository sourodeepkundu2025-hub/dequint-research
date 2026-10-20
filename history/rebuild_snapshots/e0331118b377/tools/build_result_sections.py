"""Generate manuscript numbers only from the accepted, integrity-checked batch."""

import json
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd


def write_sections():
    root = Path(__file__).resolve().parents[1]
    batch = root / "results" / "batch_v2"
    receipt = json.loads((batch / "analysis_receipt.json").read_text())
    table = pd.read_csv(batch / "aggregate.csv")
    pairs = pd.read_csv(batch / "paired_differences.csv")
    native = json.loads((root / "results/native_reference/native_summary.json").read_text())
    checks = json.loads((root / "results/quantum_validation/summary.json").read_text())
    mantissa, exponent = f"{checks['max_absolute_error']:.1e}".split("e")
    test_record = ET.parse(root / "results/branch_tests.xml").getroot().find("testsuite")
    test_count = int(test_record.attrib["tests"])
    directory = root / "manuscript"
    abstract = (f"The primary batch contains {receipt['runs']} runs and "
                f"{receipt['offered_requests']:,} offered gate tasks across ten seeds, "
                "including restored placement, loss, outage, purification, pooling and scaling sensitivities. "
                "All comparisons retain failed and low-quality requests in the offered-task denominator. ")
    primary = table[(table.cell == "primary_free_10000") & (table.policy == "adaptive")].iloc[0]
    delta = pairs[(pairs.cell == "primary_free_10000") & (pairs.metric == "quality_fraction")
                  & (pairs.comparison == "adaptive-minus-queue")].iloc[0]
    abstract += (f"At 10000 requests/s with free placement, the quality-aware candidate qualifies "
                 f"{100*primary.quality_fraction_mean:.2f}\\% of offered gates; its paired difference "
                 f"from queue-only selection is {100*delta.mean_difference:+.2f} percentage points "
                 f"(95\\% interval {100*delta.lo95:+.2f} to {100*delta.hi95:+.2f}). ")
    (directory / "results_abstract.tex").write_text(abstract.rstrip()+"\n", encoding="utf-8")
    lines = [r"\subsection{Independent Checks}",
        f"The exact Qiskit reference passed {checks['checks']} checks, with maximum absolute "
        f"channel/circuit discrepancy ${mantissa}\\times10^{{{int(exponent)}}}$. These are exact local "
        "calculations, not shot-based hardware experiments. "
        f"The primary-freeze exported-branch regression suite passed {test_count} tests, "
        "covering expiry, gate-time aging, radio timing and missing-metric reporting.",
        r"\begin{table}[t]\centering\small\caption{Separate native SeQUeNCe reference trials. Fidelity is conditional on acceptance.}\begin{tabular}{lrrr}\toprule Model & Trials & Successes & State fidelity\\\midrule"]
    for name, row in native["models"].items():
        label = "BBPSSW" if name == "bbpssw" else name.capitalize()
        lines.append(f"{label} & {row['trials']} & {row['successes']} & {row['conditional_state_fidelity']:.6f} " + r"\\")
    lines += [r"\bottomrule\end{tabular}\end{table}",
        "The native generation reference uses ideal emission/detection; teleportation uses the upstream example's "
        "own reservation and retry settings. The four finite-trial acceptance fractions have Wilson intervals "
        "in the machine-readable evidence and are not certified rate matches to the mesh abstraction. "
        "For ideal swapping of independently prepared Werner states with fidelities 0.8 and 0.9, "
        "the native density matrix has fidelity 0.726667 while its scalar metadata reports 0.72. "
        "Both are retained; scalar metadata is not substituted for a state calculation. The native BBPSSW "
        "output is not automatically Werner-twirled, unlike the explicitly twirled mesh abstraction.",
        r"\subsection{Task-Equivalent Primary Comparisons}",
        r"\begin{table*}[t]\centering\small\caption{Primary finite-batch means over ten seeds, 48 requests per seed. Completion and quality-qualified fractions use all offered tasks. Latency and process fidelity are conditional on completion.}\label{tab:primary}\begin{tabular}{llrrrrr}\toprule Placement / rate & Policy & Complete (\%) & Qualified (\%) & Latency (ms) & Process fidelity & Pairs/completed\\\midrule"]
    names = {"hh": "HH", "midpoint": "Minimax", "queue": "Queue", "adaptive": "Queue+quality"}
    for placement in ("free", "restored"):
        for rate in (1000, 10000):
            for policy in names:
                row = table[(table.cell == f"primary_{placement}_{rate}") & (table.policy == policy)].iloc[0]
                lines.append(f"{placement} / {rate} & {names[policy]} & {100*row.completion_fraction_mean:.2f} & "
                    f"{100*row.quality_fraction_mean:.2f} & {row.mean_latency_ms_mean:.4f} & "
                    f"{row.mean_completed_process_fidelity_mean:.4f} & {row.pairs_per_completed_gate_mean:.3f} " + r"\\")
    lines += [r"\bottomrule\end{tabular}\end{table*}",
        "Table~\\ref{tab:primary} reports each primary condition, not a selected best seed. "
        "Figure~\\ref{fig:quality} shows seed-level uncertainty. The following paired differences "
        "are quality-qualified fractions in percentage points, queue-plus-quality minus the named control:"]
    for placement in ("free", "restored"):
        for rate in (1000, 10000):
            rows = pairs[(pairs.cell == f"primary_{placement}_{rate}") & (pairs.metric == "quality_fraction")]
            for baseline in ("midpoint", "queue"):
                row = rows[rows.comparison == f"adaptive-minus-{baseline}"].iloc[0]
                mean = 0.0 if abs(row.mean_difference) < 1e-12 else row.mean_difference
                lines.append(f"{placement.capitalize()} placement at {rate} requests/s versus {names[baseline]}: "
                    f"{100*mean:+.2f} [95\\% CI {100*row.lo95:+.2f}, {100*row.hi95:+.2f}]. ")
    lines += [r"\begin{figure*}[t]\centering\includegraphics[width=.92\textwidth]{../results/batch_v2/figures/quality_by_task.pdf}\caption{All four primary cells. Error bars are 95\% intervals over seed-level qualified fractions; they are not per-request independent binomial intervals.}\label{fig:quality}\end{figure*}",
        r"\begin{figure*}[t]\centering\includegraphics[width=.92\textwidth]{../results/batch_v2/figures/latency_by_task.pdf}\caption{Conditional mean latency at 10000 requests/s. Completion fractions must be read alongside latency. The same free/restored task applies to every policy in a panel.}\end{figure*}",
        "A confidence interval spanning zero does not establish a quality benefit. Comparisons with endpoint "
        "HH cannot by themselves demonstrate an improvement over existing rendezvous routing. In particular, "
        "the queue-only control is needed before attributing any effect to the quality term.",
        r"\subsection{Faults, Purification and Shared Resources}",
        r"\begin{figure*}[t]\centering\includegraphics[width=.92\textwidth]{../results/batch_v2/figures/stress_tests.pdf}\caption{Predeclared secondary sensitivities. A zero qualified fraction is an outcome, not a missing run. Profiles are not measured physical platforms.}\end{figure*}"]
    for cell in ("radio", "short_memory", "packet_loss", "source_outage", "purification", "pool_1", "pool_4"):
        values = table[(table.cell == cell) & table.policy.isin(["hh", "midpoint", "adaptive"])]
        text = "; ".join(f"{names[row.policy]} {100*row.quality_fraction_mean:.2f}\\%" for row in values.itertuples())
        lines.append(f"{cell.replace('_', ' ').capitalize()} qualified fractions: {text}. ")
    lines += ["The complete-source-outage cell verifies that unsupported success is not manufactured by a "
        "routing policy. Short memory tests expose the incompatibility of long optical waiting times with "
        "high-quality gates. Ideal purification can consume additional resources without crossing the "
        "process-quality threshold. Raw accepted pair rate, resource consumption and useful operation "
        "rate must therefore remain separate metrics. Wired and radio outcomes are conditional on the "
        "declared bandwidth, token and offered-traffic model, not evidence of a universal WiNoC advantage.",
        r"\subsection{Mesh Scaling}",
        r"\begin{table}[t]\centering\small\caption{Sparse finite-batch scaling: conditional mean latency in ms. Rates scale with core count, but each seed still offers only 48 requests.}\begin{tabular}{rrrr}\toprule Cores & HH & Minimax & Queue+quality\\\midrule"]
    for side in (2, 4, 8, 16):
        cell = "primary_free_10000" if side == 4 else f"scale_{side}"
        values = [table[(table.cell == cell) & (table.policy == p)].iloc[0].mean_latency_ms_mean for p in ("hh", "midpoint", "adaptive")]
        lines.append(f"{side**2} & " + " & ".join(f"{value:.4f}" for value in values) + r"\\")
    lines += [r"\bottomrule\end{tabular}\end{table}",
        "These finite-batch estimates are not a logarithmic scaling proof. The mean Manhattan distance between "
        "uniformly selected distinct cores on an s-by-s mesh is 2s/3; quantum paths are unchanged by "
        "classical radio. No application circuit-depth improvement follows from these independent-gate "
        "service measurements. All runs reported zero unreleased resources and passed the paired workload-hash check."]
    (directory / "results.tex").write_text("\n\n".join(lines), encoding="utf-8")
    inputs = [batch / "analysis_receipt.json", batch / "aggregate.csv", batch / "paired_differences.csv",
              root / "results/quantum_validation/summary.json", root / "results/native_reference/native_summary.json",
              root / "results/branch_tests.xml", Path(__file__)]
    (directory / "result_section_provenance.json").write_text(json.dumps({
        str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in inputs}, indent=2), encoding="utf-8")
    return {"runs": receipt["runs"], "sections": str(directory / "results.tex")}


if __name__ == "__main__":
    print(json.dumps(write_sections(), indent=2))
