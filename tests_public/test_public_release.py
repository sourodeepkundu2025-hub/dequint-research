"""Publication verifier regressions, separate from the frozen scientific suite."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SPEC = importlib.util.spec_from_file_location("public_verifier", Path(__file__).resolve().parents[1] /
                                              "tools/verify_public_release.py")
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def fixture_snapshot(tmp_path, monkeypatch):
    original, public = b'private path', b'<LOCAL_HOME>'
    path = tmp_path / "environment.json"
    path.write_bytes(public)
    sha = lambda b: hashlib.sha256(b).hexdigest()
    record = {"path": "environment.json", "origin": "DEQUINT_rebuild/environment.json",
              "original_sha256": sha(original), "public_sha256": sha(public), "privacy_redacted": True}
    monkeypatch.setattr(verifier, "APPROVED_PRIVACY", {"environment.json": (sha(original), sha(public))})
    (tmp_path / "PUBLICATION_PROVENANCE.json").write_text(json.dumps({"files": [record]}))
    (tmp_path / "PUBLIC_SHA256SUMS.json").write_text(json.dumps({"environment.json": sha(public)}))
    return verifier.Snapshot(tmp_path), record


def test_explicit_privacy_identity_is_not_public_digest(tmp_path, monkeypatch):
    snapshot, record = fixture_snapshot(tmp_path, monkeypatch)
    assert snapshot.verify_files() == 1
    assert snapshot.original_identity("environment.json", record["original_sha256"]) == record["original_sha256"]
    assert record["original_sha256"] != record["public_sha256"]


def test_tampered_public_bytes_fail_even_with_original_identity(tmp_path, monkeypatch):
    snapshot, record = fixture_snapshot(tmp_path, monkeypatch)
    (tmp_path / "environment.json").write_text("tampered")
    with pytest.raises(ValueError, match="snapshot mismatch"):
        snapshot.verify_files()
    with pytest.raises(ValueError, match="bytes changed"):
        snapshot.original_identity("environment.json", record["original_sha256"])


def test_wrong_original_hash_and_missing_mapping_fail(tmp_path, monkeypatch):
    snapshot, _ = fixture_snapshot(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="Historical identity"):
        snapshot.original_identity("environment.json", "0"*64)
    with pytest.raises(ValueError, match="Missing original"):
        snapshot.original_identity("absent.json")


def test_outside_snapshot_rejected(tmp_path):
    with pytest.raises(ValueError, match="outside snapshot"):
        verifier.safe_path(tmp_path, "../private.txt")


def test_unapproved_redaction_is_rejected(tmp_path, monkeypatch):
    fixture_snapshot(tmp_path, monkeypatch)
    monkeypatch.setattr(verifier, "APPROVED_PRIVACY", {})
    with pytest.raises(ValueError, match="Unapproved privacy identity"):
        verifier.Snapshot(tmp_path)


def test_unapproved_relocation_is_rejected(tmp_path, monkeypatch):
    fixture_snapshot(tmp_path, monkeypatch)
    path = tmp_path / "PUBLICATION_PROVENANCE.json"
    document = json.loads(path.read_text())
    document["files"][0]["origin"] = "DEQUINT_rebuild/scientific_data.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="Unapproved path relocation"):
        verifier.Snapshot(tmp_path)


def test_privacy_flag_cannot_hide_byte_difference(tmp_path, monkeypatch):
    fixture_snapshot(tmp_path, monkeypatch)
    path = tmp_path / "PUBLICATION_PROVENANCE.json"
    document = json.loads(path.read_text())
    document["files"][0]["privacy_redacted"] = False
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="Inconsistent privacy flag"):
        verifier.Snapshot(tmp_path)


def test_approved_path_cannot_authorize_a_different_digest(tmp_path, monkeypatch):
    fixture_snapshot(tmp_path, monkeypatch)
    path = tmp_path / "PUBLICATION_PROVENANCE.json"
    document = json.loads(path.read_text())
    document["files"][0]["original_sha256"] = "0"*64
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="Unapproved privacy identity"):
        verifier.Snapshot(tmp_path)


@pytest.mark.parametrize("optimized_environment", [False, True])
def test_optimized_execution_cannot_report_success(optimized_environment):
    env = dict(os.environ)
    command = [sys.executable]
    if optimized_environment:
        env["PYTHONOPTIMIZE"] = "1"
    else:
        command.append("-O")
    command += [str(Path(verifier.__file__)), "--scientific"]
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    assert result.returncode != 0
    assert "Optimized Python execution is not supported" in result.stderr
