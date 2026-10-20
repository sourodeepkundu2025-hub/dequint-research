# Trace Audit: Reviewer Supplement v1

Derived from all 48 runs' events.jsonl through the frozen runner's audit_trace;
every audit.json is recomputed from the saved trace during verify. The counts below
are sums of those verified per-run audits, not inferred conceptual stages.

## Explicit Actions

| Exact action | Events |
|---|---:|
| request_arrived | 1152 |
| route_decision | 1152 |
| resource_admission | 10246 |
| complete_epr_attempt | 15936 |
| pair_ready | 3022 |
| pair_consumed | 3022 |
| payload_measured | 3022 |
| pauli_frame_confirmed | 3022 |
| two_qubit_gate | 1138 |
| classical_wired | 18397 |
| classical_radio | 18397 |
| request_terminal | 1152 |
| Total emitted trace records | 79658 |

No purification decision is observed: purification is disabled in this design.
There are 15,946 started EPR attempts in request counters, 15,936 explicit completed
attempt actions, and 10 started-but-not-completed attempts. Do not silently count
those ten as completed generation attempts. Accepted raw pairs total 3,022.

Resource observations: 6,072 admitted memory acquisitions, 3,032 admitted generator
acquisitions, 1,138 admitted gate acquisitions, and 4 denied generator acquisitions.
No memory or gate denial action is present. This is an observation, not a claim
that those resources could never cause failures in other configurations.

For EACH fabric, classical action tags comprise 948 control, 15,938 herald, and
1,511 correction observations. A wired observation is a directed hop; a radio
observation is a service outcome. Equal observed action counts do not make these
unlike units equivalent logical packet counts. Source-equals-destination sends
have no classical_wired/classical_radio action. Missing service events are not
invented, and trace timestamps do not provide a complete service-time partition.

## Exclusive Terminal Partition

| Final request outcome | Requests |
|---|---:|
| completed_qualified | 736 |
| completed_unqualified | 402 |
| failed:deadline | 10 |
| failed:resource_deadline | 4 |
| Total offered | 1152 |

All 1,152 requests have exactly one terminal action. Administrative censoring is
zero; no run exception occurred. Deadline failures are incomplete observations of
eventual service, not missing offered requests. Quality is not availability:
402 completed requests failed the declared process-fidelity qualification.

All 3,022 pair_consumed actions have reason payload_bell_measurement in this batch;
36 belong to failed requests and are included in total consumed pairs. No abort
discard or purification-input consumption event is observed. These zero observed
categories must not be generalized to other profiles. The general audit keeps
all disposal reasons separate from the model's payload-only consumed_pairs.

## What This Does Not Establish

The request observations overlap. They are not nine disjoint protocol stages,
and summing waits across resources/operands does not reconstruct critical-path
latency. The final recorded failure reason is exclusive for accounting but may
have been overwritten by concurrent operands; it is not a unique causal diagnosis.
pair_ready/ENT IDs and prospective process-fidelity scalars are not a runtime
entanglement witness. Exact action/field mapping is in the frozen protocol.
