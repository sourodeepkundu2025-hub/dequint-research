# EXP-SHORTCUT-01: Original-manuscript quantum-overlay investigation

Scope authorized by the user on2026-10-20: investigate a quantum-shortcut
extension and patch the existing supplied Wiley manuscript, not replace the paper.
Original source: inputs/latest/DEQUINT_Wiley_Converted/dequint_wiley (2).tex,
SHA256 a6a7d5aa9a7a02f2ad0204156812b68fbd6a2122b9195faae5add1b0bb113a0d.
Working copy: manuscript_existing_patch/main.tex. Source archive, previous research
revision, accepted batches and released ZIPs remain unchanged.

## Hypothesis and prior art

HYP-SC01: adding real quantum entanglement links to a bounded-degree overlay can
give logarithmic hop diameter while retaining the underlying mesh/classical NoC.
This does not imply logarithmic measured latency, constant optical cost or novelty
of shortcuts. Schoute et al.1610.05238 and Q-Fly2412.09299 already establish quantum
shortcut/low-diameter approaches. They must be attributed, not rediscovered as new.

Candidate: undirected binary de Bruijn edges i--((2i+b)modN), b in{0,1}, added to
the square mesh with N=2^k. Self loops and duplicates are removed. Appending all k
destination bits supplies a constructive walk of at most k nontrivial edges.
The mesh contributes at most4 neighbors, the overlay at most4, so degree<=8 and
edge count O(N). Proof concerns the quantum-link graph, not a radio shortcut.

## Preregistered comparisons

- Topologies: square mesh, same mesh plus quantum overlay. Classical correction
  assumptions remain identical; direct quantum shortcuts are charged separately.
- Topology census: sides2,4,8,16,32. Exact diameter, mean hops, link/port counts,
  total and maximum optical length; no fitted-asymptotic proof.
- Prospective profiles: fixed10mm footprint with zero loss; fixed10mm footprint
  with1000dB/m and3dB extra insertion loss on non-mesh edges; fixed1mm pitch with
  the same lossy parameters. These deliberately broad sensitivities are not device
  measurements or a calibrated erbium/superconducting platform.
- Finite-resource probe: sides4,8,16; seeds301--306;32 matched requests per cell.
  Global generation capacity16 and per-node optical port count2 held identical
  across topologies. A separate per-link-capacity scenario is allowed only when
  explicitly labeled unequal total generation hardware, not the primary comparison.
- Same endpoint/arrival/deadline workload within each paired condition. Report
  task definition exactly; EPR provisioning is not relabeled as full CNOT execution.
- Raw attempts, failures/retries, offered/completed denominators, conditional
  latency and modeled quantum quality only if actually propagated. Never substitute
  missing whole-circuit fidelity/depth with a graph metric.
- Paired seed differences and Student-t95% intervals; six seeds are a bounded
  sensitivity, not broad superiority. Preserve all negative results.

Exact preregistered execution grid:432 runs =3 profiles x3 side lengths x2
free/restored contracts x2 route metrics (hop-count/expected-service) x6 seeds x2
topologies. Each run offers32 ordered endpoint-CNOT tasks, Poisson1000tasks/s,
relative deadline50ms and maximum100 generation attempts per hop. Gate execution
is at the original target in both topologies; this isolates connectivity from
rendezvous selection. Quality-qualified means modeled process fidelity>=0.9.
The source/config/workload plan is written and hashed before the first batch run.
Classical correction uses an uncontended link sideband, not the existing contended
WiNoC model. A separate capacity1 channel resource serializes each physical edge.
No purification, pair cutoff, finite data storage or native optical execution is
claimed in this bounded probe. Euclidean length is a routing lower bound, not a
fabricated waveguide layout. These deviations are not pooled with prior batches.

## Kill and promotion criteria

Reject unconditional latency O(logN) if per-hop service, link loss, optical budget,
or queue load grows without bound with N. Promote only the analytic hop bound
unless independent physical-service assumptions and adequate execution support
the stronger statement. No success-only comparison may hide attrition. No physical
feasibility or depth claim is validated by topology/cost experiments.

The original manuscript is patched incrementally. Its legacy numerical plots
remain visibly identified as unreconciled source material until replaced by
matched result records. Do not call that intermediate PDF submission-ready.
