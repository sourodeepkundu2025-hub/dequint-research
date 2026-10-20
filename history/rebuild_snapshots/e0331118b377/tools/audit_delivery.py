"""Check delivered evidence identities; this is not physical/publication approval."""

import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

import pandas as pd
import pymupdf


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def audit():
    checks = []

    def check(name, passed, detail=None):
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    original = ROOT / "inputs/original/TEST_WILEY.zip"
    check("original archive identity", digest(original) ==
          "91c0728b70c316fa796abd7bf30e959a54bd0cf3828e07bcca3989ce5ee4535b")
    base = pd.read_csv(ROOT / "results/batch_v2/summary.csv")
    follow = pd.read_csv(ROOT / "results/followup_v1/summary.csv")
    for folder, receipt in (("batch_v2", "analysis_receipt.json"), ("followup_v1", "receipt.json")):
        check(folder + " summary identity", digest(ROOT / f"results/{folder}/summary.csv") ==
              read(f"results/{folder}/{receipt}")["summary_sha256"])
    check("primary count", len(base) == 460 and int(base.requests.sum()) == 22080)
    check("follow-up count", len(follow) == 300 and follow.group.value_counts().to_dict() ==
          {"application": 128, "native": 124, "control": 48})
    check("no resource leaks", not base.resource_leaks.any() and not follow.resource_leaks.any())
    frozen = read("results/followup_v1/environment.json")
    check("all follow-up frozen sources", all(digest(ROOT / p) == h for p, h in frozen["sources"].items()))
    core = ("config", "kernel", "network", "quantum", "routing", "transport", "workload", "experiments")
    baseline = read("results/batch_v2/environment.json")["sources"]
    check("eight primary scientific sources preserved", all(digest(ROOT / f"src/dequint/{p}.py") ==
          baseline[f"src/dequint/{p}.py"] for p in core))
    check("follow-up protocol preserved", digest(ROOT / "docs/FOLLOWUP_PROTOCOL.md") == frozen["followup_protocol_sha256"])
    with (ROOT / "qa/RESULT_LINEAGE_LEDGER.csv").open(newline="", encoding="utf-8") as stream:
        lineage = list(csv.DictReader(stream))
    check("760 traceable raw runs", len(lineage) == 760 and all(
        digest(ROOT / row["source"]) == row["sha256"] and (ROOT / row["raw_data"]).is_file()
        for row in lineage))
    primary_requests = sum(len(pd.read_csv(p)) for p in (ROOT / "results/batch_v2/runs").glob("*/requests.csv"))
    check("primary raw request coverage", primary_requests == 22080, primary_requests)
    for file, expected in (("branch_tests.xml", 162), ("followup_tests.xml", 203), ("final_branch_tests.xml", 203)):
        tests = ET.parse(ROOT / "results" / file).getroot()
        cases = tests.findall(".//testcase")
        check(file, len(cases) == expected and not tests.findall(".//failure") and
              not tests.findall(".//error") and not tests.findall(".//skipped"), len(cases))
    report_manifest = read("output/validation_reports/report_manifest.json")
    reports = report_manifest["reports"]
    check("eleven reports", len(reports) == 11 and {r["number"] for r in reports} == set(range(1, 12)))
    for report in reports:
        path = ROOT / report["path"]
        with pymupdf.open(path) as doc:
            text = "\n".join(page.get_text() for page in doc)
            check(f"report {report['number']} identity", digest(path) == report["sha256"] and
                  len(doc) == report["pages"] and not re.search(r"\b(?:TODO|TBD)\b", text))
            if report["number"] == 11:
                check("physical gap explicit", "PHYSICAL REQUIREMENT NOT SATISFIED" in text)
    check("report builder provenance", report_manifest["builder_sha256"] == digest(ROOT / "tools/build_validation_reports.py"))
    for receipt, key in (("manuscript/rendered/render_receipt.json", "page_checks"),
                         ("output/validation_reports/rendered/render_receipt.json", "checks")):
        rendered = read(receipt)
        check(receipt, all(not p["outside_page_words"] and not p.get("unresolved_markers", []) for p in rendered[key]))
    paper = ROOT / "manuscript/main.pdf"
    with pymupdf.open(paper) as doc:
        text = "\n".join(p.get_text() for p in doc)
        check("compiled manuscript", len(doc) == 9 and not re.search(r"\b(?:TODO|TBD|NaN)\b|\?\?", text))
        check("control attrition disclosed", "295/576" in text and "575/576" in text)
    log = (ROOT / "manuscript/main.log").read_text(errors="replace")
    check("no critical TeX diagnostics", not re.search(r"Overfull|Undefined control sequence|undefined references|Citation .+ undefined|^!", log, re.MULTILINE))
    correction = read("qa/final_followup_correction_review.json")
    check("independent correction closed", correction["disposition"] == "CLOSED" and not
          correction["remaining_p1_findings_in_correction"] and not correction["remaining_p2_findings_in_correction"])
    check("review covers current PDFs", all(digest(ROOT / row["path"]) == row["sha256"] for row in correction["inspected_pdfs"]))
    provenance = read("manuscript/followup_section_provenance.json")
    check("follow-up builder provenance", provenance["builder_sha256"] == digest(ROOT / "tools/build_followup_sections.py"))
    export = read("SeQUeNCe/research/dequint/EXPORT_MANIFEST.json")
    check("addon matches canonical source", all(digest(ROOT / p["path"]) == p["sha256"] and
          digest(ROOT / "SeQUeNCe/research/dequint" / p["path"]) == p["sha256"] for p in export["files"]))
    repo = ROOT / "SeQUeNCe"
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=repo, text=True).strip()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    changed = subprocess.check_output(["git", "diff", "--name-only", export["upstream_base"], "HEAD"], cwd=repo, text=True).splitlines()
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo, text=True).strip()
    check("local feature branch only", branch == "codex/dequint-rebuild" and not status and
          all(p.startswith("research/dequint/") for p in changed), {"branch": branch, "head": head})
    artifacts = [paper, ROOT / "manuscript/main.tex", ROOT / "results/final_branch_tests.xml",
                 ROOT / "qa/final_followup_review.json", ROOT / "qa/final_followup_correction_review.json",
                 ROOT / "output/validation_reports/report_manifest.json"]
    receipt = {"passed": all(c["passed"] for c in checks), "checks": checks,
               "artifacts_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in artifacts},
               "visual_inspection": "Main author inspected nine-page contact sheet and enlarged final result/control pages; all eleven reports' contact sheet and affected tables inspected. Independent correction review inspected the final affected PDF pages.",
               "security_scope": "Scoped new source/tests/tools/docs text scan found no token/private-key patterns, shell=True, eval/exec or os.system. No external writes, auth changes or paid execution; this is not exhaustive supply-chain certification.",
               "claim_limits": ["No physical prototype/relevant-environment validation", "No quality-term superiority established", "No O(log N) or physical-depth gain", "Application replay is timing-only", "Targeted prior art, not exhaustive novelty clearance", "Bounded research revision, not submission-ready certification"],
               "goal_outcome": "Implemented, tested and delivered evidence-grounded reconstruction; unsupported historical claims assessed and withdrawn, not manufactured."}
    (ROOT / "qa/final_delivery_audit.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"passed": receipt["passed"], "checks": len(checks),
                      "failures": [c for c in checks if not c["passed"]]}, indent=2))
    if not receipt["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    audit()
