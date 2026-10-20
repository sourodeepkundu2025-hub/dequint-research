"""Generate inspectable source, backend, result and claim lineage from real files."""

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    output = ROOT / "qa"
    output.mkdir(exist_ok=True)
    base = pd.read_csv(ROOT / "results/batch_v2/summary.csv")
    followup = pd.read_csv(ROOT / "results/followup_v1/summary.csv")
    entries = []
    for path in sorted((ROOT / "results/batch_v2/runs").glob("*/summary.json")):
        summary = json.loads(path.read_text())
        entries.append({"run_id":summary["run_id"],"layer":"abstract paired gate experiment",
                        "seed":summary["seed"],"source":path.relative_to(ROOT).as_posix(),
                        "raw_data":(path.parent/"requests.csv").relative_to(ROOT).as_posix(),
                        "sha256":digest(path),"backend":summary["backend"],"hardware":False})
    for path in sorted((ROOT / "results/followup_v1/runs").glob("*/summary.json")):
        summary = json.loads(path.read_text())
        entries.append({"run_id":path.parent.name,"layer":summary["group"],"seed":summary["seed"],
                        "source":path.relative_to(ROOT).as_posix(),
                        "raw_data":(path.parent/"result.json").relative_to(ROOT).as_posix(),
                        "sha256":digest(path),"backend":summary.get("backend","abstract Network DAG timing replay"),
                        "hardware":False})
    if len(entries) != len(base)+len(followup):
        raise RuntimeError("Result inventory does not reconcile with summary tables")
    pd.DataFrame(entries).to_csv(output/"RESULT_LINEAGE_LEDGER.csv",index=False)
    backend = [
        ["Qiskit exact primitives","results/quantum_validation/summary.json","local exact density/Kraus",472,False,0,"No network or physical device"],
        ["Native protocol references","results/native_reference/native_summary.json","native SeQUeNCe protocols",128,False,0,"32 trials per each of4 submodels; no whole mesh"],
        ["Primary abstract mesh","results/batch_v2/summary.csv","native Timeline + declared optical/Pauli model",len(base),False,0,"460 finite-batch runs; not native photon-level events"],
        ["Native photonic mesh","results/followup_v1/summary.csv","native optical/protocol/density Choi execution",int((followup.group=="native").sum()),False,0,"Dedicated generation sidebands; addon admission/dephasing"],
        ["Application timing","results/followup_v1/summary.csv","Qiskit DAG + abstract gate task timing",int((followup.group=="application").sum()),False,0,"No application state fidelity or compiled physical depth"],
        ["Matched controls","results/followup_v1/summary.csv","abstract native-Timeline mesh",int((followup.group=="control").sum()),False,0,"Equal active server count / equal raw Bell fidelity"],
    ]
    pd.DataFrame(backend,columns=["evidence","source","backend","checks_or_runs","hardware","QPU_shots","boundary"]).to_csv(output/"QUANTUM_BACKEND_LEDGER.csv",index=False)
    resources = pd.read_csv(ROOT/"results/quantum_validation/resources.csv")
    resources.to_csv(output/"CIRCUIT_RESOURCE_LEDGER.csv",index=False)
    claims = [
        ["CLM-01","Same ordered CNOT under free/restored placement","supported in implemented models","src/dequint/network.py;src/dequint/native_mesh.py","results/batch_v2/summary.csv;results/followup_v1/summary.csv","Not endpoint state exchange; profiles separate"],
        ["CLM-02","Native full routed gate-channel ideal agreement","supported within simulated model","tests/test_native_mesh.py","results/followup_v1/runs/native_ideal_4_restored_midpoint_s201/result.json","No hardware fidelity or full native reservation stack"],
        ["CLM-03","Quality term improves over queue-only","not established","src/dequint/analyze.py","results/batch_v2/paired_differences.csv","+1.04pp,95% interval[-0.41,+2.49] in primary free/10000 cell"],
        ["CLM-04","Universal wireless NoC improvement","not supported","src/dequint/transport.py","results/batch_v2/aggregate.csv","Prospective service settings; generation native sidebands are fixed"],
        ["CLM-05","Logarithmic quantum-mesh latency scaling","withdrawn","src/dequint/routing.py","results/batch_v2/aggregate.csv","Sequential quantum mesh distances scale with sqrt(N)"],
        ["CLM-06","Application timing replay","supported bounded timing study","src/dequint/application_replay.py","results/followup_v1/aggregate.csv","Whole-application quantum state fidelity and physical depth unavailable"],
        ["CLM-07","BBPSSW correctness and benefit","ideal recurrence checked; benefit not guaranteed","src/dequint/quantum.py","results/quantum_validation/summary.json;results/followup_v1/paired_controls.csv","Werner/twirl assumptions and preparation wait matter"],
        ["CLM-08","Per-link BSM or two-sided migration is new","not defensible","docs/CLAIM_IMPLEMENTATION_MAP.md","https://arxiv.org/abs/2505.11195","Existing architecture, not our algorithmic novelty"],
        ["CLM-09","Physical area/thermal/prototype feasibility","unvalidated; unsupported claims removed","docs/VALIDATION_REPORT_INDEX.md","output/validation_reports/11_prototype_environment.pdf","No fabricated hardware or relevant-environment certification"],
        ["CLM-10","Resource IDs verify entanglement","withdrawn","src/dequint/network.py","docs/REVIEWER_RESPONSE.md","Ownership and single-use checks, not single-copy entanglement certification"],
    ]
    pd.DataFrame(claims,columns=["claim_id","statement","status","implementation_or_assessment","evidence","boundary"]).to_csv(output/"CLAIM_EVIDENCE_MATRIX.csv",index=False)
    source_rows = [
        ["SRC-01","Supplied latest archive","inputs/original/TEST_WILEY.zip","full local archive identity, manuscript sources","Preserved unchanged; source instructions not executed"],
        ["SRC-02","Recovered internship prototypes","inputs/legacy_prototypes","actual code inspection","Not the missing original integrated simulator"],
        ["LIT-01","Suance et al. 2025","https://arxiv.org/html/2505.11195v1","primary full-text inspection in prior audit","Per-link BSM/two-sided migration are prior art"],
        ["LIT-02","Official SeQUeNCe","https://github.com/sequence-toolbox/SeQUeNCe","actual pinned local source v1.3.0","Installed reviewed source hashes checked; addon separate"],
        ["LIT-03","Zhan et al. ACP2025","https://arxiv.org/html/2502.01964v1","primary method positioning","Background-generation policy not reproduced or beaten here"],
        ["LIT-04","InterQ2026","https://arxiv.org/abs/2605.17769","primary abstract/metadata positioning","Not a direct quantitative baseline reproduction"],
        ["LIT-05","Priority-aware routing2026","https://arxiv.org/abs/2609.38380","primary abstract/metadata positioning","No broad first fidelity/queue-aware claim"],
        ["LIT-06","Task-based control2026","https://arxiv.org/abs/2605.03336","primary abstract/metadata positioning","Task-based SeQUeNCe control is existing work"],
        ["LIT-07","Barrett-Kok2005","https://doi.org/10.1103/PhysRevA.71.060310","primary protocol identification","Native model is not calibrated microscopic device validation"],
        ["LIT-08","BBPSSW1996","https://doi.org/10.1103/PhysRevLett.76.722","primary recurrence/protocol plus independent circuit verification","Ideal Werner assumptions explicit"],
        ["LIT-09","Fan et al. 2025","https://doi.org/10.1038/s41377-025-01805-1","primary searchable PDF/abstract and publication metadata","Multiplexing prevents universal serialization assumption; not a reproduced hardware baseline"],
        ["LIT-10","van Leent et al. 2022","https://doi.org/10.1038/s41586-022-04764-4","primary indexed title/abstract/metadata; full-text access was blocked","Physical remote-atom experiment, not on-chip multicore validation"],
    ]
    pd.DataFrame(source_rows,columns=["id","source","locator","inspection_scope","boundary"]).to_csv(output/"SOURCE_LEDGER.csv",index=False)
    text = ["# Source Map", "", "Generated evidence layers are separate; no implicit full-text screening, hardware execution or superiority clearance.", ""]
    for row in source_rows:
        text.append(f"- {row[0]}: {row[1]}. Locator: {row[2]}. Scope: {row[3]}. Boundary: {row[4]}.")
    (ROOT/"docs/SOURCE_MAP.md").write_text("\n".join(text)+"\n",encoding="utf-8")
    return {"lineage_rows":len(entries),"claims":len(claims),"sources":len(source_rows),"backend_layers":len(backend)}


if __name__ == "__main__":
    print(json.dumps(build(),indent=2))
