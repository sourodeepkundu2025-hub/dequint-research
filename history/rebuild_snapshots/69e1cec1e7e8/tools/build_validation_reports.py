"""Build the eleven requested evidence reports from immutable result records."""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

import pandas as pd
import pymupdf
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
TITLES = [
    "Integrated DEQUINT System Simulation Validation Report",
    "Quantum Teleportation Fidelity Validation Report",
    "EPR Generation and Entanglement Distribution Report",
    "BBPSSW Entanglement Purification Validation Report",
    "Multi-Hop and Inter-Core Teleportation Validation Report",
    "Latency Scaling and O(log N) Assessment Report",
    "EPR Throughput Validation and Improvement Report",
    "Benchmarking Report Against Baseline Architectures",
    "Five Software Components: Tests, Integration and Validation Report",
    "Fault and Failure Simulation Report",
    "Prototype Performance: Operating Conditions and Relevant Environment Assessment",
]
SLUGS = ["integrated_system", "teleportation_fidelity", "epr_generation", "bbpssw_purification",
         "multihop_teleportation", "latency_scaling", "throughput", "baseline_benchmarking",
         "components_integration", "fault_failure", "prototype_environment"]


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    batch = ROOT / "results/batch_v2"
    followup = ROOT / "results/followup_v1"
    base = pd.read_csv(batch / "summary.csv")
    aggregate = pd.read_csv(batch / "aggregate.csv")
    new = pd.read_csv(followup / "summary.csv")
    new_agg = pd.read_csv(followup / "aggregate.csv")
    control = pd.read_csv(followup / "paired_controls.csv")
    native = json.loads((ROOT / "results/native_reference/native_summary.json").read_text())
    quantum = json.loads((ROOT / "results/quantum_validation/summary.json").read_text())
    tests = ET.parse(ROOT / "results/followup_tests.xml").getroot()
    test_count = len(tests.findall(".//testcase"))
    failures = len(tests.findall(".//failure")) + len(tests.findall(".//error"))
    if failures:
        raise RuntimeError("Do not produce a passing component report from failed tests")
    output = ROOT / "output/validation_reports"
    output.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", fontName="Helvetica-Bold", fontSize=17, leading=21,
                             spaceAfter=12, textColor=colors.HexColor("#20292e")))
    styles.add(ParagraphStyle(name="ReportBody", fontName="Helvetica", fontSize=9, leading=13,
                             spaceAfter=8, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="ReportCell", fontName="Helvetica", fontSize=7.5, leading=10,
                             wordWrap="CJK"))
    styles.add(ParagraphStyle(name="ReportSmall", fontName="Helvetica", fontSize=7.5, leading=10,
                             spaceAfter=5, wordWrap="CJK"))
    manifests = []

    def paragraph(text, style="ReportBody"):
        return Paragraph(escape(str(text)), styles[style])

    def table(frame, widths=None):
        frame = frame.copy()
        if len(frame.columns) > 7:
            raise ValueError("Split wide report tables")
        widths = widths or [174*mm/len(frame.columns)]*len(frame.columns)
        values = [[paragraph(column, "ReportCell") for column in frame.columns]]
        for row in frame.itertuples(index=False, name=None):
            formatted = []
            for value in row:
                if pd.isna(value):
                    value = "Undefined"
                elif isinstance(value, float):
                    value = f"{value:.6g}"
                formatted.append(paragraph(value, "ReportCell"))
            values.append(formatted)
        result = Table(values, colWidths=widths, repeatRows=1, hAlign="LEFT")
        result.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e6ecee")),
            ("LINEBELOW", (0,0), (-1,0), .6, colors.HexColor("#596a70")),
            ("LINEBELOW", (0,-1), (-1,-1), .4, colors.HexColor("#b8c4c8")),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
            ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        return result

    def section(story, heading, text):
        story.append(Paragraph(escape(heading), styles["Heading2"]))
        story.append(paragraph(text))

    def native_summary(cells):
        rows = new_agg[(new_agg.group == "native") & new_agg.cell.isin(cells)]
        return rows[["cell", "policy", "mean_completion_fraction", "mean_process_fidelity", "latency_mean_s"]].rename(
            columns={"mean_completion_fraction":"Completed fraction", "mean_process_fidelity":"Process fidelity",
                     "latency_mean_s":"Latency (s)"})

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#596a70"))
        canvas.drawString(18*mm, 12*mm, "DEQUINT | simulation evidence, not hardware certification")
        canvas.drawRightString(192*mm, 12*mm, f"Page {doc.page}")

    for index, (title, slug) in enumerate(zip(TITLES, SLUGS), start=1):
        story = [paragraph(f"{index:02d}. {title}", "ReportTitle")]
        physical = index == 11
        status = ("PHYSICAL REQUIREMENT NOT SATISFIED. No relevant-environment prototype evidence is available."
                  if physical else "SOURCE-TRACEABLE SIMULATION ASSESSMENT. Scope and exclusions below are binding.")
        story += [paragraph(status), paragraph("Prepared 20 October 2026. Original submitted source is preserved unchanged.", "ReportSmall")]
        if index == 1:
            section(story, "Scope", "Fresh reconstruction, not a recovered original simulator. Primary abstract model and native photonic follow-up are separately parameterized and must not be merged into one physical validation claim.")
            story.append(table(pd.DataFrame([
                ["Abstract matched-gate batch",len(base),int(base.requests.sum()),"Native Timeline; declared optical/Pauli abstraction"],
                ["Native photonic follow-up",int((new.group=="native").sum()),int(new[new.group=="native"].requests.sum()),"Native BK/photons/detectors/teleportation and full Choi channel"],
                ["Circuit timing replay",int((new.group=="application").sum()),None,"Qiskit DAG timing only; no application-state fidelity"],
                ["Matched follow-up controls",int((new.group=="control").sum()),int(new[new.group=="control"].requests.sum()),"Equal total server budget and equal raw-fidelity purification controls"],
            ], columns=["Evidence layer","Runs","Offered gates","Meaning"])))
            section(story, "Integration checks", f"All result summaries record zero unreleased resources. The full software suite has {test_count} passing tests. Native payload Bell measurements, storage SWAPs and useful CNOTs share core gate capacity. Physical storage transfer uses three CNOTs, never amplitude copying.")
        elif index == 2:
            section(story, "Independent primitives", f"Exact local Qiskit validation passed {quantum['checks']} checks; maximum discrepancy {quantum['max_absolute_error']:.3g}. Circuit resources, QASM and full individual checks are retained under results/quantum_validation. No QPU or finite-shot hardware execution occurred.")
            teleport = native["models"]["teleportation"]
            section(story, "Native teleportation reference", f"The separate upstream TeleportApp reference completed {teleport['successes']}/{teleport['trials']} trials for unknown complex input states. Conditional state fidelity is {teleport['conditional_state_fidelity']:.9f}. This ideal-reference output-state fidelity is not the native mesh CNOT process fidelity tabulated below.")
            cases = new[(new.group=="native") & new.cell.isin([
                "native_ideal_4_free","native_ideal_4_restored","native_noisy_4_free","native_noisy_4_restored"])]
            values = []
            for cell, rows in cases.groupby("cell"):
                values.append([cell,int(rows.requests.sum()),int(rows.completed.sum()),
                               rows.mean_completed_process_fidelity.min(),
                               rows.mean_completed_process_fidelity.mean(),
                               rows.mean_completed_process_fidelity.max()])
            story.append(table(pd.DataFrame(values,columns=["Native case (all policies)","Offered","Completed",
                                                            "Minimum process F","Mean process F","Maximum process F"])))
            section(story, "Meaning of fidelity", "The native mesh carries two passive Choi diagnostic references across the complete ordered CNOT and required return hops. Process fidelity is relative to that ideal channel. Pair fidelity and selected output-state fidelity are different metrics. Ideal agreement does not establish device fidelity or a useful noisy operating regime.")
        elif index == 3:
            generation = native["models"]["generation"]
            section(story, "Native generation reference", f"Single complete-attempt native reference: {generation['successes']}/{generation['trials']} successes. Expected ideal probability {generation['expected_success_probability']}; observed Wilson95% interval {generation['wilson_95_interval']}. Conditional accepted-state fidelity is {generation['conditional_state_fidelity']}. Small-sample rate agreement is not certified.")
            rows = new[(new.group=="native") & (new.cell=="native_ideal_4_free")]
            story.append(table(rows[["policy","seed","attempts","native_photon_emissions","native_detector_notifications","consumed_pairs"]]))
            section(story, "Counter and timing boundaries", "Photon-emission counters are native send_qubit calls and include null-encoded BK photon objects. Detector notifications are herald messages, not unique detector clicks. Native generation uses fixed-delay dedicated sidebands; no microscopic spin dephasing during optical rounds is claimed. Generation IDs and protocol names join the raw records to accepted pair IDs.")
        elif index == 4:
            purification = native["models"]["bbpssw"]
            section(story, "Circuit reference", f"Native BBPSSW accepted {purification['successes']}/{purification['trials']} trials. For equal independent Werner inputs F=0.8, exact acceptance is {purification['expected_success_probability']:.9f}, conditional output fidelity {purification['expected_conditional_fidelity']:.9f}. The native circuit output is not automatically isotropically twirled. The abstract recurrence explicitly twirls inputs and output.")
            rows = control[(control.comparison=="purify1-minus-purify0") & (control.metric=="mean_completed_process_fidelity")]
            story.append(table(rows[["policy","metric","seed_pairs","mean_difference","lo95","hi95"]]))
            counts = new[(new.group=="control") & new.cell.str.startswith("matched_purification_")].groupby(["cell","policy"])[["requests","completed","quality_qualified"]].sum().reset_index()
            story.append(table(counts))
            section(story, "Survivor selection", "One purification round completes295/576 offered gates, versus575/576 without purification. Both arms yield zero quality-qualified completions. The intervals compare paired seed-level conditional means over different completed subsets, not a matched-request causal fidelity effect.")
            section(story, "Matched scope", "Both arms use raw fidelity0.7 and identical workload/resources/deadlines. Differences above are one ideal round minus none; latency intervals remain in paired_controls.csv. Failed preparation remains charged. These abstract controls are not native mesh purification or a physical advantage.")
        elif index == 5:
            story.append(table(native_summary(["native_ideal_2_free","native_ideal_2_restored","native_ideal_4_free","native_ideal_4_restored"])))
            section(story, "Task and resource equivalence", "For distance h, both gate policies use h accepted teleportation pairs under free placement and2h when outputs must return. Native storage transfers additionally execute3 local CNOTs per hop. The baseline performs the same ordered CNOT, not a different one-way delivery task. Gate and EPR counts for failed partial operations are retained.")
            section(story, "Swapping distinction", "Sequential payload teleportation is not an end-to-end entanglement-swapping chain. A separate native swapping reference accepted20/32 trials at configured probability0.6. Actual Werner density-matrix fidelity0.726666667 differs from its native scalar metadata0.72; both records are retained. This reference is not mislabeled as the multi-hop mesh route.")
        elif index == 6:
            section(story, "Scaling verdict", "O(log N) is NOT SUPPORTED on the unchanged nearest-neighbor quantum mesh. For N=s^2 cores, diameter is2(s-1), undirected links/BSM nodes are2s(s-1), and mean uniform distinct-core Manhattan distance is2s/3. Classical radio cannot shorten the quantum-layer paths. No fit to four points is treated as an asymptotic proof.")
            rows = []
            for side in (2,4,8,16):
                cell = "primary_free_10000" if side==4 else f"scale_{side}"
                for policy in ("hh","midpoint","adaptive"):
                    row = aggregate[(aggregate.cell==cell)&(aggregate.policy==policy)].iloc[0]
                    rows.append([side**2,policy,row.mean_latency_ms_mean,row.quality_fraction_mean])
            story.append(table(pd.DataFrame(rows,columns=["Cores","Policy","Conditional latency (ms)","Qualified fraction"])))
            section(story, "Experiment limit", "The larger meshes offer48 requests per seed with rate scaled per core. These are sparse finite-batch sensitivities, not steady-state saturation capacity or compiled application-depth measurements.")
        elif index == 7:
            section(story, "Metric reconciliation", "Historical approximately740 and540000 pairs/s claims are retired, not reconciled by choosing a favorable plot. Attempts, accepted raw pairs, consumed teleportation pairs, completed gates and quality-qualified gates are distinct numerators. Every rate uses the exported observation window ending at the last request deadline.")
            rows = base[base.cell=="primary_free_10000"].groupby("config_policy")[["raw_pair_rate_s","completed_gate_rate_s","quality_gate_rate_s"]].mean().reset_index()
            story.append(table(rows))
            section(story, "Interpretation", "These finite-batch rates include drain time and are not saturation throughput or fabricated device measurements. Native generation uses its own protocol timing, not a rate-matched implementation of the abstract complete-attempt model; cross-backend rate ratios are not claimed as improvements.")
        elif index == 8:
            section(story, "Matched baselines", "HH endpoint execution, minimax rendezvous, queue-only and queue-plus-quality receive identical gate tasks, deadlines and output-placement contracts. A separate application replay preserves the same circuit/QASM and initial mapping across policies. Existing per-link BSM and two-sided gate co-location remain attributed prior art, not DEQUINT novelty.")
            story.append(table(new_agg[new_agg.group=="application"][["cell","policy","mean_completion_fraction","latency_mean_s"]]))
            story.append(Spacer(1,7*mm))
            rows = control[(control.comparison=="pool24-minus-perlink24") & (control.metric.isin(["mean_completed_process_fidelity","mean_completed_latency_s"]))]
            story.append(table(rows[["policy","metric","seed_pairs","mean_difference","lo95","hi95"]]))
            section(story, "Control denominators", "Per-link24 completes575/576 offered gates with119 quality-qualified completions; pool24 completes576/576 with197 quality-qualified. Conditional intervals compare seed-level means and may use different surviving requests; all offered tasks remain in the qualified-fraction denominator.")
            section(story, "Attribution and exclusions", "Equal24-server pooling isolates abstract service allocation, not a hardware-cost-matched multiplexed central EPR source. The original quality-aware term did not establish an additional qualified-completion benefit over queue-only at10000requests/s/free placement: +1.04 percentage points,95% interval[-0.41,+2.49]. No algorithmic-superiority assertion follows from comparison only to HH.")
        elif index == 9:
            counts = {}
            for case in tests.findall(".//testcase"):
                name = case.attrib.get("classname", "unknown")
                counts[name] = counts.get(name,0)+1
            story.append(table(pd.DataFrame(sorted(counts.items()),columns=["Test module","Passing cases"])))
            section(story, "Five functional components", "(1) Quantum state/channel primitives; (2) heralded preparation and single-use entanglement records; (3) resource/event kernel and finite memory; (4) wired/radio classical transport; (5) task routing/execution and application dependency replay. Native primitive checks and full native Choi-route tests add independent backend coverage. Software components are not fabricated physical modules.")
            section(story, "Review coverage", "Independent scoped native review found and closed core-gate contention and partial-SWAP accounting defects before the follow-up batch. The existing benchmark had separate code/numerical review. Unit, integration and artifact integrity checks do not alone prove physical validity or submission readiness.")
        elif index == 10:
            story.append(table(native_summary(["native_detector_outage","native_short_cutoff","native_correction_loss"])))
            section(story, "Failure semantics", "Detector outage prevents accepted resources. Too-short cutoff rejects pairs before destructive payload use. Missing classical corrections may retry bits but never recreate the measured unknown source state. A correction-loss profile can also fail earlier in resource generation; raw terminal reasons identify the actual failure stage rather than forcing a desired outcome.")
            section(story, "Other exercised faults", "The primary batch separately retains packet loss, complete source outage, queue/deadline contention, short T2 and purification stress. Failed and low-quality tasks remain in offered-task denominators; undefined conditional latency/fidelity remain null with zero usable seed pairs. Application descendants cancel when predecessors fail; unrelated work is not silently canceled.")
        else:
            story.append(table(pd.DataFrame([
                ["FPGA / ASIC implementation","Not implemented / no evidence supplied"],
                ["Physical quantum processor or network","No hardware execution"],
                ["Cryogenic wireless compatibility","Not measured or validated"],
                ["Power, energy or thermal margin","No operating-condition measurements"],
                ["Fabrication / photonic area","No validated layout or area model"],
                ["Relevant-environment prototype qualification","Not satisfied by simulation"],
                ["Available evidence","Local exact quantum simulation and event-model sensitivity"],
            ],columns=["Requirement","Current evidence"])))
            section(story, "Physical-feasibility boundary", "The old area arithmetic24x600um^2=0.0144mm^2 does not establish total architecture footprint. A0.5K excursion is not a demonstrated operating margin at a10--20mK qubit stage. No claim is made that on-chip radio is compatible with the assumed superconducting or rare-earth platform. A network simulator cannot certify these requirements.")
            section(story, "Assessment outcome", "No physical prototype performance report can honestly be marked passed from this package. If an external assessment requires tested hardware at operating conditions, this remains an explicit unsatisfied requirement. No physical TRL uplift, regulatory approval or deployment readiness is implied.")

        section(story, "Evidence and reproducibility", "Inspect the original source archive/hash, executable code, accepted batch_v2 raw records, separately frozen followup_v1 records and JUnit evidence. The pre-review batch_v1 is quarantined and excluded. These documents distinguish exact local simulation, native protocol execution, abstract sensitivity, timing-only replay and absent physical evidence.")
        sources = [ROOT / "inputs/original/TEST_WILEY.zip", batch / "summary.csv", followup / "summary.csv",
                   ROOT / "results/followup_tests.xml"]
        for source in sources:
            story.append(paragraph(f"{source.relative_to(ROOT).as_posix()} | SHA-256 {_hash(source)}", "ReportSmall"))
        destination = output / f"{index:02d}_{slug}.pdf"
        doc = SimpleDocTemplate(str(destination), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
                                topMargin=18*mm, bottomMargin=20*mm, title=title, author="DEQUINT research evidence")
        doc.build(story, onFirstPage=footer, onLaterPages=footer)
        with pymupdf.open(destination) as pdf:
            pages = len(pdf)
            markers = [page.number+1 for page in pdf if "TBD" in page.get_text() or "TODO" in page.get_text()]
            if markers:
                raise RuntimeError(f"Unresolved report placeholders: {destination}")
        manifests.append({"number":index,"title":title,"path":str(destination.relative_to(ROOT)).replace("\\","/"),
                          "pages":pages,"sha256":_hash(destination),"physical_requirement_satisfied":False,
                          "scope":"simulation assessment" if not physical else "explicit physical evidence gap"})
    manifest = {"reports":manifests,"all_eleven_reports_exist":len(manifests)==11,
                "physical_prototype_validated":False,"source_original_preserved":True,
                "builder_sha256":_hash(Path(__file__))}
    (output / "report_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return {"reports":len(manifests),"pages":sum(row["pages"] for row in manifests),"output":str(output)}


if __name__ == "__main__":
    print(json.dumps(build(),indent=2))
