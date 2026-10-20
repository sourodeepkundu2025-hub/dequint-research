"""Independent DEQUINT arithmetic and isolated circuit checks.

These checks do not reproduce the manuscript's integrated SeQUeNCe runs.
"""

import csv
import json
import math
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import DensityMatrix, Statevector, state_fidelity
from qiskit_aer import AerSimulator


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "supporting_checks"
OUT.mkdir(parents=True, exist_ok=True)


def bell_fidelity(cooperativity):
    gamma = 14.0
    gamma_star = 32.0
    numerator = ((cooperativity + 1) * gamma) ** 2
    denominator = ((cooperativity + 1) * gamma + 2 * gamma_star) ** 2
    return 0.5 * (1.0 + numerator / denominator)


def bbpssw(fidelity):
    tail = (1.0 - fidelity) / 3.0
    success = fidelity**2 + 2.0 * fidelity * tail + 5.0 * tail**2
    purified = (fidelity**2 + tail**2) / success
    return purified, success


def teleportation_checks():
    rng = np.random.default_rng(20260928)
    states = {
        "zero": np.array([1, 0], dtype=complex),
        "one": np.array([0, 1], dtype=complex),
        "plus": np.array([1, 1], dtype=complex) / np.sqrt(2),
        "minus": np.array([1, -1], dtype=complex) / np.sqrt(2),
        "phase": np.array([1, 1j], dtype=complex) / np.sqrt(2),
    }
    for index in range(5):
        vector = rng.normal(size=2) + 1j * rng.normal(size=2)
        states[f"random_{index + 1}"] = vector / np.linalg.norm(vector)
    simulator = AerSimulator(method="density_matrix")
    rows = []
    for name, amplitudes in states.items():
        circuit = QuantumCircuit(3, 2)
        circuit.initialize(amplitudes, 0)
        circuit.h(1)
        circuit.cx(1, 2)
        circuit.cx(0, 1)
        circuit.h(0)
        circuit.measure(0, 0)
        circuit.measure(1, 1)
        with circuit.if_test((circuit.clbits[1], 1)):
            circuit.x(2)
        with circuit.if_test((circuit.clbits[0], 1)):
            circuit.z(2)
        circuit.save_density_matrix([2], label="receiver")
        compiled = transpile(circuit, simulator, optimization_level=0)
        result = simulator.run(compiled, shots=1024, seed_simulator=20260928).result()
        if not result.success:
            raise RuntimeError(f"Aer failed on {name}: {result.status}")
        receiver = DensityMatrix(result.data(0)["receiver"])
        fidelity = float(state_fidelity(receiver, Statevector(amplitudes)))
        rows.append({"state": name, "fidelity": fidelity, "qubits": 3,
                     "shots": 1024, "transpiled_depth": compiled.depth(),
                     "backend": "Aer density_matrix ideal"})
    return rows


def regression_fit(x, y):
    design = np.column_stack((np.ones(len(x)), x))
    coefficients = np.linalg.lstsq(design, y, rcond=None)[0]
    predicted = design @ coefficients
    ss_res = float(np.sum((y - predicted) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    return {"intercept": float(coefficients[0]), "slope": float(coefficients[1]),
            "r_squared": 1.0 - ss_res / ss_tot}


def fault_model():
    rng = np.random.default_rng(20260928)
    trials = 100_000
    p_swap = 0.64
    gate_fidelity = 0.99
    coherence_s = 1.3
    hop_latency_s = 0.00012
    chart = {
        0.50: [0.56, 0.31, 0.18, 0.10, 0.06, 0.03],
        0.75: [0.76, 0.58, 0.44, 0.33, 0.25, 0.19],
        0.90: [0.87, 0.76, 0.66, 0.57, 0.50, 0.43],
    }
    rows = []
    for eta, plotted in chart.items():
        per_hop = eta**2 * p_swap * gate_fidelity * math.exp(-hop_latency_s / coherence_s)
        for hop in range(1, 7):
            independent = rng.random((trials, hop)) < per_hop
            simulated = float(np.mean(independent.all(axis=1)))
            expected = per_hop**hop
            half_width = 1.96 * math.sqrt(simulated * (1 - simulated) / trials)
            rows.append({"eta_m": eta, "hops": hop, "equation_probability": expected,
                         "independent_mc_probability": simulated,
                         "mc_95pct_half_width": half_width,
                         "manuscript_plot_probability": plotted[hop - 1],
                         "difference_plot_minus_equation": plotted[hop - 1] - expected,
                         "trials": trials, "seed": 20260928})
    return rows


def write_csv(name, rows):
    with (OUT / name).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    teleport = teleportation_checks()
    write_csv("teleportation_ideal_aer.csv", teleport)
    plotted_bk = {10: 0.62, 50: 0.72, 100: 0.83, 200: 0.92,
                  300: 0.95, 400: 0.97, 500: 0.991}
    bk_rows = [{"cooperativity": c, "equation_fidelity": bell_fidelity(c),
                "plotted_qiskit_value": y, "difference": y - bell_fidelity(c)}
               for c, y in plotted_bk.items()]
    write_csv("barrett_kok_equation_vs_plot.csv", bk_rows)
    bb_rows = []
    for fidelity in [0.50, 0.62, 0.72, 0.80, 0.83, 0.92, 0.991]:
        purified, success = bbpssw(fidelity)
        bb_rows.append({"input_fidelity": fidelity, "purified_fidelity": purified,
                        "success_probability": success,
                        "fidelity_gain": purified - fidelity})
    write_csv("bbpssw_formula_sweep.csv", bb_rows)
    faults = fault_model()
    write_csv("fault_model_mc.csv", faults)

    core_counts = np.array([2, 4, 8, 16], dtype=float)
    latencies = np.array([0.147, 0.158, 0.172, 0.191], dtype=float)
    comparison = []
    for radius, hh, twt, hh_depth, twt_depth, printed in [
        (1, .12, .12, 2, 2, 0), (2, .23, .12, 4, 2, 50),
        (3, .35, .23, 6, 4, 33), (4, .47, .23, 8, 4, 50),
        (6, .70, .35, 12, 6, 50),
    ]:
        comparison.append({"connectivity_radius": radius, "hh_ms": hh, "twt_ms": twt,
                           "calculated_latency_saving_pct": 100 * (hh - twt) / hh,
                           "printed_latency_saving_pct": printed,
                           "hh_depth": hh_depth, "twt_depth": twt_depth,
                           "calculated_depth_saving_pct": 100 * (hh_depth - twt_depth) / hh_depth})
    write_csv("hh_twt_table_recalculated.csv", comparison)

    result = {
        "scope": "Independent isolated checks; original DEQUINT SeQUeNCe code and raw runs not available locally",
        "teleportation": {"state_count": len(teleport),
                           "minimum_ideal_fidelity": min(row["fidelity"] for row in teleport),
                           "backend": "Qiskit Aer 0.17.2 density_matrix, ideal, 1024 shots per state"},
        "barrett_kok": {"at_c500": bell_fidelity(500),
                         "at_c100_equation": bell_fidelity(100),
                         "at_c100_plotted": plotted_bk[100]},
        "bbpssw_at_f080": {"purified_fidelity": bbpssw(.8)[0],
                            "success_probability": bbpssw(.8)[1]},
        "throughput": {"at_eta_075_pairs_per_s": 740.6,
                       "at_eta_090_pairs_per_s": 895.5,
                       "slope_eta_050_to_090_pairs_per_s_per_eta": (895.5 - 487.5) / .4,
                       "ideal_link_rate_at_eta_075_pairs_per_s": 2 * 20_000 * .75**2,
                       "ideal_24_link_rate_pairs_per_s": 24 * 2 * 20_000 * .75**2},
        "latency": {"from_2_to_16_core_pct_increase": 100 * (.191 - .147) / .147,
                    "log2_fit": regression_fit(np.log2(core_counts), latencies),
                    "linear_n_fit": regression_fit(core_counts, latencies),
                    "hh_to_twt_mc_pct_reduction": 100 * (.320 - .195) / .320,
                    "b1_to_dequint_16_core_pct_reduction": 100 * (.63 - .191) / .63,
                    "b2_to_dequint_16_core_pct_reduction": 100 * (.271 - .191) / .271},
        "routing_table": comparison,
        "fault_model": {"trials_per_condition": 100_000,
                        "one_hop_eta_075_equation": next(row["equation_probability"] for row in faults
                                                           if row["eta_m"] == .75 and row["hops"] == 1),
                        "one_hop_eta_075_plot": .76,
                        "model": "Independent Bernoulli trial of manuscript Eq. reliability; not SeQUeNCe"},
        "topology": {"four_by_four_nearest_neighbor_links": 2 * 4 * (4 - 1),
                     "manuscript_first_formula_n16": 2 * 16 * (4 - 1) / 4,
                     "manuscript_second_formula_n16": 2 * 4 * (16 - 4)},
    }
    (OUT / "checks.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"min_teleport_fidelity": result["teleportation"]["minimum_ideal_fidelity"],
                      "bk_c100_equation": result["barrett_kok"]["at_c100_equation"],
                      "reliability_one_hop_eta075": result["fault_model"]["one_hop_eta_075_equation"]},
                     indent=2))


if __name__ == "__main__":
    main()
