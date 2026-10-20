"""Qiskit DAG timing replay using the existing per-CNOT network resource path.

This is not quantum-state execution: Network resets channels at each CNOT, and
single-qubit gates model resource occupancy only. Logical/basis circuit depths
are not compiled physical routing depths. No application fidelity is inferred.
"""

from collections.abc import Mapping
import hashlib
import json
import math
from numbers import Integral

from qiskit import QuantumCircuit, qasm3, transpile
from qiskit.circuit.library import quantum_volume
from qiskit.converters import circuit_to_dag
from qiskit.dagcircuit import DAGOpNode
from qiskit.synthesis import adder_ripple_c04, synth_qft_full

from .kernel import Signal
from .network import Job, Network
from .workload import Request


def _seed(seed):
    if isinstance(seed, bool) or not isinstance(seed, Integral) or not 0 <= seed < 2**32:
        raise ValueError("seed must be an integer in [0, 2**32)")
    return int(seed)


def build_circuit(name, size, seed):
    """Build an unmeasured logical input; CDKM size is bits per addend.

    QFT includes its final swaps. CDKM uses Qiskit's full carry-in/out builder
    (2*size+2 qubits). Quantum volume has depth=size and is bounded to 8 qubits.
    """
    seed = _seed(seed)
    if isinstance(size, bool) or not isinstance(size, Integral) or size < 1:
        raise ValueError("size must be a positive integer")
    size = int(size)
    if name == "ghz":
        circuit = QuantumCircuit(size, name=f"ghz_{size}")
        circuit.h(0)
        for qubit in range(1, size):
            circuit.cx(qubit - 1, qubit)
    elif name == "qft":
        circuit = synth_qft_full(size, do_swaps=True, name=f"qft_{size}")
    elif name in {"cdkm", "cdkm_ripple_carry_adder"}:
        circuit = adder_ripple_c04(size, kind="full")
        circuit.name = f"cdkm_{size}"
    elif name == "quantum_volume":
        if size > 8:
            raise ValueError("quantum_volume is bounded to at most 8 qubits")
        circuit = quantum_volume(size, depth=size, seed=seed)
        circuit.name = f"quantum_volume_{size}_{seed}"
    else:
        raise ValueError(f"Unknown circuit: {name}")
    return circuit


def _export_mapping(mapping, qubits=None):
    return {str(q): list(mapping[q]) for q in (sorted(mapping) if qubits is None else qubits)}


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class _ReplayNetwork(Network):
    """Observe inherited execution, without replacing CNOT routing or service."""

    def __init__(self, replay):
        self.replay = replay
        self.task_rows = {}
        # Network needs a workload to initialize its horizon; this request is
        # never executed. Actual CNOT requests are created when DAG nodes ready.
        bootstrap = Request(-1, (0, 0), (0, 0), 0, replay.deadline_s)
        super().__init__(replay.config, [bootstrap], replay.seed,
                         run_id="application_replay", trace=True)

    def emit(self, owner, action, **fields):
        super().emit(owner, action, **fields)
        operation_id = int(owner)
        if operation_id not in self.replay._records:
            return
        row = self.replay._records[operation_id]
        if action in {"payload_measured", "pauli_frame_confirmed"}:
            qubit = row["qubits"][0 if fields["operand"] == "a" else 1]
            if action == "payload_measured":
                if self.replay.mapping[qubit] != fields["source"]:
                    raise RuntimeError("Payload movement disagrees with logical mapping")
                self.replay.mapping[qubit] = tuple(fields["destination"])
            self.replay.mapping_history.append({
                "time_s": self.kernel.now, "operation_id": operation_id,
                "qubit": qubit, "action": action,
                "position": list(self.replay.mapping[qubit]),
            })
        elif action == "two_qubit_gate":
            row["gate_finished_s"] = self.kernel.now
        elif action == "request_terminal":
            self.task_rows[operation_id] = self.rows[-1]

    def _acquire(self, resource, job, amount=1):
        lease = yield from super()._acquire(resource, job, amount)
        if lease is not None and resource.name.startswith("gate:"):
            self.replay._records[job.request.request_id]["gate_started_s"] = self.kernel.now
            self.emit(job.owner, "application_gate_started", resource=resource.name)
        return lease


class ApplicationReplay:
    """Replay a fixed unitary circuit under one policy and absolute deadline.

    ``initial_mapping`` is a qubit-index mapping or coordinate sequence. Multiple
    logical qubits may share a core, as Network has no payload-core capacity
    model. ``single_qubit_gate_s`` defaults explicitly to config.gate_s; it is
    a declared local resource duration, not a hardware-calibrated u-gate time.
    ``network`` is exposed for focused instrumentation, not as a second runner.

    Operation started_s includes routing/queue time; gate_started_s and
    gate_finished_s delimit actual gate resource service. Final mapping records
    last known locations, not certified usable states after failed operations.
    """

    def __init__(self, config, circuit, initial_mapping, seed, deadline_s=.2, *,
                 single_qubit_gate_s=None):
        self.config = config.validate()
        self.seed = _seed(seed)
        if not math.isfinite(deadline_s) or deadline_s <= 0:
            raise ValueError("deadline_s must be finite and positive")
        self.deadline_s = float(deadline_s)
        self.single_qubit_gate_s = config.gate_s if single_qubit_gate_s is None else single_qubit_gate_s
        if not math.isfinite(self.single_qubit_gate_s) or self.single_qubit_gate_s < 0:
            raise ValueError("single_qubit_gate_s must be finite and nonnegative")
        self.single_qubit_gate_s = float(self.single_qubit_gate_s)
        if not isinstance(circuit, QuantumCircuit) or circuit.num_qubits < 1:
            raise ValueError("circuit must be a QuantumCircuit with at least one qubit")
        if circuit.num_clbits:
            raise ValueError("Timing replay does not support classical wires or control")
        if circuit.parameters:
            raise ValueError("Bind circuit parameters before timing replay")
        self.circuit = circuit.copy()
        mapping = dict(initial_mapping) if isinstance(initial_mapping, Mapping) else dict(enumerate(initial_mapping))
        if set(mapping) != set(range(circuit.num_qubits)):
            raise ValueError("initial_mapping must map every logical qubit exactly once")
        for qubit, position in mapping.items():
            if (not isinstance(qubit, Integral) or isinstance(qubit, bool) or
                    not isinstance(position, (tuple, list)) or len(position) != 2 or
                    any(isinstance(v, bool) or not isinstance(v, Integral) or not 0 <= v < config.mesh_side
                        for v in position)):
                raise ValueError("initial_mapping contains an invalid qubit or core coordinate")
        self.initial_mapping = {int(q): tuple(int(v) for v in p) for q, p in mapping.items()}
        self.mapping = dict(self.initial_mapping)
        # No coupling map/layout: this is basis decomposition, not physical routing.
        self.basis_circuit = transpile(self.circuit, basis_gates=["u", "cx"],
                                       optimization_level=0, seed_transpiler=self.seed)
        dag = circuit_to_dag(self.basis_circuit)
        ordered = list(dag.topological_op_nodes())
        if any(node.name not in {"u", "cx", "barrier"} for node in ordered):
            raise ValueError("Unsupported instruction: only unitary u/cx and barriers can be replayed")
        indices = {node._node_id: i for i, node in enumerate(ordered)}
        self._records = {}
        for i, node in enumerate(ordered):
            self._records[i] = {
                "operation_id": i, "name": node.name,
                "qubits": [self.basis_circuit.find_bit(q).index for q in node.qargs],
                "params": [float(p) for p in node.op.params],
                "predecessors": sorted({indices[p._node_id] for p in dag.predecessors(node)
                                        if isinstance(p, DAGOpNode)}),
                "status": "pending", "completed": False, "terminal_reason": "",
                "deadline_s": self.deadline_s, "ready_s": None, "started_s": None,
                "finished_s": None, "gate_started_s": None, "gate_finished_s": None,
                "mapping_before": None, "mapping_after": None, "counters": {},
            }
        input_qasm = qasm3.dumps(self.circuit)
        basis_qasm = qasm3.dumps(self.basis_circuit)
        self.circuit_metadata = {
            "name": self.circuit.name, "num_qubits": self.circuit.num_qubits,
            "input_depth": self.circuit.depth(), "input_operation_count": len(self.circuit.data),
            "input_count_ops": dict(self.circuit.count_ops()), "input_qasm": input_qasm,
            "input_qasm_format": "OpenQASM 3", "input_sha256": _digest(input_qasm),
            "basis": ["u", "cx"], "basis_depth": self.basis_circuit.depth(),
            "basis_operation_count": len(self.basis_circuit.data),
            "basis_count_ops": dict(self.basis_circuit.count_ops()), "basis_qasm": basis_qasm,
            "basis_qasm_format": "OpenQASM 3", "basis_sha256": _digest(basis_qasm),
            "seed_transpiler": self.seed, "optimization_level": 0,
            "depth_scope": "logical input and unplaced basis decomposition; not physical routing depth",
        }
        fixed_input = {"input_sha256": _digest(input_qasm), "basis_sha256": _digest(basis_qasm),
                       "initial_mapping": _export_mapping(self.initial_mapping), "seed": self.seed,
                       "deadline_s": self.deadline_s, "single_qubit_gate_s": self.single_qubit_gate_s}
        self.application_input_sha256 = _digest(json.dumps(fixed_input, sort_keys=True))
        self.mapping_history = []
        self.network = _ReplayNetwork(self)
        self._signals = {}
        self._has_run = False

    def _dependencies(self, row):
        """Release on all successes or cancel immediately on the first failure."""
        ready = Signal(self.network.kernel)
        remaining = {"count": len(row["predecessors"])}

        def resolved(success):
            if not success:
                ready.succeed(False)
            else:
                remaining["count"] -= 1
                if remaining["count"] == 0:
                    ready.succeed(True)

        for predecessor in row["predecessors"]:
            self._signals[predecessor].then(resolved)
        if not remaining["count"]:
            ready.succeed(True)
        return ready

    def _local_gate(self, request, row):
        network = self.network
        job = Job(request, [])
        lease = yield from network._acquire(network.cores[request.source].gate, job)
        success = False
        if lease is not None:
            try:
                success = yield from network._pause(self.single_qubit_gate_s, job)
                row["gate_finished_s"] = network.kernel.now
                network.emit(job.owner, "single_qubit_gate", qubit=row["qubits"][0],
                             duration_s=self.single_qubit_gate_s, completed=success)
            finally:
                lease.release()
        row["counters"] = dict(job.counters)
        row["terminal_reason"] = "completed" if success else job.reason
        return success

    def _operation(self, row):
        network = self.network
        if not (yield self._dependencies(row)):
            row["status"] = "cancelled"
            row["terminal_reason"] = "predecessor_failed"
            row["blocked_by"] = [p for p in row["predecessors"]
                                 if self._records[p]["status"] in {"failed", "cancelled"}]
            row["finished_s"] = network.kernel.now
            network.emit(str(row["operation_id"]), "application_operation_cancelled")
            return False
        row["ready_s"] = network.kernel.now
        qubits = row["qubits"]
        row["mapping_before"] = _export_mapping(self.mapping, qubits)
        success = False
        if row["name"] == "barrier":
            row["started_s"] = network.kernel.now
            success = True
            row["terminal_reason"] = "completed"
        elif network.kernel.now >= self.deadline_s:
            row["terminal_reason"] = "deadline"
        else:
            row["started_s"] = network.kernel.now
            network.emit(str(row["operation_id"]), "application_operation_started", qubits=qubits)
            request = Request(row["operation_id"], self.mapping[qubits[0]],
                              self.mapping[qubits[-1]], network.kernel.now, self.deadline_s)
            if row["name"] == "cx":
                yield from network._execute(request)
                task = network.task_rows[request.request_id]
                success = task["completed"]
                row["terminal_reason"] = task["terminal_reason"]
                row["counters"] = {key: task[key] for key in Job(request, []).counters}
            else:
                success = yield from self._local_gate(request, row)
        row["completed"] = bool(success)
        row["status"] = "completed" if success else "failed"
        row["finished_s"] = network.kernel.now
        row["mapping_after"] = _export_mapping(self.mapping, qubits)
        network.emit(str(row["operation_id"]), "application_operation_terminal",
                     completed=bool(success), reason=row["terminal_reason"])
        return bool(success)

    def run(self):
        """Return JSON-compatible metadata, operation/network traces and mappings."""
        if self._has_run:
            raise RuntimeError("An ApplicationReplay instance can run only once")
        self._has_run = True
        network = self.network
        for i, row in self._records.items():
            self._signals[i] = network.kernel.spawn(self._operation(row))
        network.kernel.run()
        if any(not signal.done for signal in self._signals.values()):
            raise RuntimeError("An application operation did not terminate within the horizon")
        rows = list(self._records.values())
        resources = [*network.generators.values(), *(r for c in network.cores.values()
                     for r in (c.memories, c.gate)), *network.fabric.wired.values()]
        if network.pool is not None:
            resources.append(network.pool)
        if (any(r.used or r.waiting_units for r in resources) or network.pairs.ready or
                not network.fabric.radio_idle):
            raise RuntimeError("Application terminated with leaked network resources")
        completed = all(row["completed"] for row in rows)
        makespan = max((row["finished_s"] for row in rows), default=0.0)
        counts = {key: sum(row["counters"].get(key, 0) for row in rows)
                  for key in Job(network.requests[0], []).counters}
        summary = {
            "kind": "application_timing_replay", "seed": self.seed, "policy": self.config.policy,
            "placement": self.config.placement, "classical": self.config.classical,
            "application_input_sha256": self.application_input_sha256, "deadline_s": self.deadline_s,
            "offered_operations": len(rows), "completed": completed,
            "offered_cnot_gates": sum(row["name"] == "cx" for row in rows),
            "completed_cnot_gates": sum(row["name"] == "cx" and row["completed"] for row in rows),
            "completed_single_qubit_gates": sum(row["name"] == "u" and row["completed"] for row in rows),
            "completed_operations": sum(row["completed"] for row in rows),
            "failed_operations": sum(row["status"] == "failed" for row in rows),
            "cancelled_operations": sum(row["status"] == "cancelled" for row in rows),
            "application_makespan_s": makespan,
            "completed_application_makespan_s": makespan if completed else None,
            "single_qubit_gate_s": self.single_qubit_gate_s,
            "end_to_end_state_fidelity": None, "compiled_physical_circuit_depth": None,
            "fidelity_scope": "timing replay only; inherited per-CNOT channels reset; no application fidelity",
            "mapping_scope": "last known payload locations; failures do not certify usable states or frames",
            "classical_wait_s": network.fabric.total_wait_s, "classical_packets": network.fabric.packets,
            "classical_lost_packets": network.fabric.lost_packets,
            "classical_bit_hops": network.fabric.transmitted_bits,
            "radio_busy_s": network.fabric.busy_radio_s,
            "native_events": network.kernel.timeline.run_counter, "resource_leaks": 0, **counts,
        }
        # Controller wall cost is deliberately excluded from deterministic replay output.
        cnot_tasks = [{key: value for key, value in row.items() if key != "controller_wall_s"}
                      for row in sorted(network.rows, key=lambda row: row["request_id"])]
        exported_config = {key: "Infinity" if value == math.inf else value
                           for key, value in self.config.to_dict().items()}
        return {"summary": summary, "config": exported_config, "circuit": self.circuit_metadata,
                "initial_mapping": _export_mapping(self.initial_mapping),
                "final_mapping": _export_mapping(self.mapping),
                "failed_operand_qubits": sorted({q for row in rows if row["status"] == "failed"
                                                  for q in row["qubits"]}),
                "operations": rows, "mapping_history": self.mapping_history,
                "cnot_tasks": cnot_tasks, "events": network.events}
