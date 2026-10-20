"""Arithmetic and exhaustive topology checks; these are audit tests, not DEQUINT results."""

import csv
import json
import math
from itertools import permutations
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def main():
    checks = []

    def record(name, value, meaning):
        checks.append({"check": name, "value": value, "interpretation": meaning})

    record("ideal_per_link_pairs_per_second", 2 * 20_000 * .75**2, "Inverse of manuscript tau_EPR; not validated delivered throughput")
    record("ideal_24_link_pairs_per_second", 24 * 2 * 20_000 * .75**2, "540,000 follows from the printed formula and 24 parallel links")
    record("throughput_claim_ratio", 540_000 / 740, "Different primary throughput values need event/metric definitions")
    record("mean_latency_reduction_percent", 100 * (.320 - .195) / .320, "Reduction computed from the printed rounded means")
    record("mean_hop_reduction_percent", 100 * (2.75 - 1.67) / 2.75, "Hop reduction differs from latency reduction after rounding")
    record("HH_ms_per_mean_hop", .320 / 2.75, "Near-constant latency per hop is not by itself proof of absent simulation")
    record("TWT_ms_per_mean_critical_round", .195 / 1.67, "Critical-path rounds must not be confused with total quantum hop operations")
    p = .75**2 * .64 * .99 * math.exp(-.00012 / 1.3)
    record("printed_model_one_hop_reliability", p, "Scalar Eq.6; interpretation of F_g as probability is not established")
    record("printed_model_at_mean_2_75_hops", p**2.75, "Plug-in value only: R(E[h]) is not E[R(h)]")
    record("retry_mean_multiplier_if_geometric", 1 / p, "Only if p is independent retry success and whole hop is repeated at equal cost")
    record("epr_latency_microseconds", 1e6 / (2 * 20_000 * .75**2), "Already contains eta_m^2; blindly adding same loss again can double-count")
    record("qm_load_microseconds", 1e6 / 20_000, "Printed 1/f_m latency")
    record("24_bsm_area_square_mm", 24 * 600 / 1_000_000, "Manuscript 14.4 mm^2 has a factor-1000 unit error")
    record("detector_300x180_area_square_mm", 300 * 180 / 1_000_000, "0.054 mm^2 per cited detector, larger than claimed complete 600 um^2 node")
    record("wired_delay_ns", .05 * 1_000_000, "50,000 ns is not justified by on-chip propagation; queue/service latency needs measured assumptions")
    record("wireless_delay_ns", .01 * 1_000_000, "10,000 ns likewise needs MAC/channel/queue decomposition")
    record("0_5K_to_20mK_ratio", .5 / .020, "A bound DeltaT<0.5K does not establish millikelvin compatibility")
    record("0_5K_to_10mK_ratio", .5 / .010, "This is a permissive bound, not evidence the actual rise equals 0.5K")
    record("mesh_bsm_count_correct_N16", 2 * 16 - 2 * math.sqrt(16), "Square-grid edge count")
    record("mesh_bsm_count_wrong_N16", 2 * math.sqrt(16) * (16 - math.sqrt(16)), "Printed non-equivalent expression")
    r = math.sqrt(.6)
    record("cooperativity_at_equation_F_0_8", (64 * r / (1 - r)) / 14 - 1, "About 14.7, not 100, for the printed Eq.3 parameters")
    tail = .2 / 3
    pur_success = .8**2 + 2 * .8 * tail + 5 * tail**2
    record("BBPSSW_F0_8_output", (.8**2 + tail**2) / pur_success, "Werner-state, ideal-operation conditional fidelity")
    record("BBPSSW_F0_8_success", pur_success, "Acceptance probability must enter resource accounting")
    record("BBPSSW_expected_raw_pairs_per_output", 2 / pur_success, "About 2.60, not exactly two, for repeat-until-success at F=.8")

    nodes = [(x, y) for x in range(4) for y in range(4)]
    rows = []
    for source, destination in permutations(nodes, 2):
        midpoint = ((source[0] + destination[0]) // 2, (source[1] + destination[1]) // 2)
        a, b = distance(source, midpoint), distance(destination, midpoint)
        optimal = min(max(distance(source, m), distance(destination, m)) for m in nodes)
        rows.append({"source": str(source), "destination": str(destination), "HH_hops": distance(source, destination),
                     "paper_midpoint": str(midpoint), "source_path": a, "destination_path": b,
                     "paper_critical_rounds": max(a, b), "optimal_critical_rounds": optimal,
                     "total_quantum_hops": a + b, "paper_midpoint_suboptimal": int(max(a, b) > optimal)})
    record("ordered_distinct_pairs_tested", len(rows), "Exhaustive check of printed midpoint, without congestion")
    record("suboptimal_midpoint_pair_count", sum(r["paper_midpoint_suboptimal"] for r in rows), "Coordinate-wise floor fails to minimize maximum Manhattan distance for these pairs")
    record("all_shortest_midpoint_paths_total_hops_equal_HH", all(r["total_quantum_hops"] == r["HH_hops"] for r in rows), "Counters the categorical claim that rendezvous doubles EPR consumption")
    record("uniform_distinct_pair_mean_HH_hops", sum(r["HH_hops"] for r in rows) / len(rows), "Uniform all-pair reference, not the unknown manuscript 100-pair sample")
    record("uniform_distinct_pair_mean_paper_critical_rounds", sum(r["paper_critical_rounds"] for r in rows) / len(rows), "Printed floor rule")
    record("uniform_distinct_pair_mean_optimal_rounds", sum(r["optimal_critical_rounds"] for r in rows) / len(rows), "Correct minimax reference")
    record("midpoint_counterexample_h_2", "(0,0)->(1,1): floor midpoint=(0,0), paths=(0,2), optimal midpoint=(0,1), paths=(1,1)", "Printed rule fails its ceil(h/2) claim")
    record("fallback_bounds_counterexample", "(3,2)->(3,3): midpoint=(3,2), candidate midpoint+(1,0)=(4,2)", "No bounds check or reservation protocol appears in Algorithm 3")
    with (ROOT / "recomputed_claims.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(checks[0]))
        writer.writeheader()
        writer.writerows(checks)
    with (ROOT / "exhaustive_midpoint_checks.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (ROOT / "numeric_audit.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
