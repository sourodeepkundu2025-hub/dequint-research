"""Apply source-attributable consolidation to the supplied Wiley manuscript.

The immutable pre-consolidation source and supplied archive retain all legacy
plots. Active numerical figures come only from named accepted evidence layers.
"""

from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "manuscript_existing_patch"


def between(text, start, end):
    return text[text.index(start):text.index(end)]


def main():
    old = (ROOT / "qa/baseline_main_before_consolidation.tex").read_text(encoding="utf-8")
    header = old[:old.index(r"\section{Introduction}")]
    notice = header.index(r"\noindent\textbf{Incremental author-review copy.}")
    footnote = header.index(r"\renewcommand\thefootnote{}", notice)
    header = header[:notice] + header[footnote:]
    header = header.replace("TWT, bidirectional (two-way) teleportation", "TWT, two-sided gate co-location")
    # Suppress production-only placeholders without modifying the Wiley class.
    header = header.replace(r"\begin{document}", r"""\makeatletter
\historydates{}
\doiheadtext{}
\gdef\printjnlcitation{}
\def\oddhead@titlepage@info{\vbox{\hsize=\textwidth\hrule\vskip6pt}}
\def\evenhead@titlepage@info{\oddhead@titlepage@info}
\def\oddfoot@titlepage@info{\hbox to\textwidth{\footnotesize Author revision\hfil\thepage}}
\def\evenfoot@titlepage@info{\oddfoot@titlepage@info}
\def\head@headings@def#1{\vbox{\hsize=\textwidth\strut\par\vskip-5pt
\hrule\vskip2pt\hbox to\textwidth{#1}\vskip1pt}}
\makeatother
\setlength{\emergencystretch}{1em}
\begin{document}""")
    header = re.sub(r"\\jnlcitation\{.*?\}\s*\n\s*\\maketitle", r"\\maketitle", header, flags=re.S)
    abstract = r"""\abstract[Abstract]{DEQUINT evaluates a decentralized quantum interconnect
with per-link Bell-state measurement, classical feed-forward and two-sided gate
co-location. Endpoint and rendezvous policies perform the same ordered CNOT,
with free and restored output placements reported separately. An executable
SeQUeNCe resource model charges stochastic preparation, retries, finite
communication memories, classical contention, dephasing and failed tasks. The
primary 460-run benchmark offers 22080 gates; a separate 300-run follow-up
includes native photonic channels, application timing and matched controls.
At 10000 arrivals/s with free placement, queue-plus-quality qualifies 121/480
gates versus 116/480 for queue-only, a difference of 1.04 percentage points
(95\% paired interval -0.41 to 2.49); an added quality-term benefit is not
established. An optional bounded-degree quantum overlay has hop diameter at
most $\log_2N$, not a logarithmic-latency guarantee. A separate 432-run probe
charges distance-dependent loss, finite active ports and matched generation
capacity; lower conditional latency can accompany fewer completed tasks.
The architecture and evaluation distinguish simulated channel evidence from
compiled-circuit scope and physical integration requirements.}
"""
    header = header[:header.index(r"\abstract[Abstract]")] + abstract + header[header.index(r"\keywords"):]
    architecture = between(old, r"\section{System Architecture}", r"\subsection{Feasibility of Dense BSM Integration}")
    # Supplied Picture2 embeds an untraceable cooperativity result and a central
    # generator; Picture1 describes a different control schematic. Preserve both
    # original files, but do not present either as the evaluated architecture.
    legacy_start = architecture.index(r"Fig.~\ref{fig:dequint_upload_1}")
    legacy_end = architecture.index(r"Fig.~\ref{fig:module}")
    architecture = architecture[:legacy_start] + architecture[legacy_end:]
    architecture = architecture.replace("a \\emph{per-link BSM node} serving as the entanglement source", "a \\emph{per-link BSM node} heralding entanglement between emitter memories")
    architecture = architecture.replace("a Wireless Router (WR) implementing 2DMAC", "a Wireless Router (WR) providing declared token service")
    architecture = architecture.replace("dotted green lines\nare wireless classical shortcuts", "solid orange arrows\nare illustrative wireless classical shortcuts")
    architecture = architecture.replace("low-latency classical communication to enable scalable", "classical feed-forward to coordinate")
    architecture = architecture.replace("with EPR qubits flowing over dashed quantum channels", "with photons directed from endpoint memories to the BSM")
    architecture = architecture.replace("\\draw[qarr] (bsm.west) --", "\\draw[qarr] (qm.east) --")
    architecture = architecture.replace("{EPR$_A$} (qm.east)", "{photon $A$} (bsm.west)")
    architecture = architecture.replace("\\draw[qarr] (bsm.east) --", "\\draw[qarr] (dqm.west) --")
    architecture = architecture.replace("{EPR$_B$} (dqm.west)", "{photon $B$} (bsm.east)")
    architecture = architecture.replace("Dashed blue arrows carry EPR qubits over quantum channels; solid orange arrows carry classical correction bits over the WiNoC.", "Dashed blue arrows carry emitted photons toward the BSM; entangled matter memories remain at the endpoints. Solid orange arrows carry classical feed-forward.")
    architecture = architecture.replace("\\draw[arr, qblue!60] (qm) -- (wr);", "\\draw[carr] (qm) -- (wr);")
    architecture = architecture.replace("\\draw[arr, qblue!60] (dqm) -- (dwr);", "\\draw[carr] (dqm) -- (dwr);")
    # Move the new numerical results to the results section, retaining theory here.
    extension = (PAPER / "shortcut_extension.tex").read_text(encoding="utf-8")
    extension = extension.replace(r"\input{shortcut_results.tex}", "")
    (PAPER / "shortcut_extension.tex").write_text(extension, encoding="utf-8")
    primary = (ROOT / "manuscript/results.tex").read_text(encoding="utf-8")
    faults_at = primary.index(r"\subsection{Faults, Purification and Shared Resources}")
    scale_at = primary.index(r"\subsection{Mesh Scaling}")
    primary_main = primary[:faults_at] + primary[scale_at:]
    faults = primary[faults_at:scale_at]
    followup = (ROOT / "manuscript/followup.tex").read_text(encoding="utf-8")
    app_at = followup.index(r"\subsection{Dependency-Preserving Application Timing}")
    controls_at = followup.index(r"\subsection{Matched Resource and Purification Controls}")
    results = "\\section{Experimental Results}\n\\label{sec:results}\n" + primary_main + followup[:app_at]
    results += "\n\\subsection{Quantum-Overlay Cost and Completion}\n\\input{shortcut_results.tex}\n"
    reliability = r"""\section{Reliability and Error Budget Analysis}
\label{sec:reliability}
\subsection{Availability Is Not Conditional Fidelity}
A failed entanglement attempt reduces supply and adds waiting; it does not
directly multiply the fidelity of a heralded pair. High conditional fidelity and
low completion probability can coexist. Conversely, retries and memory aging
can reduce completed-channel quality. Averaging $p^h$ over requests is not the
same as $p^{\mathbb E[h]}$. Neither a marginal-loss pie normalized to 100\% nor
a fixed hop reliability is used as a decomposition of task failure here.
The raw task records retain one terminal status alongside overlapping counters
for preparation, queueing, classical failures and consumed resources. Successful
completion below the quality threshold is reported separately from failure.
""" + faults + followup[controls_at:]
    benchmark = "\\section{Benchmark Circuit Overhead Analysis}\n\\label{sec:benchmark}\n" + followup[app_at:controls_at]
    benchmark += "\n\\IfFileExists{compiled_depth_results.tex}{\\input{compiled_depth_results.tex}}{}\n"
    results += "\n\\IfFileExists{review_supplement_results.tex}{\\input{review_supplement_results.tex}}{}\n"
    (PAPER / "revision_results.tex").write_text(results, encoding="utf-8")
    (PAPER / "revision_reliability.tex").write_text(reliability, encoding="utf-8")
    (PAPER / "revision_benchmark.tex").write_text(benchmark, encoding="utf-8")
    front = (PAPER / "revision_front.tex").read_text(encoding="utf-8")
    body = header + front + architecture
    for name in ("architecture", "protocol", "implementation", "results", "reliability", "benchmark", "discussion"):
        body += f"\n\\input{{revision_{name}.tex}}\n"
    disclosure = between(old, r"\bmsection*{Author contributions}", r"\begin{thebibliography}")
    disclosure = disclosure[:disclosure.index(r"\bmsection*{Data availability statement}")] + r"""\bmsection*{Data availability statement}
The reproducible addon, declared protocols, raw per-request results and evidence
ledgers accompany the revision package. The base simulator is available at
\url{https://github.com/sequence-toolbox/SeQUeNCe}. Publication of the addon to a
public remote repository is not asserted. Original untraceable performance
illustrations are retained in the source archive, not used as new results.
"""
    bibliography = between(old, r"\begin{thebibliography}{99}", r"\end{thebibliography}")
    bibliography = bibliography.replace("``An Optical Interconnect for Modular Quantum Computers,''\narXiv:2412.09299v2,2024.", "``Q-Fly: An Optical Interconnect for Modular Quantum Computers,''\narXiv:2412.09299v4,2025.")
    extra = r"""
\bibitem{acp2025} C.~Zhan, J.~Chung, A.~Zang, A.~Kolar and R.~Kettimuthu,
``Design and Simulation of the Adaptive Continuous Entanglement Generation
Protocol,'' IEEE QCNC, 2025, doi:10.1109/QCNC64685.2025.00028;
arXiv:2502.01964v2.
\bibitem{taskcontrol2026} A.~Pirker et al., ``Centralizing Task-based Approach
to Quantum Network Control,'' arXiv:2605.03336v1, 2026 (preprint).
\bibitem{fan2025multiplex} Y.-R.~Fan et al., ``Quantum entanglement network enabled
by a state-multiplexing quantum light source,'' Light: Science \& Applications,
vol.~14, art.~189, 2025, doi:10.1038/s41377-025-01805-1.
\bibitem{vanleent2022} T.~van Leent et al., ``Entangling single atoms over 33 km
telecom fibre,'' Nature, vol.~607, pp.~69--73, 2022,
doi:10.1038/s41586-022-04764-4.
"""
    bibliography += extra
    entries = {m.group(1):m.group(0) for m in re.finditer(r"\\bibitem\{([^}]+)\}.*?(?=\\bibitem|\Z)", bibliography, re.S)}
    all_source = body + "\n" + "\n".join(p.read_text(encoding="utf-8") for p in PAPER.glob("*.tex") if p.name.startswith("revision_") or p.name.startswith("shortcut_"))
    keys = {key.strip() for group in re.findall(r"\\cite\{([^}]+)\}", all_source) for key in group.split(",")}
    if keys - entries.keys():
        raise RuntimeError(f"Missing citation keys: {keys - entries.keys()}")
    citation_order = []
    expanded = body
    for _ in range(3):
        expanded = re.sub(r"\\input\{([^}]+)\}", lambda m: (PAPER/m.group(1)).read_text(encoding="utf-8") if (PAPER/m.group(1)).is_file() else m.group(0), expanded)
    for group in re.findall(r"\\cite\{([^}]+)\}", expanded):
        for key in group.split(","):
            if key.strip() not in citation_order:
                citation_order.append(key.strip())
    selected = "".join(entries[k] for k in citation_order)
    body += disclosure + "\n\\begin{thebibliography}{99}\n" + selected + "\\end{thebibliography}\n"
    body += r"""\bmsection*{Supporting information}
Protocols, raw evidence, source hashes, per-point reviewer responses and component
validation reports accompany the revision. Quantum-primitive, abstract mesh,
native mesh, application replay and overlay evidence remain separately identified.
\appendix
\section{Barrett--Kok State Machine}
\label{app:bk}
Each accepted generation uses two-round single-detection heralding. The abstract
attempt probability and duration are Eq.~\ref{eq:attempt}; there is no separate
inconsistent detector/attenuation factor applied only in an appendix. A complete
attempt is charged even when an earlier physical rejection might be possible.
The native protocol check tests its own optical implementation and parameters.
\section{Entanglement Purification (BBPSSW)}
\label{app:bbpssw}
For independent Werner inputs, $q_j=(1-F_j)/3$, the modeled acceptance and
retained fidelity are
\begin{align}
P_{acc}&=(F_1+q_1)(F_2+q_2)+4q_1q_2,\\
F_{out}&=(F_1F_2+q_1q_2)/P_{acc}.
\end{align}
Explicit ideal bilateral input/output twirls are part of this abstraction.
Both inputs, local operations, classical comparison and subsequent waiting are
charged. The matched controls show why accepted-pair fidelity alone is inadequate.
\section{SeQUeNCe Simulator Extensions}
\label{app:sequence}
The primary addon implements finite resources, generation records, classical
transport and a gate-task controller on the native event kernel. Native mesh
checks additionally use upstream photonic and quantum-manager components;
application replay schedules Qiskit DAGs without propagating an application state.
The overlay uses separate Bernoulli optics and analytic Pauli quality. No
amplitude-copying transfer, physical 2DMAC implementation, per-payload fidelity
measurement or unmodified full native reservation stack is implied.
\end{document}
"""
    (PAPER / "main.tex").write_text(body, encoding="utf-8")
    print("Consolidated supplied Wiley manuscript; original archive and baseline unchanged")


if __name__ == "__main__":
    main()
