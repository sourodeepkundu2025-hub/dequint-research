"""Verify the public byte identities and, optionally, saved scientific evidence.

Privacy-redacted records retain original identities explicitly; this verifier
checks public bytes before using any original identity in a historical manifest.
No frozen file is rewritten and no cloud/hardware service is contacted.
"""

import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
APPROVED_PRIVACY = {
    "results/compiled_depth_v1/DELIVERY.md": (
        "f0d3e9293f542ea97c181a876e595504dc8e8b7808b0337b2bd0fc4cbb23d089",
        "d73bc9a23d16b5e489a2c12a823b997d6581bdcd510a196d8b7fb2743d641086"),
    "results/compiled_depth_v1/run01/pre_run.json": (
        "c502105851b56abc2baa348a89f22c145cebeb444c83e8988a353ad982c03d00",
        "a7fa3cf80800f87a2a698f93291175fce761dab3127d193dd3fe4f4d766350b9"),
    "results/native_reference/native_provenance.json": (
        "f5306cfbb386b0e00050eb88835c41d357ee623f0549c75e3bbf20d8eaa46409",
        "b273bcccf5409b54c4df99f5782ce67560b4eadf9dd1b9673b06cf4d6fd17bc1"),
    "results/review_supplement_v1/EVIDENCE_HANDOFF.md": (
        "8a6fd42d28ef286777124c6e66e05152f0a4b67dec9dbcadfb972b0322100b6c",
        "191cb4f1f0afa36f5a46ae39189e51c4b5cc9d6c7533f93cd5d6f9b78358db2d"),
    "results/review_supplement_v1/freeze.json": (
        "5a3c3f0a8a65525812223b0d74d8638f362f232823823504110075073b4fabf4",
        "d8b6094bac7bb0abe82e1cf00c5eaa58d028345d2ee1dcc65c08cb8b5817c97f"),
    "results/review_supplement_v1/tests_pre_freeze.xml": (
        "a0337e8f180334c1e65258b545f5255452f2c6e5819cc9db6c68eda842516325",
        "696211280c24d43006f20df72097d3767ec192b2ad4e5843063c5c27983f0415"),
    "results/review_supplement_v1/tests_pre_freeze_r2.xml": (
        "4e8ecd41090d8e211a0a3d40f1e1bc5d9d7d9130633c40e221daf2e0526591b7",
        "7d45828a24d2d830300aefdf57c95f330249732df1bce140008e2023af981adb"),
}
PACKAGING_FILES = {"PKG-INFO", "SOURCES.txt", "dependency_links.txt", "requires.txt", "top_level.txt"}
APPROVED_RELOCATIONS = {f"src/dequint_rebuild.egg-info/{name}": f"history/frozen_packaging_metadata/{name}"
                        for name in PACKAGING_FILES}


def require_assertions():
    if sys.flags.optimize or not __debug__:
        raise RuntimeError("Optimized Python execution is not supported: scientific assertions must remain active")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or Path(relative).is_absolute():
        raise ValueError(f"Path outside snapshot: {relative}")
    return path


class Snapshot:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.hashes = json.loads((self.root / "PUBLIC_SHA256SUMS.json").read_text(encoding="utf-8"))
        entries = json.loads((self.root / "PUBLICATION_PROVENANCE.json").read_text(encoding="utf-8"))["files"]
        self.origins = {}
        privacy_seen = set()
        for entry in entries:
            original, public = entry["original_sha256"], entry["public_sha256"]
            changed = original != public
            if entry["privacy_redacted"] != changed:
                raise ValueError(f"Inconsistent privacy flag: {entry['path']}")
            if changed:
                if APPROVED_PRIVACY.get(entry["path"]) != (original, public):
                    raise ValueError(f"Unapproved privacy identity exception: {entry['path']}")
                privacy_seen.add(entry["path"])
            if entry["origin"].startswith("DEQUINT_rebuild/"):
                key = entry["origin"].removeprefix("DEQUINT_rebuild/")
                if entry["path"] != APPROVED_RELOCATIONS.get(key, key):
                    raise ValueError(f"Unapproved path relocation: {key}")
                if key in self.origins:
                    raise ValueError(f"Duplicate canonical provenance: {key}")
                self.origins[key] = entry
        if privacy_seen != set(APPROVED_PRIVACY):
            raise ValueError("Missing approved privacy records")

    def verify_files(self):
        for relative, expected in self.hashes.items():
            path = safe_path(self.root, relative)
            if not path.is_file() or digest(path) != expected:
                raise ValueError(f"Public snapshot mismatch: {relative}")
        entries = json.loads((self.root / "PUBLICATION_PROVENANCE.json").read_text(encoding="utf-8"))["files"]
        for entry in entries:
            if self.hashes.get(entry["path"]) != entry["public_sha256"]:
                raise ValueError(f"Conflicting publication provenance: {entry['path']}")
        return len(self.hashes)

    def original_identity(self, relative, expected=None):
        record = self.origins.get(relative)
        if record is None:
            raise ValueError(f"Missing original/public mapping: {relative}")
        path = safe_path(self.root, record["path"])
        if digest(path) != record["public_sha256"]:
            raise ValueError(f"Public bytes changed: {relative}")
        identity = record["original_sha256"]
        if expected is not None and identity != expected:
            raise ValueError(f"Historical identity mismatch: {relative}")
        return identity

    def verify_lineage(self):
        with (self.root / "qa/FINAL_RESULT_LINEAGE_LEDGER.csv").open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != 1258 or len({(r["experiment"], r["run_id"]) for r in rows}) != 1258:
            raise ValueError("Expected 1,258 unique network/application/circuit records")
        for row in rows:
            for path_key, hash_key in (("source", "sha256"), ("raw_data", "raw_sha256"),
                                       ("event_trace", "event_trace_sha256"),
                                       ("raw_manifest", "raw_manifest_sha256")):
                if row[path_key]:
                    self.original_identity(row[path_key], row[hash_key])
        if any(r["experiment"] == "batch_v1" for r in rows):
            raise ValueError("Quarantined batch appeared in accepted scientific lineage")
        return len(rows)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_transport(snapshot):
    require_assertions()
    root = snapshot.root
    output = root / "results/review_supplement_v1"
    read = lambda path: json.loads(path.read_text(encoding="utf-8"))
    freeze = read(output / "freeze.json")
    for name, expected in freeze["source_sha256"].items():
        snapshot.original_identity(name, expected)
    for name, expected in freeze["protected_result_sha256"].items():
        snapshot.original_identity(name, expected)
    snapshot.original_identity("results/review_supplement_v1/run_plan.json", freeze["plan_sha256"])
    runner = load_module(root / "tools/run_review_supplement.py", "dequint_public_transport_audit")
    plan = read(output / "run_plan.json")
    if plan != runner.design() or len(plan) != 48:
        raise ValueError("Transport design mismatch")
    records = []
    freeze_original = snapshot.original_identity("results/review_supplement_v1/freeze.json")
    for item in plan:
        directory = output / "runs" / item["run_id"]
        summary, rows, audit = runner.reconcile_run(directory)
        started = read(directory / "started.json")
        assert started["freeze_sha256"] == freeze_original
        assert started["started_at_utc"] >= freeze["frozen_at_utc"]
        assert summary["design"] == item and summary["config"] == item["config"]
        assert summary["seed"] == item["seed"] and summary["run_id"] == item["run_id"]
        saved = freeze["workloads"][f"{item['offered_rate_s']}:{item['seed']}"]
        assert digest(output / saved["path"]) == saved["raw_sha256"]
        requests = read(output / saved["path"])
        assert len(rows) == len(requests)
        assert all(all(row[key] == request[key] for key in request) for row, request in zip(rows, requests))
        assert summary["workload_sha256"] == saved["workload_sha256"]
        records.append((summary, rows, audit))
    assert runner.aggregate(records) == read(output / "analysis.json")
    receipt = read(output / "receipt.json")
    assert digest(output / "analysis.json") == receipt["analysis_sha256"]
    assert digest(output / "REPORT.md") == receipt["report_sha256"]
    assert freeze_original == receipt["freeze_sha256"]
    return {"runs": len(records), "offered": sum(s["requests"] for s, _, _ in records),
            "protected_original_identities": len(freeze["protected_result_sha256"]),
            "qualified": sum(s["quality_qualified"] for s, _, _ in records),
            "completed": sum(s["completed"] for s, _, _ in records)}


def verify_compiled(snapshot):
    require_assertions()
    import networkx as nx
    import numpy as np

    base = snapshot.root / "results/compiled_depth_v1/run01"
    read = lambda path: json.loads(path.read_text(encoding="utf-8"))
    manifest = read(base / "manifest.json")
    for relative, expected in manifest.items():
        name = f"results/compiled_depth_v1/run01/{relative}"
        snapshot.original_identity(name, expected)
    declaration, receipt = read(base / "pre_run.json"), read(base / "receipt.json")
    assert declaration["sources_before"] == receipt["sources_after"]
    for name, expected in declaration["sources_before"].items():
        snapshot.original_identity(name, expected)
    assert digest(base / "protocol_snapshot.md") == declaration["sources_before"]["docs/COMPILED_DEPTH_PROTOCOL.md"]
    target = np.zeros(16, complex)
    for a in (0, 1):
        for b in (0, 1):
            target[a + 2*(a ^ b) + 4*a + 8*b] = .5
    expected = np.outer(target, target.conj())
    channels = list(base.glob("*/channel.json"))
    assert len(channels) == 18
    errors = []
    for path in channels:
        check = read(path)
        rho = np.array(check["choi_real"]) + 1j*np.array(check["choi_imag"])
        errors.append(float(np.max(np.abs(rho - expected))))
        assert errors[-1] < 1e-9 and abs(np.trace(rho)-1) < 1e-9
        assert np.max(np.abs(rho-rho.conj().T)) < 1e-9
        assert np.linalg.eigvalsh(rho).min() > -1e-9
        marginal = np.trace(rho.reshape(4, 4, 4, 4), axis1=1, axis2=3)
        assert np.max(np.abs(marginal-np.eye(4)/4)) < 1e-9
    schedules = list(base.glob("*/schedule_*.json"))
    assert len(schedules) == 108
    for path in schedules:
        saved = read(path)
        graph = nx.DiGraph()
        last_wire, last_core, last_measure = {}, {}, {}
        for event in saved["events"]:
            index, metric = event["event"], saved["metric"]
            weight = int(metric == "instrument" or event["name"] == "cx" or
                         (metric == "quantum" and event["name"] == "u"))
            assert event["weight"] == weight
            graph.add_node(index, weight=weight)
            for wire in event["qubits"]:
                if wire in last_wire:
                    graph.add_edge(last_wire[wire], index)
                last_wire[wire] = index
            if event["condition_bit"] is not None:
                graph.add_edge(last_measure[event["condition_bit"]], index)
            for bit in event["classical_output"]:
                last_measure[bit] = index
            if saved["concurrency"] == "one_primitive_per_core":
                for core in {wire//3 for wire in event["qubits"]}:
                    if core in last_core:
                        graph.add_edge(last_core[core], index)
                    last_core[core] = index
        finish = {}
        for index in nx.topological_sort(graph):
            start = max((finish[p] for p in graph.predecessors(index)), default=0)
            finish[index] = start + graph.nodes[index]["weight"]
            event = saved["events"][index]
            assert (event["start"], event["end"]) == (start, finish[index])
        assert saved["depth"] == max(finish.values(), default=0)
    return {"channels": len(channels), "schedules": len(schedules), "max_choi_error": max(errors)}


def main():
    require_assertions()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scientific", action="store_true", help="Also reconcile transport and compiled evidence")
    args = parser.parse_args()
    snapshot = Snapshot()
    output = {"public_files_verified": snapshot.verify_files(), "lineage_records": snapshot.verify_lineage(),
              "scope": "snapshot integrity, not physical validation or a new full-study execution"}
    if args.scientific:
        output["transport"] = verify_transport(snapshot)
        output["compiled"] = verify_compiled(snapshot)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
