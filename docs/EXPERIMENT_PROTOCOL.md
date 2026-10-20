# Frozen experiment protocol v1

This protocol precedes the comparative experiment batch. A 40-request adaptive-only
smoke test checked execution, not comparative performance. Parameters were not fitted
to comparative results. All profiles are prospective sensitivity models, not an
identified physical implementation.

## Endpoint and comparisons

Every request is the same ordered two-operand CNOT task. Free placement permits both
outputs at the selected gate core. Restored placement returns each output to its
original core; this includes the correlated propagation of Pauli errors through CNOT.
HH sends one operand to the other's original core, executes that same gate, and returns
it when restoration is required. Neither policy is a mere state-delivery baseline.

Primary endpoint: fraction of all offered requests completed by deadline with process
fidelity >= 0.90. Also report completion fraction, conditional mean and p95 latency,
conditional process fidelity, attempts, accepted raw pairs, consumed teleportation
pairs, queue wait, classical bit-hops and event count. No timed-out request is silently
excluded from a success denominator. Latency is explicitly conditional on completion.

Policies: HH, geodesic minimax midpoint, observable-queue-only selection, queue plus
predicted quality selection. Geodesic candidates include endpoints. No policy sees
future arrivals or random draws. Quality weight is fixed at 0.002 seconds, not tuned.
The heuristic is a candidate, not a certified novel or optimal algorithm.

## Design

Frozen seeds 101--110, 48 independent gate requests per seed. Poisson arrival rates
1000 and 10000 requests/s on a 4x4 mesh. Both free and restored placement are primary.
The same arrival/endpoints hash is required within each comparison cell. Component
random streams are request/link/tag keyed; changed physical paths need not have
identical sampled attempts. Inference uses independent seed replicates, not treating
all correlated per-request observations as independent trials.

Secondary checks at 10000 requests/s, free placement: shared radio; short T2=3.3us;
10% packet loss; complete source outage; raw F=0.7 with one ideal BBPSSW round and
explicit input/output Werner twirls; pooled heralding capacity 1 and 4. Pooling means
shared link-generation servers on the same mesh, not a physical central-source star.
Scaling uses 2x2, 8x8 and 16x16 meshes at offered rate 625 per core, 48 requests/seed,
so it is a sparse finite-batch sensitivity test, not a steady-state capacity result.

Ten seeds and 48 requests are a bounded first comparative batch. Report its limited
power; do not claim a universally superior policy or optimized hardware deployment.
Use paired seed differences and a two-sided Student-t 95% confidence interval.
No post-hoc selection of seeds, favorable thresholds, or only positive cells.

## Explicit exclusions

No fabricated O(log N), circuit-depth, energy, area, thermal, QPU or FPGA/ASIC result.
Sequential mesh payload hops have a square-root-in-core-count distance scale.
Gate-task latency is not compiled application circuit depth. Full mesh uses native
SeQUeNCe Timeline with declared optical Bernoulli/Pauli abstractions. Native photon,
detector, memory, swapping, BBPSSW and teleportation checks are separate reference
experiments, not evidence that every mesh event uses native optical components.
No claim of full application DAG scheduling, background pre-generation, or measured
wireless cryogenic compatibility. Classical ns-scale parameters are assumptions.
