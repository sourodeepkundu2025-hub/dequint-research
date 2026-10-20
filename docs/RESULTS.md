# Experiments, Evidence and Results

## Evidence Classes

1. **Arithmetic/topology checks:** validate equations or graph properties only.
2. **Exact primitive checks:** circuit/density-matrix agreement for bounded protocols.
3. **Abstract event-network simulation:** resource contention and declared noise laws.
4. **Native photonic checks:** actual pinned upstream optical/protocol objects.
5. **Application timing replay:** circuit dependencies and placement, not application state fidelity.
6. **Ideal compiled channels:** dynamic-gate skeletons, not optical hardware depth.
7. **Physical experiment:** not supplied in this repository.

Never substitute one evidence class for another.

## Dataset Catalog

| Folder | Status | What to inspect |
| --- | --- | --- |
| `results/batch_v1` | Quarantined, NOT_ACCEPTED | Earlier partial/pre-review records; never a paper-result source |
| `results/batch_v2` | Accepted primary snapshot | 460 runs, 22,080 offered gates; requests, workload identities, traces and paired intervals |
| `results/followup_v1` | Accepted follow-up snapshot | 124 native runs / 172 offered CNOTs; 128 application replays; 48 matched-control runs / 2,304 offered gates |
| `results/shortcut_v1` | Separate overlay profile | 432 runs / 13,824 offered tasks; topology census, edge costs and lossy conditions |
| `results/review_supplement_v1` | Separate matched transport profile | 48 runs / 1,152 offered tasks; all-run events and paired common-completion comparisons |
| `results/compiled_depth_v1` | Ideal gate-link profile | 18 Choi channels, 108 schedules, source/compiled QASM and readback audit |
| `results/quantum_validation` | Exact primitive checks | 472 checks; equations versus Qiskit circuit/density-matrix calculations |
| `results/native_reference` | Separate protocol checks | Generation, teleportation, BBPSSW and swapping, 32 trials per protocol |
| `history/isolated_checks` | Historical limited checks | Formula sweeps and isolated ideal teleportation; not integrated DEQUINT evidence |
| `history/arithmetic_audit` | Historical diagnostic checks | Printed-equation arithmetic and exhaustive midpoint enumeration |

The final lineage ledger has **1,258 records: 1,240 network/application runs plus
18 compiled channels**. The separate primitive/reference checks are not silently
added to that run count. `PUBLIC_SHA256SUMS.json` authenticates this public copy;
the retained original manifests document the earlier frozen executions.

The primary analyzer was improved after the initial batch freeze. Its current
source matches the recorded analysis receipt, not the earlier run-environment
analyzer identity. The seven source checkpoints do not recover every original
source-freeze version, including the complete quarantined batch freeze. The
repository supplies raw records and current reproducible analyses, not a claim
of byte-exact recovery of all historical software states.

## Selected Quantitative Readouts

| Question | Observed result | Interpretation |
| --- | --- | --- |
| Does the primary quality term add benefit over queue-only? | 121/480 versus 116/480 qualified; +1.04 percentage points, paired 95% interval [-0.41, +2.49] | No established added benefit in this cell |
| Are native ideal corner cases correct? | All 64 ideal corner tasks complete with unit process fidelity to numerical precision | Bounded native channel validation, not a physical device |
| Does pooling necessarily lose to per-link generation? | Equal 24-server pool: 197 qualified; per-link: 119, out of 576 offered each | Universal decentralization superiority is not supported |
| Does purification necessarily improve useful throughput? | 295/576 complete versus 575/576 without; zero qualified in both tested stress cells | Preserve the negative result and conditional-quality/resource tradeoff |
| What does the 1,024-core overlay change? | Graph diameter 62 to 8; links 1,984 to 4,021; 1 mm-pitch cable lower bound 1.984 m to about 27.053 m | Lower hop diameter has installation/loss costs |
| Does radio improve latency in the matched sensitivity? | 736 qualified, 402 completed-unqualified, 14 failed overall; radio about 0.60-0.90 microseconds slower in all eight contrasts | No radio crossover in the bounded tested cells |
| Are compiled teleportation skeletons the best depth controls? | Endpoint/rendezvous depth 32/26 at distance two and 64/42 at distance four; matched SABRE is shallower throughout | No application/QEC depth advantage demonstrated |
| Do compiled saved channels implement restored CNOT? | Maximum Choi entry error about 2.82e-16 across 18 ideal channels | Numerical channel agreement, not physical fidelity |

Thresholds, placement, load and backend conditions matter. Inspect the relevant
protocol and raw summaries before reusing a number; this table is an index, not
a replacement for the frozen design.

## Data Integrity and Privacy

Scientific raw requests, events, QASM and numerical arrays are retained.
Some environment/receipt files contain redacted local-home/workspace strings.
For those files the original and public SHA-256 values are both recorded in
`PUBLICATION_PROVENANCE.json`; old source/result hashes are not relabeled as new
execution evidence. The public verifier follows that explicit identity mapping
and fails on any other file change.

Five frozen setuptools metadata files are stored under
`history/frozen_packaging_metadata`, rather than live `src/*.egg-info`, so an
editable installation cannot overwrite their historical identities. Their
canonical origin paths remain in the provenance mapping. Temporary test fixtures
that are not scientific runs or protected evidence are omitted.

## Replotting

Primary and follow-up plotting utilities live in `src/dequint/analyze.py` and
`tools/build_followup_sections.py`; overlay plotting is in
`tools/run_shortcut_investigation.py`. Reporting builders may require private
paper/template inputs and are not needed for running scientific experiments.
Use a fresh result directory for analysis work rather than overwriting supplied
plots. Figure PDFs/PNGs are derived model outputs, not AI-generated result data.
