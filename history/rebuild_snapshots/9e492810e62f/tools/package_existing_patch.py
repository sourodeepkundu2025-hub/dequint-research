"""Render and package the original-paper patch without changing old releases."""

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re
import zipfile

from PIL import Image, ImageDraw
import pymupdf


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "manuscript_existing_patch"
SOURCE = ROOT / "inputs/latest/DEQUINT_Wiley_Converted"
ORIGINAL = SOURCE / "dequint_wiley (2).tex"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render():
    output = PROJECT / "rendered"
    output.mkdir(exist_ok=True)
    checks, thumbs = [], []
    with pymupdf.open(PROJECT / "main.pdf") as pdf:
        for index, page in enumerate(pdf):
            path = output / f"page_{index+1:02d}.png"
            page.get_pixmap(matrix=pymupdf.Matrix(1.3,1.3),alpha=False).save(path)
            checks.append({"page":index+1,"outside_page_words":[w[4] for w in page.get_text("words")
                           if w[0]<-1 or w[1]<-1 or w[2]>page.rect.width+1 or w[3]>page.rect.height+1]})
            thumb = Image.open(path).convert("RGB")
            thumb.thumbnail((330,470))
            tile = Image.new("RGB",(350,500),"#e4e9eb")
            tile.paste(thumb,((350-thumb.width)//2,8))
            ImageDraw.Draw(tile).text((10,480),f"Page {index+1}",fill="black")
            thumbs.append(tile)
        first = pdf[0].get_text()
        count = len(pdf)
    contact = Image.new("RGB",(1400,500*((len(thumbs)+3)//4)),"white")
    for index, thumb in enumerate(thumbs):
        contact.paste(thumb,((index%4)*350,(index//4)*500))
    contact.save(output/"contact_sheet.png")
    original_text = ORIGINAL.read_text(encoding="utf-8")
    revised = (PROJECT/"main.tex").read_text(encoding="utf-8")
    headings = r"\\section\{([^}]+)\}"
    assets = [p for p in SOURCE.rglob("*") if p.is_file() and p.suffix.lower() in
              {".jpg",".jpeg",".png",".eps",".ttf",".otf"}]
    preserved = all((PROJECT/p.relative_to(SOURCE)).is_file() and
                    sha(p)==sha(PROJECT/p.relative_to(SOURCE)) for p in assets)
    manifest = {"original_source_sha256":sha(ORIGINAL),"revised_source_sha256":sha(PROJECT/"main.tex"),
                "pdf_sha256":sha(PROJECT/"main.pdf"),"pages":count,"page_checks":checks,
                "original_section_order_preserved":re.findall(headings,original_text)==re.findall(headings,revised),
                "original_figure_blocks_preserved":len(re.findall(r"\\begin\{figure\*?\}",original_text))==len(re.findall(r"\\begin\{figure\*?\}",revised)),
                "original_table_blocks_preserved":len(re.findall(r"\\begin\{table\*?\}",original_text))==len(re.findall(r"\\begin\{table\*?\}",revised)),
                "original_image_and_font_files_preserved":preserved,"preserved_asset_files":len(assets),
                "review_scope_notice_present":"Incremental author-review copy" in first,
                "scientific_status":"Incremental original-manuscript review patch; inherited numerical results remain unconsolidated; not submission-ready",
                "new_results_scope":"Native scheduler, abstract link provisioning and analytic Pauli endpoint-CNOT task; not native quantum optics or physical validation"}
    environment=json.loads((ROOT/"results/shortcut_v1/environment.json").read_text())
    receipt=json.loads((ROOT/"results/shortcut_v1/receipt.json").read_text())
    manifest["frozen_experiment_sources_match"]=all(sha(ROOT/p)==h for p,h in environment["sources"].items())
    manifest["experiment_summary_sha256"]=sha(ROOT/"results/shortcut_v1/summary.csv")
    manifest["experiment_receipt_matches"]=manifest["experiment_summary_sha256"]==receipt["summary_sha256"]
    manifest["result_tex_sha256"]=sha(PROJECT/"shortcut_results.tex")
    manifest["report_copyediting_scope"]="Generated result prose was manually copyedited and presented as a table; model/run sources and raw data remain frozen."
    if not manifest["frozen_experiment_sources_match"] or not manifest["experiment_receipt_matches"]:
        raise RuntimeError("Experiment freeze or raw-result identity changed")
    if not all(manifest[k] for k in ("original_section_order_preserved","original_figure_blocks_preserved",
                                    "original_table_blocks_preserved","original_image_and_font_files_preserved",
                                    "review_scope_notice_present")):
        raise RuntimeError("Original-paper preservation or review-label check failed")
    (ROOT/"qa/existing_patch_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    patch = "".join(difflib.unified_diff(original_text.splitlines(keepends=True),revised.splitlines(keepends=True),
                                        fromfile="supplied/dequint_wiley (2).tex",tofile="revised/main.tex"))
    (ROOT/"qa/existing_manuscript.patch").write_text(patch,encoding="utf-8")
    print(json.dumps({"pages":count,"preserved_assets":len(assets),"outside_words":sum(len(c["outside_page_words"]) for c in checks)}))


def package():
    destination=ROOT/"DEQUINT_existing_paper_quantum_shortcut_patch.zip"
    if destination.exists():
        raise RuntimeError("Preserve existing package; choose a new version")
    paths=[]
    for directory in (PROJECT,ROOT/"results/shortcut_v1"):
        paths.extend(p for p in directory.rglob("*") if p.is_file() and "rendered" not in p.parts
                     and not p.name.startswith("initial_page_") and p.suffix not in {".log",".aux",".out",".pag"}
                     and (p.suffix!=".tex" or p.name in {"main.tex","shortcut_extension.tex","shortcut_results.tex"})
                     and p.name!="wileyNJDv5_AMA.pdf")
    paths += [ORIGINAL, ROOT/"src/dequint/shortcut_probe.py",ROOT/"tests/test_shortcut_probe.py",
              ROOT/"tools/run_shortcut_investigation.py",Path(__file__),
              ROOT/"docs/SHORTCUT_EXTENSION_PROTOCOL.md",ROOT/"docs/EXISTING_PAPER_PATCH_PLAN.md",
              ROOT/"docs/CONTEXT_HANDOFF.md",ROOT/"docs/PROGRESS.md",
              ROOT/"results/shortcut_full_tests.xml",ROOT/"qa/shortcut_extension_review.json",
              ROOT/"results/shortcut_branch_tests.xml",ROOT/"qa/shortcut_review_actions.md",
              ROOT/"qa/shortcut_literature.csv",ROOT/"qa/existing_patch_manifest.json",ROOT/"qa/existing_manuscript.patch"]
    # Include the small existing implementation needed by the new probe, not a clone/venv.
    paths += list((ROOT/"src/dequint").glob("*.py"))
    paths += [ROOT/"pyproject.toml",ROOT/"requirements-lock-windows-py312.txt"]
    manifest={}
    with zipfile.ZipFile(destination,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(set(paths)):
            relative=path.relative_to(ROOT).as_posix()
            manifest[relative]=sha(path)
            archive.write(path,relative)
        archive.writestr("SHA256SUMS.json",json.dumps(manifest,indent=2))
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() or any(hashlib.sha256(archive.read(p)).hexdigest()!=h for p,h in manifest.items()):
            raise RuntimeError("Package integrity failed")
    receipt={"archive":str(destination),"sha256":sha(destination),"files":len(manifest),
             "bytes":destination.stat().st_size,"zip_integrity":"passed",
             "scope":"Original-paper incremental review patch, not final submission"}
    (ROOT/"existing_patch_receipt.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps(receipt,indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--package",action="store_true")
    args=parser.parse_args()
    render()
    if args.package:
        package()
