"""Refresh only the owned addon on the existing local feature branch."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT/"SeQUeNCe"
DEST=REPO/"research/dequint"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    branch=subprocess.check_output(["git","branch","--show-current"],cwd=REPO,text=True).strip()
    if branch!="codex/dequint-quantum-shortcuts":
        raise RuntimeError("Refuse export outside the approved local feature branch")
    paths=[]
    for folder in ("src/dequint","tests","tools"):
        paths += list((ROOT/folder).glob("*.py"))
    for name in ("COMPILED_DEPTH_PROTOCOL.md","REVIEW_SUPPLEMENT_PROTOCOL.md","REVIEW_CLOSURE_REPRODUCE.md","REVIEW_CLOSURE_PLAN.md","01_CONTRACTS.md","PROGRESS.md","CONTEXT_HANDOFF.md"):
        paths.append(ROOT/"docs"/name)
    paths += [p for p in (ROOT/"manuscript_existing_patch").glob("*.tex") if p.name=="main.tex" or p.name.startswith(("revision_","shortcut_","compiled_depth_","review_supplement_"))]
    paths += [ROOT/"manuscript_existing_patch/main.pdf",ROOT/"manuscript_existing_patch/README.md"]
    for name in ("FINAL_CLAIM_EVIDENCE_MATRIX.csv","FINAL_RESULT_LINEAGE_LEDGER.csv","FINAL_FIGURE_TABLE_LEDGER.csv","FINAL_REVIEWER_CLOSURE_LEDGER.json","FINAL_REVIEWER_CLOSURE_LEDGER.csv","FINAL_INDEPENDENT_REVIEW.json"):
        paths.append(ROOT/"qa"/name)
    manifest={}
    for path in sorted(set(paths)):
        target=DEST/path.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
        assert sha(target)==sha(path)
        manifest[path.relative_to(ROOT).as_posix()]=sha(path)
    receipt={"branch":branch,"upstream_base":"88f92cca8aaa6dbf82bccc6a759465120afbdd34",
             "files":manifest,"scope":"Owned addon copy only; original evidence stays canonical outside clone; no upstream edit or remote publication"}
    (DEST/"REVIEW_REVISION_EXPORT.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    (ROOT/"qa/REVIEW_REVISION_EXPORT.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(f"Verified{len(manifest)}owned addon files on{branch}; no remote write")


if __name__=="__main__":
    main()
