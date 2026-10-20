"""Physical invariants and independent, exact Qiskit primitive regression tests."""

import json

import numpy as np
import pytest
from qiskit.quantum_info import DensityMatrix, Operator, Pauli

from dequint.quantum import (
    age_channel, bbpssw, compose_pauli, dephasing_channel,
    gate_average_fidelity, gate_process_fidelity, identity_channel,
    pauli_depolarizing, werner_channel,
)
from dequint.quantum_validation import (
    bbpssw_density, cnot_process_check, run_validation, teleportation_density,
)


def assert_distribution(channel):
    assert channel.shape == (4,)
    assert np.all(np.isfinite(channel))
    assert np.all(channel >= 0)
    assert np.sum(channel) == pytest.approx(1, abs=1e-12)


def test_identity_and_probability_channels():
    identity = identity_channel()
    identity[0] = 0
    np.testing.assert_array_equal(identity_channel(), [1, 0, 0, 0])
    for fidelity in np.linspace(0, 1, 21):
        assert_distribution(werner_channel(fidelity))
        np.testing.assert_allclose(werner_channel(fidelity), pauli_depolarizing(1 - fidelity))
    np.testing.assert_allclose(werner_channel(0.25), [0.25] * 4)


@pytest.mark.parametrize("i", range(4))
@pytest.mark.parametrize("j", range(4))
def test_pauli_convolution_against_matrix_multiplication(i, j):
    first, second = np.eye(4)[i], np.eye(4)[j]
    labels = "IXYZ"
    actual = Operator(Pauli(labels[j])).data @ Operator(Pauli(labels[i])).data
    # Identify the matrix product by Hilbert-Schmidt overlap, ignoring phase.
    expected = np.array([abs(np.trace(Operator(Pauli(p)).data.conj().T @ actual)) ** 2 / 4
                         for p in labels])
    np.testing.assert_allclose(compose_pauli(first, second), expected, atol=1e-14)


def test_convolution_invariants_and_no_mutation():
    rng = np.random.default_rng(372)
    for _ in range(30):
        a, b, c = rng.dirichlet(np.ones(4), size=3)
        before = a.copy()
        assert_distribution(compose_pauli(a, b))
        np.testing.assert_allclose(compose_pauli(a, identity_channel()), a)
        np.testing.assert_allclose(compose_pauli(a, b), compose_pauli(b, a))
        np.testing.assert_allclose(compose_pauli(compose_pauli(a, b), c),
                                   compose_pauli(a, compose_pauli(b, c)))
        np.testing.assert_array_equal(before, a)
    np.testing.assert_array_equal(compose_pauli([0, 1, 0, 0], [0, 1, 0, 0]), [1, 0, 0, 0])


def test_dephasing_coherence_semigroup_and_endpoints():
    for duration, t2 in ((0, 1), (1e-15, 3), (1, 2), (1e300, 1e-300), (1, np.inf)):
        channel = dephasing_channel(duration, t2)
        assert_distribution(channel)
        coherence = np.exp(-duration / t2)
        assert channel[0] - channel[3] == pytest.approx(coherence)
    assert dephasing_channel(1e-15, 3)[3] > 0
    np.testing.assert_array_equal(dephasing_channel(5, np.inf), identity_channel())
    np.testing.assert_allclose(dephasing_channel(1e300, 1e-300), [0.5, 0, 0, 0.5])
    np.testing.assert_allclose(compose_pauli(dephasing_channel(0.3, 2), dephasing_channel(0.7, 2)),
                               dephasing_channel(1, 2))
    np.testing.assert_allclose(age_channel(age_channel(werner_channel(0.9), 0.4, 3), 0.4, 3),
                               age_channel(werner_channel(0.9), 0.8, 3))


@pytest.mark.parametrize("value", [-1, 1.01, np.nan, np.inf, -np.inf, True, "0.5", 0.5j, None])
def test_invalid_probabilities(value):
    for function in (werner_channel, pauli_depolarizing, bbpssw):
        with pytest.raises(ValueError):
            function(value)
    if value is not None:
        with pytest.raises(ValueError):
            bbpssw(0.7, value)
    with pytest.raises(ValueError):
        gate_process_fidelity(identity_channel(), identity_channel(), value)


@pytest.mark.parametrize("channel", [[], [1, 0, 0], [[1, 0, 0, 0]], [0.1] * 4,
    [1.1, -0.1, 0, 0], [np.nan, 0, 0, 1], [np.inf, 0, 0, 0],
    [1 + 0j, 0, 0, 0], ["1", "0", "0", "0"], [True, False, False, False], None])
def test_invalid_channels(channel):
    for args in ((channel, identity_channel()), (identity_channel(), channel)):
        with pytest.raises(ValueError):
            compose_pauli(*args)
        with pytest.raises(ValueError):
            gate_process_fidelity(*args)
        with pytest.raises(ValueError):
            gate_average_fidelity(*args)
    if channel is not None:
        for keyword in ("post_a", "post_b"):
            with pytest.raises(ValueError):
                gate_process_fidelity(identity_channel(), identity_channel(), **{keyword: channel})
            with pytest.raises(ValueError):
                gate_average_fidelity(identity_channel(), identity_channel(), **{keyword: channel})
    with pytest.raises(ValueError):
        age_channel(channel, 1, 2)


@pytest.mark.parametrize("duration,t2", [(-1, 1), (np.inf, 1), (np.nan, 1), (1, 0),
    (1, -1), (1, -np.inf), (1, np.nan), (True, 1), (1, "2")])
def test_invalid_dephasing(duration, t2):
    with pytest.raises(ValueError):
        dephasing_channel(duration, t2)
    with pytest.raises(ValueError):
        age_channel(identity_channel(), duration, t2)


def test_bbpssw_threshold_and_invariants():
    assert bbpssw(1) == pytest.approx((1, 1))
    assert bbpssw(0.5) == pytest.approx((0.5, 5 / 9))
    assert bbpssw(0.25) == pytest.approx((0.25, 0.5))
    for f in np.linspace(0.501, 0.999, 30):
        conditional, probability = bbpssw(f)
        assert f < conditional <= 1
        assert 0 < probability <= 1
    for a in np.linspace(0, 1, 11):
        for b in np.linspace(0, 1, 11):
            conditional, probability = bbpssw(a, b)
            assert 0 <= conditional <= 1
            assert 0 < probability <= 1
            assert bbpssw(a, b) == pytest.approx(bbpssw(b, a))


@pytest.mark.parametrize("a,b", [(1, 1), (0.5, 0.5), (0.25, 0.25), (0, 0),
                                 (0.9, 0.65), (0.2, 0.95), (1, 0)])
def test_bbpssw_independent_bilateral_cnot_and_twirl(a, b):
    fidelity, probability, untwirled, twirled, branches = bbpssw_density(a, b)
    assert (fidelity, probability) == pytest.approx(bbpssw(a, b), abs=1e-12)
    assert sum(branch["probability"] for branch in branches) == pytest.approx(1)
    for branch in branches:
        if branch["accepted"]:
            assert branch["probability"] == pytest.approx(probability / 2)
            assert branch["retained_phi_plus_fidelity"] == pytest.approx(fidelity)
    assert untwirled.is_valid() and twirled.is_valid()
    # Isotropic form has one distinguished eigenvalue and three equal others.
    eigenvalues = np.linalg.eigvalsh(twirled.data)
    np.testing.assert_allclose(np.sort(eigenvalues), np.sort(werner_channel(fidelity)), atol=1e-12)


def test_purification_needs_more_than_a_pauli_twirl():
    _, _, untwirled, twirled, _ = bbpssw_density(0.8)
    assert not np.allclose(untwirled.data, twirled.data)


@pytest.mark.parametrize("channel", [identity_channel(), werner_channel(0.73),
    [0.6, 0.1, 0.2, 0.1], *np.eye(4)])
@pytest.mark.parametrize("state", [[1, 0], [0, 1], np.array([1, 1]) / np.sqrt(2),
    np.array([1, 1j]) / np.sqrt(2), np.array([np.sqrt(0.3), np.exp(0.7j) * np.sqrt(0.7)])])
def test_teleportation_actual_corrections_and_independent_channel(state, channel):
    result, branches = teleportation_density(state, channel)
    rho = DensityMatrix(state).data
    expected = sum(p * Operator(Pauli(label)).data @ rho @ Operator(Pauli(label)).data.conj().T
                   for p, label in zip(channel, "IXYZ"))
    assert result.is_valid()
    np.testing.assert_allclose(result.data, expected, atol=1e-12)
    assert len(branches) == 4
    for branch in branches:
        assert branch["probability"] == pytest.approx(0.25)
        assert branch["x_correction"] == branch["m1"]
        assert branch["z_correction"] == branch["m0"]
        density = branch["corrected_density"]
        np.testing.assert_allclose(np.array(density["real"]) + 1j * np.array(density["imag"]),
                                   expected, atol=1e-12)


def test_gate_cancellation_and_fidelity_endpoints():
    identity, x = identity_channel(), np.eye(4)[1]
    assert gate_process_fidelity(identity, identity) == 1
    assert gate_average_fidelity(identity, identity) == 1
    assert gate_process_fidelity(x, identity) == 0
    assert gate_process_fidelity(x, identity, 1) == pytest.approx(1 / 15)
    assert gate_process_fidelity(identity, identity, 1) == 0
    assert gate_process_fidelity([0.25] * 4, [0.25] * 4, 0.71) == pytest.approx(1 / 16)
    assert gate_average_fidelity([0.25] * 4, [0.25] * 4, 0.71) == pytest.approx(0.25)


def test_gate_independent_full_kraus_cnot_reference():
    rng = np.random.default_rng(197)
    cases = [(np.eye(4)[i], np.eye(4)[j], e)
             for i in range(4) for j in range(4) for e in (0, 0.23, 1)]
    cases.extend((rng.dirichlet(np.ones(4)), rng.dirichlet(np.ones(4)), rng.random())
                 for _ in range(12))
    for a, b, error in cases:
        independent = cnot_process_check(a, b, error)
        assert independent["is_cptp"]
        assert independent["process_fidelity"] == pytest.approx(gate_process_fidelity(a, b, error), abs=1e-12)
        assert independent["average_fidelity"] == pytest.approx(gate_average_fidelity(a, b, error), abs=1e-12)


@pytest.mark.parametrize("input_a,input_b,return_a,return_b", [
    ("X", "I", "X", "X"), ("I", "Z", "Z", "Z"),
    ("Y", "I", "Y", "X"), ("I", "Y", "Z", "Y"),
    ("Z", "X", "Z", "X"), ("X", "Z", "Y", "Y"),
])
def test_cnot_correlated_input_return_cancellation(input_a, input_b, return_a, return_b):
    channels = {p: np.eye(4)[i] for i, p in enumerate("IXYZ")}
    a, b = channels[input_a], channels[input_b]
    post_a, post_b = channels[return_a], channels[return_b]
    for error in (0, 0.17, 1):
        expected = 1 - error
        actual = gate_process_fidelity(a, b, error, post_a=post_a, post_b=post_b)
        independent = cnot_process_check(a, b, error, post_a=post_a, post_b=post_b)
        assert actual == pytest.approx(expected, abs=1e-12)
        assert independent["process_fidelity"] == pytest.approx(expected, abs=1e-12)
        assert independent["is_cptp"]


def test_cnot_joint_error_distribution_cannot_be_replaced_by_marginals():
    # A random I/X control error propagates to joint II/XX, not independent I/X outputs.
    random_x = np.array([0.5, 0.5, 0, 0])
    identity, x = identity_channel(), np.eye(4)[1]
    assert gate_process_fidelity(random_x, identity, post_a=x, post_b=x) == pytest.approx(0.5)
    # Multiplying independently computed output marginals would incorrectly give 0.25.
    independent = cnot_process_check(random_x, identity, post_a=x, post_b=x)
    assert independent["process_fidelity"] == pytest.approx(0.5)
    assert gate_process_fidelity(x, identity, post_a=x, post_b=identity) == 0


def test_noisy_returns_against_qiskit_and_default_compatibility():
    rng = np.random.default_rng(812)
    for _ in range(12):
        a, b, post_a, post_b = rng.dirichlet(np.ones(4), size=4)
        error = rng.random()
        independent = cnot_process_check(a, b, error, post_a=post_a, post_b=post_b)
        actual = gate_process_fidelity(a, b, error, post_a=post_a, post_b=post_b)
        average = gate_average_fidelity(a, b, error, post_a=post_a, post_b=post_b)
        assert 0 <= actual <= 1
        assert independent["process_fidelity"] == pytest.approx(actual, abs=1e-12)
        assert independent["average_fidelity"] == pytest.approx(average, abs=1e-12)
        assert gate_process_fidelity(a, b, error) == pytest.approx(
            gate_process_fidelity(a, b, error, post_a=identity_channel(), post_b=identity_channel()))


def test_validation_evidence(tmp_path):
    summary = run_validation(tmp_path)
    assert summary["passed"], summary["failed_checks"]
    assert summary["checks"] >= 300
    assert not summary["hardware"] and not summary["network_execution"]
    assert not summary["whole_network_validated"]
    assert summary == json.loads((tmp_path / "summary.json").read_text())
    for name in ("checks.csv", "checks.json", "details.json", "resources.csv",
                 "teleportation.qasm", "bbpssw.qasm", "cnot.qasm"):
        assert (tmp_path / name).stat().st_size > 0
    assert "if (" in (tmp_path / "teleportation.qasm").read_text()
