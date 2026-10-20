# Reviewer 2/3 Supplement Protocol v1

## Authority and Evidence Class

This is an additive, predeclared bounded supplement. Only its runner, this protocol,
its test file, and results/review_supplement_v1 are owned. Existing src, manuscripts,
and frozen results are read-only. Network and ModelConfig are used without edits,
monkeypatches, or replacement implementations. The backend is SeQUeNCe's native
Timeline with the existing declared Bernoulli optical and Pauli-channel model,
not a full native-photonic mesh or measured physical device. All configurations
are prospective. No paid service, hardware run, publication, or commit is involved.

## Frozen Design and Stop Rule

Full factorial: excitation 20,000 or 2,000,000 Hz; Poisson offered load 1,000 or
100,000 requests/s; wired or radio; HH or geodesic minimax (API policy midpoint);
seeds 701, 702, 703; 24 requests per run. Total 48 runs and 1,152 offered CNOTs.
This finite batch is not steady state. No selection of seeds/cells after outcomes.
No parameter tuning or favorable-profile substitution. A source drift or exception
stops the batch; preserve partial events and explicit administrative censor counts.
No automatic retry or overwrite of an existing freeze or run directory.

Same task: ordered two-operand CNOT, 4x4 mesh, free output placement for every arm.
HH moves one operand to the other's original core. Minimax uses geodesic meeting
and the same gate; it is not compared against mere state delivery. This supplement
does not cover restored placement or application-circuit fidelity/depth.

Fixed across all cells: deadline 5 ms after each arrival; memory T2=10 ms; cutoff
20 ms; 8 communication memories/core; one generator/edge; no pooling/purification;
maximum 1,000 attempts and 500,000 native events/run. These finite memory/deadline
values are a prospective sensitivity choice, not hardware-calibrated. Other
parameters remain ModelConfig defaults, saved exhaustively in run_plan.json.
Wired: 1 GHz, 16 bits, two router cycles; radio: 12 Gbit/s, one channel, 2 ns token
and startup. Raw Bell fidelity .99, minimum process fidelity .90. No packet loss
or outage is injected; deadline/contention and quality failures remain possible.

For each load/seed, make_workload is invoked with identical arguments for every
excitation/policy/fabric. Thus arrivals, endpoint order, IDs and deadlines are
identical; endpoints are also identical between loads for a seed, with arrival
times scaled by offered rate. Component streams are seeded and request/link/tag
keyed by the unchanged model. Distinct routes or causal schedules need not produce
identical draws; matching seeds is not a claim of identical path outcomes.

## Freeze and Integrity

Before constructing any experimental Network, freeze.json stores UTC time, complete
non-generated src file SHA-256 inventory (excluding __pycache__ and .pyc), protocol,
runner and test hashes, dependency declarations, environment versions, the full
plan hash, and each saved workload's raw and model-semantic hashes. It also hashes
all preexisting results outside this owned result directory. Tests precede the
freeze. Check source inventory before each run and after the batch. Final verify
checks protected result hashes without rewriting those files. An extra sibling
file created by another worker is not a modification of a preexisting frozen file.

Each run retains requests.json, all events.jsonl (not just one seed), original model
summary.json, audit.json, started.json linking the freeze hash, and raw_sha256.json.
All writes are exclusive. Analysis reads saved raw files and independently
recomputes counts, workload pairing, terminal partitions and consumption audit.
Local deterministic reconciliation is not independent scientific approval.

## Endpoints and Inference

Primary: completed by deadline AND process fidelity >= .90 divided by ALL offered.
Secondary: completed/offered; failed/offered; exact terminal reasons; mean latency
and fidelity conditional on completion; total attempts and accepted raw pairs;
payload Bell pairs consumed over all requests and failed requests; all pair
consumption events including discards; classical and quantum-resource wait sums.
Deadline failures are operational outcomes and incomplete observations of eventual
completion, not successes or missing denominators. Their latency and fidelity are
not imputed. Administrative censoring is separately recorded only on exceptions.
Never report conditional success latency as all-offered latency.

Report every 16 profile cell's exact counts (72 offered each). Paired seed contrasts:
radio-minus-wired, minimax-minus-HH, and 2MHz-minus-20kHz. Fraction differences use
all 24 offered/seed; latency differences use only matched requests completing in
BOTH arms, then average per seed. Report that intersection's sample size and null
if empty. Two-sided Student-t 95% intervals across independent seed means (n=3,
df=2 when all available), exploratory and unadjusted for multiple comparisons.
Degenerate zero intervals mean observed agreement, not proof of equivalence.
Correlated requests within a run are not independent inference replicates.

Generation-service sensitivity is the excitation contrast, not measured optical
hardware acceleration. A descriptive wired/radio latency crossover is a sign
reversal of the radio-minus-wired common-completion latency delta between the two
excitation profiles at fixed load/policy. Intervals containing zero make the
direction inconclusive. Both profiles having the same sign is no observed reversal;
it is not proof there is no crossover elsewhere. Do not claim classical dominance
from wait sums, nor interpolate a crossover frequency from two points. No additive
classical/generation latency partition is available from these trace actions.

## Exact Trace Action and Metric Mapping

The following are overlapping per-request observations, NOT nine disjoint stages,
not a bijection to a conceptual protocol figure, and not a timing decomposition.
An absent action means not observed, not that a conceptual stage has zero cost.

| Observation/metric | Explicit action/field | Interpretation and limit |
|---|---|---|
| Arrived | request_arrived | Explicit task arrival, endpoints, deadline |
| Route selected | route_decision | Meeting selected; no modeled route-compute delay; controller wall time is separate |
| Resource admission | resource_admission, resource, admitted, wait_s | Completed admission/denial observation, bucket memory/bsm/gate; no resource-release trace |
| Complete EPR attempts | complete_epr_attempt, accepted | Complete two-round attempt only; epr_attempts counter can include an interrupted attempt |
| Accepted raw pairs | complete_epr_attempt with accepted=true; raw_pairs row | Bernoulli accepted pair, not entanglement witness or physical certification |
| Pair available | pair_ready, pair_id | Resource association; not independent entanglement verification |
| Purification decision | purification, accepted | Only if explicitly observed; disabled in this design, no claimed runtime witness |
| Payload BSM | payload_measured, pair_id; pair_consumed reason=payload_bell_measurement | Payload consumed_pairs and quantum_hops, including failures after measurement |
| Frame confirmed | pauli_frame_confirmed | Explicit classical correction confirmation, not merely a send |
| Gate attempt | two_qubit_gate, completed | Gate can be attempted but not complete; count completed flag separately if interpreting success |
| Terminal | request_terminal, completed, quality_qualified, reason | Exactly one per request; row terminal_reason is authoritative final recorded reason, not unique causal mechanism |
| Classical trace | classical_wired or classical_radio, tag prefix control/herald/correction/purification | Wired event is a completed directed hop, radio event a service outcome with completed flag; neither is a logical packet count |
| Classical wait | model summary classical_wait_s | Existing fabric's accounted waits; not complete all-path classical time or all aborted queue waits |
| Quantum-resource wait | row quantum_queue_wait_s | Sum of admissions, can overlap between operands; not critical-path latency |
| Any pair disposal | pair_consumed, reason | Includes payload use, purification inputs and abort discards; distinct from consumed_pairs counter |
| Partial attempt | row epr_attempts minus complete_epr_attempt count | Interrupted/not completed attempts; no invented completion event |

audit.json retains every action count, overlapping stage request/event counts,
classical action/tag buckets, admission outcomes, pair-consumption reasons and exact
terminal failure reasons. Exclusive terminal outcome partition is completed_qualified,
completed_unqualified, or failed:<exact recorded reason>. It sums to all recorded
requests. Failed resource_deadline/deadline, classical-unconfirmed, pair-expired and
attempt-bound reasons are never double-counted as separate terminal stages. The
shared Job reason can be overwritten by concurrent operands; no causal attribution
beyond the final recorded value is asserted. A model exception has no invented
request_terminal; missing rows are explicitly administratively censored.

## Claim Boundaries and Reproduction

No entanglement-witness sampling runtime is added. Existing IDs/quality scalars do
not certify entanglement; analytical witness design is outside this bounded batch.
Nulls, failed cells and uncertainty must remain visible. No universal superiority,
physical wired/radio compatibility, hardware crossover, quantum advantage, nine-stage
disjoint timing, compiled depth, or production-readiness claim follows.

Use the requested dequint-py312 Python with PYTHONPATH=src and
PYTHONDONTWRITEBYTECODE=1. Run tests with cache disabled and a basetemp under this
owned result directory. Runner actions in order: freeze, run, analyze, verify.
No frozen module, manuscript, existing result, handoff, or other shared file is edited.
