# DEQUINT claim-to-SeQUeNCe map

The user-supplied latest archive is preserved in inputs/original. Its statements are
targets for assessment, not instructions to manufacture a favorable outcome.

| Submitted claim or reviewer issue | Upstream component / extension | Disposition |
|---|---|---|
| Per-link entanglement generation | Native generation.barret_kok; extension network._raw_pair | Existing architecture, not new. Full mesh uses explicitly abstracted complete two-round heralding trials. Native optics checked separately. |
| Quantum teleportation | Native TeleportApp and teleportation protocol; Pauli model independently checked by Qiskit | Implemented at separate reference and scalable abstraction levels; no hardware claim. |
| Multi-hop communication | Sequential mesh payload teleportation | Implemented; not falsely described as end-to-end entanglement swapping. |
| Entanglement swapping | Native swapping module reference | Separate reference experiment, not in the payload-hop routing path. A swapping-based mesh protocol remains a different architecture. |
| BBPSSW | Native purification reference; exact Werner formula/Qiskit validation; optional mesh preparation | Ideal operations and explicit Werner input/output twirls. Success consumes two inputs; failures and classical comparison cost charged. |
| Two-way/bidirectional teleportation | Geodesic two-operand gate co-location | Renamed rendezvous/co-location. Does not swap unknown endpoint states. Known prior art. |
| HH vs rendezvous speedup | Same ordered CNOT under free/restored placement | New runs replace old percentages; all EPR consumption and failed requests retained. |
| Congestion fallback | Observable queue + quality candidate over geodesic gate cores | Implemented candidate and queue-only ablation; not proven optimal or broadly original. |
| Time synchronization | Shared picosecond event clock, explicit request/herald/correction sequencing | Ideal synchronized-clock assumption. No physical clock-jitter or oscillator synchronization validation. |
| Fidelity at every stage | Conditional Pauli channels, waiting-time dephasing, CNOT process fidelity | Model-derived channel quality; not single-copy entanglement certification. |
| Stage-8 entanglement verification | Pair owner/ID/single-use checks | Resource association only. Original entanglement-verification wording withdrawn. |
| Nine-stage pipeline | Raw timestamped event traces | Events are observable accounting stages, not a novelty claim or fixed-delay performance simulation. |
| Wireless NoC advantage | Directed FIFO wired mesh vs contended shared token radio | ns-scale prospective parameters, finite capacity and losses; no guaranteed advantage. Token model is not a validated implementation of 2DMAC. |
| 740 vs 540000 pairs/s | Distinct attempted/accepted raw pairs, consumed pairs, completed and quality-qualified gates | Inconsistent old figures retired; denominators and observation window exported per run. |
| O(log N) scaling | Side lengths 2,4,8,16; explicit sequential hop counts | Withdrawn. Classical radio cannot shorten quantum mesh distance. |
| Circuit-depth reduction | Gate-task service times only | Not claimed. Application DAG mapping and native-gate-depth comparison still required. |
| Centralized architecture benchmark | Shared link-generation capacity 1 or 4 on unchanged mesh | Resource-pooling ablation only, not a stand-in for a multiplexed physical central-source star. |
| Area/thermal/cryogenic compatibility | No implementation in SeQUeNCe | Withdraw unsupported device claims. Requires independent circuit/electromagnetic/thermal engineering, not network simulation. |
| Faults and relevant environment | Outage, packet loss, deadline, short memory, purification stress | Simulation sensitivity, not physical prototype qualification. |

## Closest prior work and candidate contribution

Suance et al., [arXiv:2505.11195](https://arxiv.org/abs/2505.11195), already describe
per-link BSM and two-sided gate co-location. Those are baselines here, not DEQUINT
novelty. Their discussion identifies intermediate-core congestion as a limitation.

Zhan et al., [arXiv:2502.01964](https://arxiv.org/abs/2502.01964), extend SeQUeNCe for
adaptive continuous entanglement generation. This rebuild does not reproduce their
background-generation policy; generic adaptivity or fidelity awareness is not new.

Recent adjacent work includes [InterQ](https://arxiv.org/abs/2605.17769),
[coherence-aware routing](https://arxiv.org/abs/2609.38380), and
[resource-aware site selection](https://doi.org/10.1140/epjqt/s40507-026-00519-6).
These prevent a broad 'first queue/fidelity-aware scheduling' assertion. This is a
targeted positioning check, not a complete systematic review or novelty clearance.
In addition, [Pirker et al.](https://arxiv.org/abs/2605.03336) already implement
resource-centric task-based centralized control in SeQUeNCe. A task-based framework
or simulator integration alone cannot be the proposed new architecture.

The bounded candidate contribution is an auditable *task-equivalent* multicore
co-location benchmark, with free/restored placement, quantum resource failure,
contended classical service, quality-qualified goodput and independently checked
channel semantics. Its quality-aware heuristic must beat static and queue-only
controls on independent seeds to support an algorithmic improvement claim. If it
does not, report the negative result and retain the reproducibility contribution.
