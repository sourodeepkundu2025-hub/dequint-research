"""Package owned code, original archive and accepted raw evidence; no private history."""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def package(destination=None, receipt_path=None):
    root = Path(__file__).resolve().parents[1]
    destination = Path(destination) if destination else root / "DEQUINT_SeQUeNCe_rebuild_2026-10-20_r2.zip"
    receipt_path = Path(receipt_path) if receipt_path else root / "release_receipt_r2.json"
    if destination.suffix.lower() != ".zip":
        raise ValueError("Destination must be a ZIP archive")
    if destination.exists():
        raise RuntimeError("Preserve existing release: choose a new explicit destination")
    if receipt_path.exists():
        raise RuntimeError("Preserve existing receipt: choose a new explicit destination")
    paths = [root / "README.md", root / "pyproject.toml", root / ".gitignore",
             root / "requirements-lock-windows-py312.txt"]
    for folder in ("src", "tests", "tools", "docs", "manuscript", "results/quantum_validation",
                   "results/native_reference", "results/batch_v2", "results/followup_v1",
                   "output/validation_reports", "qa", "inputs/original", "inputs/legacy_prototypes"):
        paths.extend(p for p in (root / folder).rglob("*") if p.is_file()
                     and "__pycache__" not in p.parts and "rendered" not in p.parts
                     and p.suffix not in {".pyc", ".aux", ".out", ".log", ".xdv"})
    paths += [root / "inputs/source_manifest.json", root / "results/branch_tests.xml",
              root / "results/followup_tests.xml", root / "results/final_branch_tests.xml",
              root / "manuscript/rendered/render_receipt.json",
              root / "output/validation_reports/rendered/render_receipt.json"]
    required = [root / "qa/final_delivery_audit.json", root / "qa/final_followup_review.json",
                root / "qa/final_followup_correction_review.json", root / "manuscript/main.pdf",
                root / "output/validation_reports/report_manifest.json"]
    if any(not path.is_file() for path in required):
        raise RuntimeError("Final delivery review/audit or requested PDF is missing")
    if not json.loads(required[0].read_text())["passed"]:
        raise RuntimeError("Final delivery audit did not pass")
    manifest = {}
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(set(paths)):
            relative = path.relative_to(root).as_posix()
            manifest[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            archive.write(path, relative)
        archive.writestr("SHA256SUMS.json", json.dumps(manifest, indent=2))
    with zipfile.ZipFile(destination) as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise RuntimeError(f"Corrupt packaged entry: {corrupt}")
        if len(archive.infolist()) != len(manifest) + 1:
            raise RuntimeError("Unexpected archive member count")
        for relative, expected in manifest.items():
            if hashlib.sha256(archive.read(relative)).hexdigest() != expected:
                raise RuntimeError(f"Packaged content hash mismatch: {relative}")
    receipt = {"archive": str(destination), "files": len(manifest), "bytes": destination.stat().st_size,
               "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(), "zip_integrity": "passed",
               "excluded": ["private chat history", "quarantined batch_v1", "unrelated research",
                            "upstream Git checkout (clone pinned source separately)"],
               "scientific_readiness": "working revision, not submission-ready certification"}
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.destination, args.receipt), indent=2))
