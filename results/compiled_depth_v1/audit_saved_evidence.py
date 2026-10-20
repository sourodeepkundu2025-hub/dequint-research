"""Readback audit independent of the experiment's channel/scheduler code."""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import networkx as nx
import numpy as np


BASE = Path(__file__).resolve().parent
RUN = BASE / "run01"
ROOT = BASE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((RUN / "manifest.json").read_text())
    for name, expected in manifest.items():
        path = (RUN / name).resolve()
        assert path.is_relative_to(RUN.resolve()), name
        assert digest(path) == expected, name
    declaration = json.loads((RUN / "pre_run.json").read_text())
    receipt = json.loads((RUN / "receipt.json").read_text())
    assert declaration["sources_before"] == receipt["sources_after"]
    assert digest(RUN / "protocol_snapshot.md") == declaration["sources_before"]["docs/COMPILED_DEPTH_PROTOCOL.md"]
    current_drift = [name for name, expected in declaration["sources_before"].items()
                     if digest(ROOT / name) != expected]
    assert not current_drift, current_drift

    target = np.zeros(16, complex)
    # Little-endian physical output-control, output-target, reference-control,
    # reference-target, constructed without any project quantum helper.
    for a in (0, 1):
        for b in (0, 1):
            target[a + 2*(a ^ b) + 4*a + 8*b] = .5
    expected = np.outer(target, target.conj())
    max_error, min_eigenvalue = 0., 0.
    channels = list(RUN.glob("*/channel.json"))
    assert len(channels) == 18
    for path in channels:
        check = json.loads(path.read_text())
        rho = np.array(check["choi_real"]) + 1j*np.array(check["choi_imag"])
        error = float(np.max(np.abs(rho - expected)))
        max_error = max(max_error, error)
        eigenvalue = float(np.linalg.eigvalsh(rho).min())
        min_eigenvalue = min(min_eigenvalue, eigenvalue)
        assert error < 1e-9, path
        assert abs(np.trace(rho) - 1) < 1e-9, path
        assert np.max(np.abs(rho - rho.conj().T)) < 1e-9, path
        assert eigenvalue > -1e-9, path
        reference_marginal = np.trace(rho.reshape(4, 4, 4, 4), axis1=1, axis2=3)
        assert np.max(np.abs(reference_marginal - np.eye(4)/4)) < 1e-9, path

    schedules = list(RUN.glob("*/schedule_*.json"))
    assert len(schedules) == 108
    for path in schedules:
        saved = json.loads(path.read_text())
        graph = nx.DiGraph()
        last_wire, last_core, last_measure = {}, {}, {}
        for event in saved["events"]:
            index = event["event"]
            metric = saved["metric"]
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
                for core in {wire // 3 for wire in event["qubits"]}:
                    if core in last_core:
                        graph.add_edge(last_core[core], index)
                    last_core[core] = index
        finish = {}
        for index in nx.topological_sort(graph):
            start = max((finish[p] for p in graph.predecessors(index)), default=0)
            finish[index] = start + graph.nodes[index]["weight"]
            event = saved["events"][index]
            assert (event["start"], event["end"]) == (start, finish[index]), path
        assert saved["depth"] == max(finish.values(), default=0), path

    tests = ET.parse(BASE / "tests_initial.xml").getroot()
    assert sum(int(suite.get("tests", 0)) for suite in tests) == 18
    assert all(suite.get("failures") == "0" and suite.get("errors") == "0" for suite in tests)
    result = {"passed": True, "manifest_files_checked": len(manifest),
              "source_hashes_checked": len(declaration["sources_before"]),
              "current_source_drift": current_drift,
              "saved_channels_checked": len(channels), "saved_schedules_checked": len(schedules),
              "focused_tests": 18, "max_saved_choi_error": max_error,
              "minimum_choi_eigenvalue": min_eigenvalue,
              "audit_source_sha256": digest(Path(__file__)),
              "scope": "separate mathematical/readback audit; not external scientific approval"}
    (BASE / "readback_audit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
