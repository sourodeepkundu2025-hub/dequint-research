"""Export an inspectable, local-only addon snapshot into the authorized branch."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def export():
    root = Path(__file__).resolve().parents[1]
    checkout = root / "SeQUeNCe"
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=checkout, text=True).strip()
    if branch != "codex/dequint-rebuild":
        raise RuntimeError(f"Refusing export into unexpected branch {branch}")
    destination = checkout / "research" / "dequint"
    destination.mkdir(parents=True, exist_ok=True)
    sources = [root / "README.md", root / "pyproject.toml", root / ".gitignore",
               root / "requirements-lock-windows-py312.txt"]
    for folder, pattern in (("src", "*.py"), ("tests", "*.py"), ("docs", "*.md"),
                            ("tools", "*.py"), ("manuscript", "*.tex")):
        sources.extend(sorted((root / folder).rglob(pattern)))
    manifest = []
    for source in sources:
        relative = source.relative_to(root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Export copy hash mismatch")
        manifest.append({"path": relative.as_posix(), "sha256": digest})
    (destination / "EXPORT_MANIFEST.json").write_text(json.dumps({
        "purpose": "Local addon snapshot; no publication or upstream submission",
        "upstream_base": "88f92cca8aaa6dbf82bccc6a759465120afbdd34", "branch": branch,
        "files": manifest, "raw_results": "Retained in owning DEQUINT_rebuild/results; not duplicated here",
    }, indent=2), encoding="utf-8")
    return {"destination": str(destination), "files": len(manifest), "branch": branch}


if __name__ == "__main__":
    print(json.dumps(export(), indent=2))
