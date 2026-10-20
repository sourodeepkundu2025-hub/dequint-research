"""Capture the actual dependency resolution without embedding editable local paths."""

from pathlib import Path
import subprocess
import sys


root = Path(__file__).resolve().parents[1]
frozen = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
lines = [line for line in frozen.splitlines() if not line.startswith("-e ")
         and not line.startswith("# Editable")]
(root / "requirements-lock-windows-py312.txt").write_text(
    "# Observed Windows Python 3.12 environment; install this project separately.\n"
    + "\n".join(lines) + "\n", encoding="utf-8")
print(f"Captured {len(lines)} pinned package entries")
