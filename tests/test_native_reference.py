"""Bounded integration checks of actual official SeQUeNCe components/protocols."""

import json
import subprocess

import numpy as np
import pytest
from sequence.constants import DENSITY_MATRIX_FORMALISM
from sequence.entanglement_management.generation import EntanglementGenerationA, EntanglementGenerationB
from sequence.entanglement_management.purification import PurificationProtocol
from sequence.entanglement_management.swapping import EntanglementSwappingA, EntanglementSwappingB
from sequence.kernel.quantum_manager import QuantumManager
from sequence.utils import metrics

import dequint.native_reference as native

from dequint.native_reference import (
    UPSTREAM_COMMIT, _native_settings, _purification_trial, _sequence_root, _swapping_trial, run_native_reference,
)


def _settings():
    return (QuantumManager.get_active_formalism(), EntanglementGenerationA.get_global_type(),
            EntanglementGenerationB.get_global_type(), PurificationProtocol.get_formalism(),
            EntanglementSwappingA.get_formalism(), EntanglementSwappingB.get_formalism())


@pytest.fixture(scope="module")
def reference(tmp_path_factory):
    path = tmp_path_factory.mktemp("native_reference")
    before = _settings()
    summary = run_native_reference(path, trials=8)
    assert before == _settings()
    return path, summary, json.loads((path / "native_raw.json").read_text())


def test_reference_evidence_and_provenance(reference):
    path, summary, rows = reference
    assert len(rows) == 32
    assert summary["native_execution"]
    assert not summary["whole_mesh_validated"] and not summary["hardware"]
    assert not summary["rate_agreement_certified"]
    assert summary["conditional_fidelity_checks_passed"]
    assert summary["all_models_observed_success"]
    assert summary == json.loads((path / "native_summary.json").read_text())
    provenance = json.loads((path / "native_provenance.json").read_text())
    assert provenance["version"] == "1.3.0"
    assert provenance["pinned_source_commit"] == UPSTREAM_COMMIT
    assert len(provenance["actual_head"]) == 40
    assert provenance["pinned_commit_is_ancestor"]
    assert all(row["matches"] for row in provenance["source_hashes"])
    assert (path / "native_trials.csv").stat().st_size > 0
    for model in ("generation", "teleportation", "bbpssw", "swapping"):
        result = summary["models"][model]
        assert result["trials"] == 8
        assert result["successes"] == sum(row["success"] for row in rows if row["model"] == model)
        assert result["observed_success_fraction"] == result["successes"] / 8
        assert result["max_fidelity_error"] < 1e-9
        low, high = result["wilson_95_interval"]
        assert 0 <= low <= high <= 1


def test_native_generation_real_photons_detectors_and_memory(reference):
    _, _, rows = reference
    for row in (row for row in rows if row["model"] == "generation"):
        assert row["protocol_classes"] == ["BarretKokA", "BarretKokA", "BarretKokB"]
        assert row["native_manager"] == "QuantumManagerKet"
        assert row["counters"]["photon_emissions"] in (2, 4)
        assert row["counters"]["classical_messages"] > 0
        assert row["counters"]["executed_events"] > 0
        assert sum(component["class"] == "Detector" for component in row["components"]) == 2
        if row["success"]:
            assert row["counters"]["photon_emissions"] == 4
            assert row["counters"]["detector_clicks"] >= 2
            assert row["state_fidelity"] == pytest.approx(1)
            assert row["latency_ps"] > 0
        else:
            assert row["state_fidelity"] is None


def test_native_teleportation_unknown_complex_input_and_feedforward(reference):
    _, _, rows = reference
    for row in (row for row in rows if row["model"] == "teleportation"):
        assert row["success"] and row["result_count"] == 1
        assert row["protocol_class"] == "TeleportProtocol"
        assert row["state_fidelity"] == pytest.approx(1, abs=1e-12)
        assert any(abs(value) > 0 for value in row["input_state"]["imag"])
        corrections = [event for event in row["events"] if event["kind"] == "classical_send"
                       and event["message"] == "TeleportMessage" and event["message_type"] == "MEASUREMENT_RESULT"]
        assert len(corrections) == 1
        correction = corrections[0]
        assert correction["x_flip"] in (0, 1) and correction["z_flip"] in (0, 1)
        assert correction["time_ps"] >= row["first_herald_time_ps"]
        assert row["completion_time_ps"] == correction["time_ps"] + 500_000_000
        assert row["latency_ps"] == row["completion_time_ps"] - row["reservation_start_ps"]
        assert row["counters"]["photon_emissions"] >= 4


def test_native_bbpssw_state_and_scalar_are_separate_measurements(reference):
    _, summary, rows = reference
    expected_p = 0.8**2 + 2 * 0.8 * 0.2 / 3 + 5 * (0.2 / 3)**2
    expected_f = (0.8**2 + (0.2 / 3)**2) / expected_p
    assert summary["models"]["bbpssw"]["expected_success_probability"] == pytest.approx(expected_p)
    for row in (row for row in rows if row["model"] == "bbpssw"):
        assert row["protocol_class"] == "BBPSSWCircuit"
        assert row["native_manager"] == "QuantumManagerDensity"
        assert row["success"] == (row["measurements"][0] == row["measurements"][1])
        assert row["latency_ps"] == 10_000_000
        if row["success"]:
            assert row["state_fidelity"] == pytest.approx(expected_f, abs=1e-12)
            assert row["metadata_fidelity"] == pytest.approx(expected_f, abs=1e-12)
            matrix = np.array(row["output_state"]["real"]) + 1j * np.array(row["output_state"]["imag"])
            assert np.trace(matrix).real == pytest.approx(1)
            # The native circuit does not twirl: non-Phi+ Bell weights remain unequal.
            assert not np.allclose(np.sort(np.linalg.eigvalsh(matrix)),
                                   np.sort([expected_f] + [(1 - expected_f) / 3] * 3))
        else:
            assert row["state_fidelity"] is None and row["metadata_fidelity"] is None


def test_native_swapping_reports_scalar_state_discrepancy(reference):
    _, summary, rows = reference
    assert summary["known_discrepancies"]
    for row in (row for row in rows if row["model"] == "swapping"):
        assert row["native_manager"] == "QuantumManagerDensity"
        assert row["configured_success_probability"] == 0.6
        assert row["latency_ps"] == 10_000_000
        if row["success"]:
            assert row["state_fidelity"] == pytest.approx(0.8 * 0.9 + 0.2 * 0.1 / 3)
            assert row["metadata_fidelity"] == pytest.approx(0.8 * 0.9)
            assert row["state_fidelity"] - row["metadata_fidelity"] == pytest.approx(0.2 * 0.1 / 3)
        else:
            assert row["state_fidelity"] is None


def test_native_swapping_certain_success_and_failure():
    with _native_settings():
        for probability in (0, 1):
            result = _swapping_trial([13, 17, 19], success_probability=probability)
            assert result["success"] == bool(probability)
            if probability:
                assert result["state_fidelity"] == pytest.approx(0.7266666666666667)


def test_native_threshold_limitation_is_not_hidden():
    before = _settings()
    with pytest.raises(AssertionError, match="too low"):
        with _native_settings():
            _purification_trial([7, 11], fidelity=0.5)
    assert _settings() == before


def test_native_global_selectors_and_time_provider_restored():
    before = _settings()
    provider = getattr(metrics, "time_provider", None)
    with _native_settings():
        QuantumManager.set_global_manager_formalism(DENSITY_MATRIX_FORMALISM)
    assert _settings() == before
    assert getattr(metrics, "time_provider", None) is provider


def test_native_reference_reproducible(tmp_path):
    first = run_native_reference(tmp_path / "first", seed=817, trials=2)
    second = run_native_reference(tmp_path / "second", seed=817, trials=2)
    assert first == second
    assert json.loads((tmp_path / "first/native_raw.json").read_text()) == json.loads(
        (tmp_path / "second/native_raw.json").read_text())


@pytest.mark.parametrize("kwargs", [{"trials": 0}, {"trials": -1}, {"trials": 257},
    {"trials": 1.5}, {"trials": True}, {"seed": -1}, {"seed": 1.5}, {"seed": True}])
def test_native_reference_rejects_invalid_bounds_without_output(tmp_path, kwargs):
    destination = tmp_path / "not_created"
    with pytest.raises(ValueError):
        run_native_reference(destination, **kwargs)
    assert not destination.exists()


@pytest.mark.parametrize("layout", ["parent_project", "research_addon"])
def test_sequence_root_both_supported_layouts(tmp_path, monkeypatch, layout):
    monkeypatch.delenv("DEQUINT_SEQUENCE_ROOT", raising=False)
    root = tmp_path / "project/SeQUeNCe"
    timeline = root / "sequence/kernel/timeline.py"
    timeline.parent.mkdir(parents=True)
    timeline.touch()
    if layout == "parent_project":
        start = tmp_path / "project/src/dequint/native_reference.py"
    else:
        start = root / "research/dequint/src/dequint/native_reference.py"
    assert _sequence_root(start) == root


def test_sequence_root_override_and_invalid_path(tmp_path, monkeypatch):
    timeline = tmp_path / "official/sequence/kernel/timeline.py"
    timeline.parent.mkdir(parents=True)
    timeline.touch()
    monkeypatch.setenv("DEQUINT_SEQUENCE_ROOT", str(tmp_path / "official"))
    assert _sequence_root(tmp_path / "elsewhere") == timeline.parents[2]
    monkeypatch.setenv("DEQUINT_SEQUENCE_ROOT", str(tmp_path / "invalid"))
    with pytest.raises(ValueError, match="DEQUINT_SEQUENCE_ROOT"):
        _sequence_root()


def test_provenance_accepts_descendant_and_compares_pinned_blobs(monkeypatch):
    # Simulate only Git's descendant response; pinned blobs and installed sources
    # are still read and compared for real. No checkout commits are created.
    real_run = subprocess.run
    descendant = "a" * 40
    calls = []

    def git(args, **kwargs):
        calls.append(args)
        if "rev-parse" in args:
            return subprocess.CompletedProcess(args, 0, stdout=descendant + "\n", stderr="")
        if "merge-base" in args:
            assert args[-2:] == [UPSTREAM_COMMIT, descendant]
            return subprocess.CompletedProcess(args, 0, stdout=b"", stderr=b"")
        return real_run(args, **kwargs)

    monkeypatch.setattr(native.subprocess, "run", git)
    result = native._provenance(_sequence_root())
    assert result["actual_head"] == descendant
    assert result["pinned_source_commit"] == UPSTREAM_COMMIT
    assert all(row["matches"] for row in result["source_hashes"])
    assert any("diff" in call and call[call.index("diff") + 1] == UPSTREAM_COMMIT for call in calls)


def test_provenance_rejects_unrelated_head(monkeypatch):
    real_run = subprocess.run

    def git(args, **kwargs):
        if "merge-base" in args:
            return subprocess.CompletedProcess(args, 1, stdout=b"", stderr=b"")
        return real_run(args, **kwargs)

    monkeypatch.setattr(native.subprocess, "run", git)
    with pytest.raises(RuntimeError, match="descend"):
        native._provenance(_sequence_root())
