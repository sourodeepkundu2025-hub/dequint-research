"""Package owned code, original archive and accepted raw evidence; no private history."""

import hashlib
import json
from pathlib import Path
import zipfile


def package():
    root = Path(__file__).resolve().parents[1]
    destination = root / "DEQUINT_SeQUeNCe_rebuild_2026-10-20.zip"
    if destination.exists():
        raise RuntimeError("Preserve existing release: choose a new explicit destination")
    paths = [root / "README.md", root / "pyproject.toml", root / "requirements-lock-windows-py312.txt"]
    for folder in ("src", "tests", "tools", "docs", "manuscript", "results/quantum_validation",
                   "results/native_reference", "results/batch_v2", "inputs/original", "inputs/legacy_prototypes"):
        paths.extend(p for p in (root / folder).rglob("*") if p.is_file()
                     and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".aux", ".out", ".log", ".xdv"})
    paths += [root / "inputs/source_manifest.json", root / "results/branch_tests.xml"]
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
    receipt = {"archive": str(destination), "files": len(manifest), "bytes": destination.stat().st_size,
               "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(), "zip_integrity": "passed",
               "excluded": ["private chat history", "quarantined batch_v1", "unrelated research",
                            "upstream Git checkout (clone pinned source separately)"],
               "scientific_readiness": "working revision, not submission-ready certification"}
    (root / "release_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


if __name__ == "__main__":
    print(json.dumps(package(), indent=2))
