# Reviewer 2/3 Supplement v1

Prospective finite-batch model, not measured physical hardware.
Same ordered CNOT, free placement, fixed memory/deadline contract; all 48 runs retained.

| Excitation Hz | Offered /s | Policy | Fabric | Completed/offered | Qualified/offered | Payload pairs (failed) | Mean completed latency us |
|---:|---:|---|---|---:|---:|---:|---:|
| 20000 | 1000 | hh | radio | 71/72 | 22/72 | 188 (3) | 1387.383 |
| 20000 | 1000 | hh | wired | 71/72 | 22/72 | 188 (3) | 1386.733 |
| 20000 | 1000 | midpoint | radio | 72/72 | 28/72 | 190 (0) | 1158.604 |
| 20000 | 1000 | midpoint | wired | 72/72 | 28/72 | 190 (0) | 1158.007 |
| 20000 | 100000 | hh | radio | 69/72 | 14/72 | 186 (6) | 2005.803 |
| 20000 | 100000 | hh | wired | 69/72 | 14/72 | 186 (6) | 2005.045 |
| 20000 | 100000 | midpoint | radio | 69/72 | 16/72 | 187 (9) | 1696.324 |
| 20000 | 100000 | midpoint | wired | 69/72 | 16/72 | 187 (9) | 1695.648 |
| 2000000 | 1000 | hh | radio | 72/72 | 72/72 | 190 (0) | 15.746 |
| 2000000 | 1000 | hh | wired | 72/72 | 72/72 | 190 (0) | 14.849 |
| 2000000 | 1000 | midpoint | radio | 72/72 | 72/72 | 190 (0) | 11.915 |
| 2000000 | 1000 | midpoint | wired | 72/72 | 72/72 | 190 (0) | 11.302 |
| 2000000 | 100000 | hh | radio | 72/72 | 72/72 | 190 (0) | 16.685 |
| 2000000 | 100000 | hh | wired | 72/72 | 72/72 | 190 (0) | 15.985 |
| 2000000 | 100000 | midpoint | radio | 72/72 | 72/72 | 190 (0) | 13.230 |
| 2000000 | 100000 | midpoint | wired | 72/72 | 72/72 | 190 (0) | 12.593 |

## Wired/radio contrasts

Positive delta favors wired for latency, radio for fractions.
Intervals are exploratory seed-level t intervals (3 seeds); no multiplicity correction.

| Excitation Hz | Offered /s | Policy | Qualified delta | Completion delta | Common-completion latency delta us [95% CI] |
|---:|---:|---|---:|---:|---|
| 20000 | 1000 | hh | 0.000000 | 0.000000 | 0.6494 [0.4860, 0.8129] |
| 20000 | 1000 | midpoint | 0.000000 | 0.000000 | 0.5967 [0.4532, 0.7402] |
| 20000 | 100000 | hh | 0.000000 | 0.000000 | 0.7542 [0.4380, 1.0703] |
| 20000 | 100000 | midpoint | 0.000000 | 0.000000 | 0.6725 [0.3410, 1.0039] |
| 2000000 | 1000 | hh | 0.000000 | 0.000000 | 0.8976 [0.5239, 1.2712] |
| 2000000 | 1000 | midpoint | 0.000000 | 0.000000 | 0.6131 [0.4309, 0.7953] |
| 2000000 | 100000 | hh | 0.000000 | 0.000000 | 0.7001 [0.5080, 0.8921] |
| 2000000 | 100000 | midpoint | 0.000000 | 0.000000 | 0.6365 [0.4979, 0.7752] |

Crossover screening at fixed load/policy:
- 1000/s, hh: sign reversal=False; both exploratory intervals exclude zero=True; supported reversal in tested cells=False.
- 1000/s, midpoint: sign reversal=False; both exploratory intervals exclude zero=True; supported reversal in tested cells=False.
- 100000/s, hh: sign reversal=False; both exploratory intervals exclude zero=True; supported reversal in tested cells=False.
- 100000/s, midpoint: sign reversal=False; both exploratory intervals exclude zero=True; supported reversal in tested cells=False.

## Interpretation Boundaries

Generation-rate contrasts and minimax/HH contrasts, full failure reasons, pair accounting, and intervals are in analysis.json.
Do not infer classical-service dominance from generation-rate sensitivity or treat a sign change alone as an established crossover.
A wired/radio latency crossover requires a reversal of paired common-completion latency signs across excitation profiles; intervals spanning zero are inconclusive.
The trace has no complete service-start/end partition. No nine-disjoint-stage timing, physical crossover threshold, steady-state capacity, or entanglement-witness runtime result is established.
Terminal deadline failures remain in all-offered denominators; incomplete latency/fidelity is not imputed.
Consumed payload pairs on failures are included. All pair_consumed events also include discarded resources and are reported separately.
No manuscript edits are made. This report supports only the stated prospective parameter cells.
