# Reviewer 2/3 Evidence Handoff

## Scope and Sources

Additive prospective finite-batch model only. No measured physical data, new native
optical implementation, runtime entanglement witness, frozen-module edit,
manuscript edit, remote write, or commit. This handoff does not approve paper claims.

- Frozen design and exact action mapping: docs/REVIEW_SUPPLEMENT_PROTOCOL.md.
- Executable experiment and analysis: tools/run_review_supplement.py.
- Freeze identity: freeze.json; 27 source/protocol/harness/test/declaration hashes.
- Protected existing results: 3,993 preexisting files hashed and verified unchanged.
- Workloads: six saved load/seed files; same IDs, ordered endpoints, arrival times
  and deadlines in every matched excitation/policy/fabric arm at a fixed load/seed.
- Raw evidence: runs/*/requests.json, events.jsonl, summary.json, audit.json and
  raw_sha256.json. Each started.json links the prior freeze's SHA-256.
- Tables: REPORT.md; exact counts and seed-paired intervals: analysis.json.
- Trace count overview: STAGE_AUDIT.md. Its observations are explicitly overlapping.
- Local reconciliation receipt: receipt.json.

## Counts for Reviewers

48 runs, three seeds, 24 requests/run, 1,152 offered CNOTs. Exactly 1,138 completed,
736 qualified, 402 completed but unqualified, 14 failed. The exclusive recorded
failure reasons are deadline (10) and resource_deadline (4). No administrative
censoring or resource leak is observed. There are 3,022 consumed payload pairs,
including 36 consumed by failed requests. All failure costs remain in the totals.

At 20 kHz, 160/576 offered requests qualify; at 2 MHz, 576/576 qualify. These are
descriptive totals over repeated matched arms, not 576 independent statistical
replicates. Inferential units are the three seeds per fixed comparison cell.

## Allowed Wording

"In the predeclared prospective sensitivity experiment, wired and radio arms used
the same CNOT task, workloads, seeds, memory settings and deadlines. Completion and
qualification counts were identical between fabrics in every matched cell. Radio
had a higher common-completion paired mean latency in all eight contrasts
(approximately 0.60-0.90 microseconds; exploratory seed-level intervals reported).
No wired/radio latency sign reversal was observed between 20 kHz and 2 MHz at
either offered load under HH or geodesic minimax. The faster excitation profile
increased the observed qualification counts within this model; this is not a
measured physical acceleration or a classical-service dominance threshold."

For the event-stage reviewer concern: "Full traces support explicit arrival,
route, admission, complete-attempt, pair, payload-measurement, frame-confirmation,
gate and terminal observations. They do not support a nine-disjoint-stage timing
decomposition. Resource IDs are associations, not entanglement certification."

## Statistical and Interpretation Limits

All paired fraction deltas use the full offered denominator. Latency deltas use
only request-ID intersections completing in BOTH arms, averaged per seed.
REPORT.md's cell mean latencies instead pool completed requests; a difference of
those two pooled means need not equal a seed-weighted paired estimate. The
intersection sizes and sample sizes are explicit in analysis.json.

Student-t intervals use three independent seeds, are exploratory and unadjusted
for multiple comparisons, and are not clipped to parameter bounds. Fraction-delta
intervals can therefore extend beyond [-1, 1]; this is a limitation of this small
sample approximation, not a possible observed fraction. Degenerate zero intervals
on matched count differences do not establish equivalence.

Forbidden: universal wireless superiority, physical compatibility/validation,
measured hardware crossover, proof of no crossover elsewhere, critical-path
classical/optical time partition, nine disjoint runtime stages, implemented
entanglement witness, compiled application depth/fidelity, or quantum advantage.
No analytical witness sampling design is supplied or claimed as implemented.

## Verification and Reproduction

Requested interpreter:
<LOCAL_HOME>/AppData/Local/CodexResearch/venvs/dequint-py312/Scripts/python.exe.
Set PYTHONPATH=src and PYTHONDONTWRITEBYTECODE=1. Runner actions were executed in
order: freeze, run, analyze; verify is the read-only audit/reproduction action.
Freeze/run/analyze refuse replacement rather than silently overwriting evidence.

Focused pre-freeze regression: 38 passed in 16.25 seconds, covering the seven new
supplement tests plus existing network/transport tests. Evidence:
tests_pre_freeze_r3.xml. Earlier test attempts remain preserved: an absent pytest
temporary-directory parent caused setup errors, then an unsupported test assumption
that the baseline must contain failed-request pair costs failed. The separate
accounting fixture was shortened to 0.5 ms to exercise that path; the predeclared
48-run design remained at 5 ms and was not tuned from comparative results.

Local deterministic verification recomputes trace audits, summaries, workload
pairing and paired analysis from raw files; checks raw/report/analysis/freeze SHA;
checks full frozen source identities and protected result files. This is not an
independent scientific review. No live subagent slot/capacity inspection tool was
exposed, so no additional worker was spawned or unknown task interrupted.
