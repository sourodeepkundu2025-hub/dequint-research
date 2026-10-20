"""Conditional Pauli noise primitives; no availability or retry probabilities.

Channels use I, X, Y, Z order. The corresponding Bell order is Phi+, Psi+,
Psi-, Phi- (global phases ignored). All gates in BBPSSW are ideal; its inputs
must be independent Werner states about Phi+. Its output is generally Bell
diagonal, not Werner, until an explicit fidelity-preserving bilateral twirl.
"""

from __future__ import annotations

import math
from numbers import Real

import numpy as np


def _real(value: float, name: str, *, allow_infinity: bool = False) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a real number")
    value = float(value)
    if math.isnan(value) or (not allow_infinity and not math.isfinite(value)):
        raise ValueError(f"{name} must be finite")
    return value


def _probability(value: float, name: str) -> float:
    value = _real(value, name)
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be in [0, 1]")
    return value


def _channel(channel) -> np.ndarray:
    """Validate a distribution, normalizing only <=1e-12 summation roundoff."""
    try:
        array = np.asarray(channel)
    except (TypeError, ValueError) as exc:
        raise ValueError("channel must contain four real probabilities") from exc
    if array.shape != (4,) or array.dtype.kind not in "iuf":
        raise ValueError("channel must contain four real probabilities")
    array = array.astype(float, copy=True)
    if not np.all(np.isfinite(array)) or np.any(array < 0) or np.any(array > 1):
        raise ValueError("channel probabilities must be finite and in [0, 1]")
    total = float(array.sum())
    if abs(total - 1) > 1e-12:
        raise ValueError("channel probabilities must sum to one")
    return array / total


def identity_channel() -> np.ndarray:
    return np.array([1.0, 0.0, 0.0, 0.0])


def werner_channel(fidelity: float) -> np.ndarray:
    fidelity = _probability(fidelity, "fidelity")
    return np.array([fidelity, *((1 - fidelity) / 3,) * 3])


def compose_pauli(first, second) -> np.ndarray:
    """Exact phase-ignored group convolution, including repeated-error cancellation."""
    first, second = _channel(first), _channel(second)
    output = np.zeros(4)
    for i in range(4):
        for j in range(4):
            output[i ^ j] += first[i] * second[j]
    return output


def dephasing_channel(duration_s: float, t2_s: float) -> np.ndarray:
    duration_s = _real(duration_s, "duration_s")
    t2_s = _real(t2_s, "t2_s", allow_infinity=True)
    if duration_s < 0 or t2_s <= 0:
        raise ValueError("duration_s must be nonnegative and t2_s positive")
    # expm1 preserves very small, nonzero dephasing probabilities.
    phase_error = -0.5 * math.expm1(-duration_s / t2_s)
    return np.array([1 - phase_error, 0.0, 0.0, phase_error])


def age_channel(channel, duration_s: float, t2_s: float) -> np.ndarray:
    """Age one endpoint; use duration 2*t for two equally aging endpoints."""
    return compose_pauli(channel, dephasing_channel(duration_s, t2_s))


def pauli_depolarizing(error_probability: float) -> np.ndarray:
    error_probability = _probability(error_probability, "error_probability")
    return werner_channel(1 - error_probability)


def bbpssw(fidelity_a: float, fidelity_b: float | None = None) -> tuple[float, float]:
    """Return (accepted Phi+ fidelity, acceptance probability) for two Werner pairs.

    Bilateral CNOT uses the retained pair as control, with equal Z-basis target
    outcomes accepted. No retries or gate/detection imperfections are included.
    A subsequent isotropic U tensor U* twirl preserves this fidelity and makes
    the output suitable as another Werner input. This is not a Pauli-only twirl.
    """
    a = _probability(fidelity_a, "fidelity_a")
    b = a if fidelity_b is None else _probability(fidelity_b, "fidelity_b")
    qa, qb = (1 - a) / 3, (1 - b) / 3
    acceptance = (a + qa) * (b + qb) + 4 * qa * qb
    return (a * b + qa * qb) / acceptance, acceptance


def gate_process_fidelity(
    channel_a, channel_b, gate_error: float = 0, *, post_a=None, post_b=None,
) -> float:
    """Entanglement fidelity relative to CNOT, for independent input noise.

    Operand A is control (q0), B is target (q1). Optional independent return
    channels post_a/post_b act after ideal CNOT and gate noise. Input errors
    become correlated under CNOT; their joint distribution is retained.
    A two-qubit gate Pauli has identity mass 1-e and e/15 on each nonidentity.
    It can cancel the residual input/return error, not just reduce fidelity.
    """
    a, b = _channel(channel_a), _channel(channel_b)
    error = _probability(gate_error, "gate_error")
    after_a = identity_channel() if post_a is None else _channel(post_a)
    after_b = identity_channel() if post_b is None else _channel(post_b)
    # I=(0,0), X=(1,0), Y=(1,1), Z=(0,1). Pauli phases do not matter.
    xz = ((0, 0), (1, 0), (1, 1), (0, 1))
    index = {bits: i for i, bits in enumerate(xz)}
    identity_mass = 0.0
    for i, (xa, za) in enumerate(xz):
        for j, (xb, zb) in enumerate(xz):
            cnot_a = index[(xa, za ^ zb)]
            cnot_b = index[(xb ^ xa, zb)]
            identity_mass += a[i] * b[j] * after_a[cnot_a] * after_b[cnot_b]
    return float((1 - error) * identity_mass + error * (1 - identity_mass) / 15)


def gate_average_fidelity(
    channel_a, channel_b, gate_error: float = 0, *, post_a=None, post_b=None,
) -> float:
    """Dimension-four average gate fidelity, not a selected output-state fidelity."""
    return (4 * gate_process_fidelity(
        channel_a, channel_b, gate_error, post_a=post_a, post_b=post_b,
    ) + 1) / 5
