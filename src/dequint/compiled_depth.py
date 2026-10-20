"""Ideal mapped remote-CNOT evidence; no conversion of network time to depth."""

from collections import Counter
from dataclasses import dataclass
from itertools import combinations

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit import Clbit
from qiskit.quantum_info import DensityMatrix, Operator, partial_trace
from qiskit.transpiler import CouplingMap


BASIS = ["u", "cx"]
SEEDS = (201, 202, 203, 204)
TOLERANCE = 1e-9


@dataclass(frozen=True)
class CoreGraph:
    name: str
    nodes: tuple
    links: tuple

    @property
    def num_qubits(self):
        return 3 * len(self.nodes)

    def data(self, node, slot=0):
        return 3 * self.nodes.index(node) + slot

    def comm(self, node):
        return self.data(node, 2)

    @property
    def edges(self):
        edges = []
        for node in self.nodes:
            edges.extend(combinations(range(self.data(node), self.data(node) + 3), 2))
        edges.extend((self.comm(a), self.comm(b)) for a, b in self.links)
        return sorted((a, b) for x, y in edges for a, b in ((x, y), (y, x)))

    @property
    def homes(self):
        return [self.data(self.nodes[0]), self.data(self.nodes[-1])]


def cases():
    for length in (3, 5):
        nodes = tuple((i, 0) for i in range(length))
        yield CoreGraph(f"line{length}", nodes, tuple(zip(nodes, nodes[1:])))
    nodes = ((0, 0), (0, 1), (1, 0), (1, 1))
    yield CoreGraph("square2", nodes, (((0, 0), (0, 1)), ((0, 0), (1, 0)),
                                      ((0, 1), (1, 1)), ((1, 0), (1, 1))))


def xy_path(source, destination):
    path = [source]
    x, y = source
    while x != destination[0]:
        x += 1 if destination[0] > x else -1
        path.append((x, y))
    while y != destination[1]:
        y += 1 if destination[1] > y else -1
        path.append((x, y))
    return path


def teleport_hop(circuit, source_data, source_comm, dest_comm, dest_data, zbit, xbit):
    """Gate-link surrogate, with explicit BSM, feed-forward and storage SWAP."""
    for qubit in (source_comm, dest_comm, dest_data):
        circuit.reset(qubit)
    circuit.h(source_comm)
    circuit.cx(source_comm, dest_comm)
    circuit.cx(source_data, source_comm)
    circuit.h(source_data)
    circuit.measure(source_data, zbit)
    circuit.measure(source_comm, xbit)
    with circuit.if_test((circuit.clbits[xbit], True)):
        circuit.x(dest_comm)
    with circuit.if_test((circuit.clbits[zbit], True)):
        circuit.z(dest_comm)
    circuit.swap(dest_comm, dest_data)
    for qubit in (source_data, source_comm, dest_comm):
        circuit.reset(qubit)


def build_teleport(graph, policy, *, restore=True):
    if policy not in {"endpoint", "rendezvous"}:
        raise ValueError("policy must be endpoint or rendezvous")
    source, target = graph.nodes[0], graph.nodes[-1]
    route = xy_path(source, target)
    meeting = target if policy == "endpoint" else route[len(route) // 2]
    paths = [xy_path(source, meeting), xy_path(target, meeting)]
    hops = sum(len(path) - 1 for path in paths) * (2 if restore else 1)
    circuit = QuantumCircuit(graph.num_qubits, 2 * hops, name=f"{graph.name}_{policy}")
    positions = [source, target]
    slots = list(graph.homes)
    occupied = set(slots)
    history = []
    bit = 0

    def move(operand, path, phase):
        nonlocal bit
        for destination in path[1:]:
            if positions[operand] == destination:
                raise RuntimeError("zero-length hop")
            options = [graph.data(destination, i) for i in range(2)
                       if graph.data(destination, i) not in occupied]
            if not options:
                raise RuntimeError("no vacant destination storage")
            incoming, outgoing = slots[operand], min(options)
            first = len(circuit.data)
            teleport_hop(circuit, incoming, graph.comm(positions[operand]),
                         graph.comm(destination), outgoing, bit, bit + 1)
            history.append({"operand": operand, "phase": phase,
                            "source": positions[operand], "destination": destination,
                            "input": incoming, "output": outgoing,
                            "instruction_range": [first, len(circuit.data)],
                            "measurement_bits": [bit, bit + 1]})
            occupied.remove(incoming)
            occupied.add(outgoing)
            positions[operand], slots[operand] = destination, outgoing
            bit += 2

    for operand, path in enumerate(paths):
        move(operand, path, "out")
    circuit.cx(*slots)
    if restore:
        for operand, path in enumerate(paths):
            move(operand, list(reversed(path)), "return")
        if slots != graph.homes:
            raise RuntimeError("home data slot not restored")
    metadata = {"policy": policy, "meeting": meeting, "hops": hops,
                "bell_pairs": hops, "bsm": hops, "correction_bits": 2 * hops,
                "storage_cx": 3 * hops, "out_hops": sum(h["phase"] == "out" for h in history),
                "return_hops": sum(h["phase"] == "return" for h in history),
                "history": history, "final_slots": slots, "restored": restore}
    return circuit, metadata


def compile_teleport(graph, circuit):
    compiled = transpile(circuit, basis_gates=BASIS, coupling_map=CouplingMap(graph.edges),
                         initial_layout=list(range(graph.num_qubits)),
                         optimization_level=0, routing_method="none", seed_transpiler=201)
    assert_connectivity(compiled, graph)
    return compiled


def swap_control(graph, seed):
    """Restore every routing SWAP explicitly, including unused-wire placement."""
    circuit = QuantumCircuit(graph.num_qubits, name=f"{graph.name}_sabre_s{seed}")
    circuit.cx(*graph.homes)
    routed = transpile(circuit, basis_gates=["u", "cx", "swap"],
                       coupling_map=CouplingMap(graph.edges),
                       initial_layout=list(range(graph.num_qubits)),
                       optimization_level=0, routing_method="sabre", seed_transpiler=seed)
    swaps = [tuple(routed.find_bit(q).index for q in inst.qubits)
             for inst in routed.data if inst.operation.name == "swap"]
    restored = routed.copy()
    for a, b in reversed(swaps):
        restored.swap(a, b)
    compiled = transpile(restored, basis_gates=BASIS, coupling_map=CouplingMap(graph.edges),
                         initial_layout=list(range(graph.num_qubits)),
                         optimization_level=0, routing_method="none", seed_transpiler=seed)
    assert_connectivity(compiled, graph)
    final_layout = (routed.layout.final_layout.get_virtual_bits()
                    if routed.layout.final_layout is not None else {})
    return compiled, routed, {"policy": "sabre_swap", "seed": seed,
        "routing_swaps": len(swaps), "return_swaps": len(swaps),
        "swap_edges": swaps, "restored": True,
        "router_final_layout": {str(q): int(p) for q, p in final_layout.items()}}


def events(circuit):
    """Flatten only the supported single-bit positive correction control flow."""
    result = []
    for inst in circuit.data:
        op = inst.operation
        qubits = [circuit.find_bit(q).index for q in inst.qubits]
        clbits = [circuit.find_bit(c).index for c in inst.clbits]
        if op.name == "if_else":
            bit, value = op.condition
            if not isinstance(bit, Clbit) or len(op.blocks) != 1 or value != 1:
                raise ValueError("only positive single-bit if-without-else is supported")
            condition = circuit.find_bit(bit).index
            block = op.blocks[0]
            if block.num_clbits != len(clbits):
                raise ValueError("control-flow classical mapping mismatch")
            for child in block.data:
                if child.operation.name != "u":
                    raise ValueError("compile correction to a single u gate")
                result.append({"name": "u", "qubits": [qubits[block.find_bit(q).index]
                                                        for q in child.qubits],
                               "clbits": [], "condition": condition, "op": child.operation})
        elif op.name in {"u", "cx", "measure", "reset"}:
            result.append({"name": op.name, "qubits": qubits, "clbits": clbits,
                           "condition": None, "op": op})
        else:
            raise ValueError(f"unsupported compiled operation {op.name}")
    return result


def assert_connectivity(circuit, graph):
    legal = set(graph.edges)
    for event in events(circuit):
        if event["name"] == "cx" and tuple(event["qubits"]) not in legal:
            raise ValueError(f"nonlocal compiled CX {event['qubits']}")
    if circuit.num_qubits != graph.num_qubits:
        raise ValueError("compiler changed the physical qubit budget")


def schedule(circuit, *, core_serial=False, metric="quantum"):
    """ASAP reservation envelope with wire, feedback and optional core edges."""
    if metric not in {"quantum", "instrument", "cx"}:
        raise ValueError("unknown depth metric")
    qready = [0] * circuit.num_qubits
    cready = [0] * circuit.num_clbits
    cores = [0] * ((circuit.num_qubits + 2) // 3)
    rows = []
    for index, event in enumerate(events(circuit)):
        name, qubits, condition = event["name"], event["qubits"], event["condition"]
        resources = sorted({q // 3 for q in qubits})
        dependencies = [qready[q] for q in qubits]
        if condition is not None:
            dependencies.append(cready[condition])
        if core_serial:
            dependencies.extend(cores[c] for c in resources)
        start = max(dependencies, default=0)
        weight = int(metric == "instrument" or name == "cx" or
                     (metric == "quantum" and name == "u"))
        end = start + weight
        for q in qubits:
            qready[q] = end
        for bit in event["clbits"]:
            cready[bit] = end
        if core_serial:
            for core in resources:
                cores[core] = end
        rows.append({"event": index, "name": name, "qubits": qubits,
                     "classical_output": event["clbits"], "condition_bit": condition,
                     "start": start, "end": end, "weight": weight})
    return {"depth": max(qready + cready, default=0), "events": rows,
            "metric": metric, "concurrency": "one_primitive_per_core" if core_serial else "disjoint_qubit",
            "conditional_count_scope": "positive correction reservation upper envelope"}


def resources(circuit):
    rows = events(circuit)
    counts = Counter(event["name"] for event in rows)
    return {"physical_qubits": circuit.num_qubits,
            "used_qubits": len({q for e in rows for q in e["qubits"]}),
            "classical_bits": circuit.num_clbits,
            "u_count": counts["u"], "cx_count": counts["cx"],
            "measure_count": counts["measure"], "reset_count": counts["reset"],
            "conditional_u_slots": sum(e["condition"] is not None for e in rows),
            "total_primitive_slots": sum(counts.values())}


def _reorder(rho, active, order):
    if active == order:
        return rho
    n = len(active)
    axes = [n - 1 - active.index(q) for q in reversed(order)]
    data = rho.data.reshape((2,) * (2 * n)).transpose(axes + [n + a for a in axes])
    return DensityMatrix(data.reshape(2**n, 2**n))


def _extend(rho, active, required):
    active = list(active)
    for q in required:
        if q not in active:
            rho = DensityMatrix([1, 0]).tensor(rho)
            active.append(q)
    order = sorted(active)
    return _reorder(rho, active, order), order


def _compact(rho, active):
    """Discard only numerical zero-state spectators, never entangled payload."""
    active = list(active)
    trace = float(np.trace(rho.data).real)
    dropped_error = 0.0
    for index in reversed(range(len(active))):
        probability = float(rho.probabilities([index])[1])
        if probability <= 1e-14 * trace:
            dropped_error += max(0.0, probability)
            rho = partial_trace(rho, [index])
            active.pop(index)
    return rho, active, dropped_error


def _merge(branches):
    merged = {}
    for classical, rho, active in branches:
        key = tuple(sorted(classical.items()))
        if key not in merged:
            merged[key] = (classical, rho, active)
        else:
            _, previous, old_active = merged[key]
            union = sorted(set(active) | set(old_active))
            previous, _ = _extend(previous, old_active, union)
            rho, _ = _extend(rho, active, union)
            merged[key] = (classical, DensityMatrix(previous.data + rho.data), union)
    return list(merged.values())


def verify_channel(circuit, homes, *, tolerance=TOLERANCE):
    """Numerically exact Choi evaluation of the actual compiled instructions.

    Classical branches are summed only after the last use of a measured bit.
    Known-zero inactive wires are represented implicitly to bound memory.
    """
    if len(set(homes)) != 2 or any(q < 0 or q >= circuit.num_qubits for q in homes):
        raise ValueError("two distinct physical home qubits are required")
    references = [circuit.num_qubits, circuit.num_qubits + 1]
    active = sorted(homes + references)
    prepare = QuantumCircuit(4)
    for home, reference in zip(homes, references):
        prepare.h(active.index(reference))
        prepare.cx(active.index(reference), active.index(home))
    initial = DensityMatrix.from_instruction(prepare)
    useful = QuantumCircuit(4)
    useful.cx(active.index(homes[0]), active.index(homes[1]))
    ideal = initial.evolve(useful).data
    rows = events(circuit)
    last_use = {e["condition"]: i for i, e in enumerate(rows) if e["condition"] is not None}
    branches = [({}, initial, active)]
    max_width, max_branches, dropped = len(active), 1, 0.0
    for index, event in enumerate(rows):
        next_branches = []
        for classical, rho, active in branches:
            name, condition = event["name"], event["condition"]
            if condition is not None and condition not in classical:
                raise ValueError("condition reads an unmeasured bit")
            if condition is None or classical[condition] == 1:
                if name == "reset":
                    qubit = event["qubits"][0]
                    if qubit in active:
                        location = active.index(qubit)
                        rho = partial_trace(rho, [location])
                        active = [q for q in active if q != qubit]
                else:
                    rho, active = _extend(rho, active, event["qubits"])
                    max_width = max(max_width, len(active))
                    locations = [active.index(q) for q in event["qubits"]]
                    if name == "measure":
                        for bit in (0, 1):
                            projector = Operator(np.diag([int(bit == 0), int(bit == 1)]))
                            projected = rho.evolve(projector, qargs=locations)
                            if float(np.trace(projected.data).real) > 1e-16:
                                memory = dict(classical)
                                if event["clbits"][0] in last_use:
                                    memory[event["clbits"][0]] = bit
                                projected, compact, error = _compact(projected, active)
                                dropped += error
                                next_branches.append((memory, projected, compact))
                        continue
                    rho = rho.evolve(event["op"], qargs=locations)
            memory = dict(classical)
            if condition is not None and last_use[condition] == index:
                memory.pop(condition)
            rho, active, error = _compact(rho, active)
            dropped += error
            next_branches.append((memory, rho, active))
        max_branches = max(max_branches, len(next_branches))
        branches = _merge(next_branches)
    if len(branches) != 1 or branches[0][0]:
        raise RuntimeError("unresolved classical branches")
    _, rho, active = branches[0]
    output_order = sorted(homes + references)
    work = [q for q in active if q not in output_order]
    work_error = sum(float(rho.probabilities([active.index(q)])[1]) for q in work)
    if work:
        rho = partial_trace(rho, [active.index(q) for q in work])
        active = [q for q in active if q not in work]
    rho, active = _extend(rho, active, output_order)
    rho = _reorder(rho, active, output_order)
    error = float(np.max(np.abs(rho.data - ideal)))
    trace = float(np.trace(rho.data).real)
    fidelity = float(np.trace(rho.data @ ideal).real)
    return {"passed": bool(error < tolerance and abs(trace - 1) < tolerance
                           and work_error < tolerance and dropped < tolerance),
            "max_choi_error": error, "trace": trace, "process_fidelity": fidelity,
            "work_qubit_one_probability_sum": work_error,
            "discarded_zero_probability_bound": dropped,
            "max_active_qubits_including_references": max_width,
            "max_branches_before_merge": max_branches,
            "method": "deterministic projective-branch density matrix, normalized Choi input",
            "choi_real": rho.data.real.tolist(), "choi_imag": rho.data.imag.tolist()}


def hop_branch_check():
    """Independent exhaustive instrument calculation: four corrected K=I/2."""
    circuit = QuantumCircuit(4)
    circuit.h(1)
    circuit.cx(1, 2)
    circuit.cx(0, 1)
    circuit.h(0)
    unitary = Operator(circuit).data
    rows = []
    completeness = np.zeros((2, 2), complex)
    for z in (0, 1):
        for x in (0, 1):
            correction = QuantumCircuit(4)
            if x:
                correction.x(2)
            if z:
                correction.z(2)
            correction.swap(2, 3)
            fix = Operator(correction).data
            kraus = np.zeros((2, 2), complex)
            for incoming in (0, 1):
                state = unitary[:, incoming].copy()
                for address in range(16):
                    if address & 1 != z or (address >> 1) & 1 != x:
                        state[address] = 0
                state = fix @ state
                for outgoing in (0, 1):
                    kraus[outgoing, incoming] = state[z + 2*x + 8*outgoing]
            completeness += kraus.conj().T @ kraus
            rows.append({"z": z, "x": x, "max_kraus_error":
                         float(np.max(np.abs(kraus - np.eye(2)/2)))})
    error = float(np.max(np.abs(completeness - np.eye(2))))
    return {"passed": all(row["max_kraus_error"] < TOLERANCE for row in rows)
                       and error < TOLERANCE,
            "branches": rows, "completeness_error": error}
