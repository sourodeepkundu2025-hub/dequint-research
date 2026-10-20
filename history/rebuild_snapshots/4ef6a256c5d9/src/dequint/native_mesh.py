"""Native photonic mesh and complete CNOT-channel diagnostics.

Generation uses native BK photons/detectors and fixed-delay optical sidebands.
Payload correction/ACK uses the contended DEQUINT classical fabric. Admission,
finite data slots, post-herald dephasing and local operation times are explicit
addon models, not an unmodified native reservation stack or a calibrated device.
"""

from dataclasses import dataclass
import math
import time

import numpy as np
from sequence.components.circuit import Circuit
from sequence.components.memory import MemoryArray
from sequence.components.optical_channel import ClassicalChannel, QuantumChannel
from sequence.constants import DENSITY_MATRIX_FORMALISM
from sequence.entanglement_management.generation import EntanglementGenerationA
from sequence.entanglement_management.teleportation import TeleportMessage, TeleportMsgType, TeleportProtocol
from sequence.network_management.reservation import Reservation
from sequence.topology.node import BSMNode, Node

from .kernel import FifoResource, PS_PER_SECOND, Signal
from .native_reference import _formalism, _native_settings
from .network import Job, Network
from .quantum import dephasing_channel, identity_channel, pauli_depolarizing
from .routing import edge_key, mesh_edges, xy_path


PAULIS = (np.eye(2, dtype=complex), np.array([[0, 1], [1, 0]], complex),
          np.array([[0, -1j], [1j, 0]], complex), np.diag([1, -1]).astype(complex))
_CNOT = Circuit(2)
_CNOT.cx(0, 1)


def joint_density(manager, requested_keys):
    """Reduced density matrix in the requested native MSB-first key order."""
    keys, states, seen = [], [], set()
    for key in requested_keys:
        state = manager.get(key)
        if id(state) not in seen:
            seen.add(id(state))
            keys.extend(state.keys)
            states.append(np.asarray(state.state, dtype=complex))
    rho = np.array([[1]], complex)
    for state in states:
        rho = np.kron(rho, state)
    count = len(keys)
    tensor = rho.reshape((2,) * (2 * count))
    for index in reversed(range(count)):
        if keys[index] not in requested_keys:
            tensor = np.trace(tensor, axis1=index, axis2=len(keys) + index)
            keys.pop(index)
    order = [keys.index(key) for key in requested_keys]
    count = len(keys)
    tensor = tensor.transpose(order + [count + i for i in order])
    return tensor.reshape(2**count, 2**count)


def _apply_channel(manager, target_keys, probabilities):
    states, keys, seen = [], [], set()
    for key in target_keys:
        state = manager.get(key)
        if id(state) not in seen:
            seen.add(id(state))
            states.append(np.asarray(state.state, complex))
            keys.extend(state.keys)
    rho = np.array([[1]], complex)
    for state in states:
        rho = np.kron(rho, state)
    result = np.zeros_like(rho)
    for errors, probability in probabilities:
        if probability == 0:
            continue
        op = np.array([[1]], complex)
        errors_by_key = dict(zip(target_keys, errors))
        for key in keys:
            op = np.kron(op, PAULIS[errors_by_key.get(key, 0)])
        result += probability * (op @ rho @ op.conj().T)
    manager.set(keys, result)


def ideal_cnot_choi():
    state = np.zeros(16, complex)
    for a in range(2):
        for b in range(2):
            state[8*a + 4*b + 2*a + (a ^ b)] = .5
    return state


@dataclass
class NativeOperand:
    name: str
    position: tuple[int, int]
    memory: object
    slot: int
    lease: object
    data_core: tuple[int, int]


class _ResourceAdapter:
    def __init__(self, node):
        self.node = node
        self.callbacks = {}

    def update(self, protocol, memory, state):
        self.node.backend.emit("native", "native_resource_update", node=self.node.name,
                               memory=memory.name, state=state, protocol=type(protocol).__name__,
                               protocol_name=protocol.name)
        if state == "RAW":
            memory.reset()
        callback = self.callbacks.get(protocol.name)
        if callback:
            callback(self.node.name, state)


class _NativeCore(Node):
    def __init__(self, backend, coordinate, seed, data_slots):
        super().__init__(f"core.{coordinate[0]}.{coordinate[1]}", backend.kernel.timeline, seed=seed)
        self.backend, self.coordinate = backend, coordinate
        self.resource_manager = _ResourceAdapter(self)
        config = backend.config
        self.comm = MemoryArray(f"{self.name}.comm", self.timeline,
                                num_memories=config.communication_memories,
                                fidelity=config.raw_bell_fidelity, frequency=config.excitation_rate_hz,
                                efficiency=config.emission_efficiency, coherence_time=-1, cutoff_flag=False)
        self.data = MemoryArray(f"{self.name}.data", self.timeline, num_memories=data_slots,
                                fidelity=1, frequency=config.excitation_rate_hz,
                                efficiency=1, coherence_time=-1, cutoff_flag=False)
        self.add_component(self.comm)
        self.add_component(self.data)
        self.data_memo_arr_name = self.data.name
        self.free_comm = set(range(len(self.comm)))
        self.free_data = set(range(data_slots))
        self.data_resource = FifoResource(backend.kernel, f"data:{coordinate}", data_slots)
        self.teleports = {}
        self.acknowledgments = {}
        self.completed_callbacks = {}
        self.teleport_app = self

    def init(self):
        self.comm.add_receiver(self)

    def get(self, photon, **kwargs):
        self.send_qubit(kwargs["dst"], photon)

    def send_qubit(self, destination, photon):
        self.backend.photons += 1
        self.backend.emit("native", "native_photon", node=self.name, destination=destination,
                          is_null=bool(photon.is_null))
        return super().send_qubit(destination, photon)

    def send_message(self, destination, message, priority=math.inf, sender_delay=0):
        if isinstance(message, TeleportMessage):
            self.backend.kernel.spawn(self.backend._transport_payload(self, destination, message))
            return
        self.backend.control_messages += 1
        self.backend.emit("native", "native_control", source=self.name, destination=destination,
                          message_type=message.msg_type.name, receiver=message.receiver)
        return super().send_message(destination, message, priority, sender_delay)

    def receive_message(self, source, message):
        if isinstance(message, TeleportMessage):
            if message.msg_type is TeleportMsgType.ACK:
                signal = self.acknowledgments.get(message.reservation.identity)
                if signal:
                    signal.succeed(True)
            else:
                protocol = self.teleports.get(message.bob_comm_memory_name)
                if protocol is not None:
                    self.backend._age_key(protocol.bob_comm_memory.qstate_key)
                    protocol.received_message(source, message)
                    protocol.bob_acknowledge_complete(message.reservation)
            return
        return super().receive_message(source, message)

    def teleport_complete(self, key):
        signal = self.completed_callbacks.get(key)
        if signal:
            signal.succeed(True)


class _NativeBSM(BSMNode):
    def __init__(self, backend, edge, endpoints, seed):
        self.backend, self.edge, self.active_attempt = backend, edge, None
        config = backend.config
        super().__init__(f"bsm.{endpoints[0].name}.{endpoints[1].name}", backend.kernel.timeline,
                         [node.name for node in endpoints], seed=seed,
                         component_templates={"SingleAtomBSM": {"detectors": [
                             {"efficiency": config.detector_efficiency, "dark_count": 0,
                              "count_rate": 1e11, "time_resolution": 1} for _ in range(2)]}})

    def send_message(self, destination, message, priority=math.inf, sender_delay=0):
        if message.msg_type.name == "MEAS_RES":
            self.backend.detector_notifications += 1
            if self.active_attempt is not None:
                self.active_attempt.setdefault("first_herald_s", self.backend.kernel.now)
            self.backend.emit("native", "native_herald", node=self.name, destination=destination,
                              detector=int(message.detector),
                              generation_id=self.active_attempt.get("identity") if self.active_attempt else None)
        return super().send_message(destination, message, priority, sender_delay)


class _NativeMesh(Network):
    def __init__(self, config, requests, seed, run_id, trace, data_slots, control_delay_ps):
        if config.purification_rounds or config.pooled_servers or config.link_servers != 1:
            raise ValueError("Native mesh currently requires one BSM/link, no pool or purification")
        if config.source_outage_probability:
            raise ValueError("Use zero detector efficiency for the native optical outage check")
        if data_slots < 2 or control_delay_ps < 1:
            raise ValueError("At least two data slots and positive native sideband delay are required")
        super().__init__(config, requests, seed, run_id, trace)
        self.live_last = {}
        self.native_jobs = {}
        self.photons = self.control_messages = self.detector_notifications = 0
        self.sequence_id = 0
        self.control_delay_ps = control_delay_ps
        self.drain_s = config.link_length_m / 2e8 + (4 * control_delay_ps + 100) / PS_PER_SECOND
        self.kernel.timeline.stop_time += round((2*self.drain_s + 1e-6) * PS_PER_SECOND)
        self.native_nodes = {coordinate: _NativeCore(self, coordinate, seed*1000 + index, data_slots)
                             for index, coordinate in enumerate(sorted(self.cores))}
        self.native_by_name = {node.name: node for node in self.native_nodes.values()}
        self.bsms = {}
        for index, edge in enumerate(mesh_edges(config.mesh_side)):
            endpoints = [self.native_nodes[n] for n in edge]
            middle = _NativeBSM(self, edge, endpoints, seed*1000 + 500 + index)
            self.bsms[edge] = middle
            trio = endpoints + [middle]
            for source in trio:
                for destination in trio:
                    if source is not destination:
                        channel = ClassicalChannel(f"sideband.{source.name}.{destination.name}",
                                                   self.kernel.timeline, 0, delay=control_delay_ps)
                        channel.set_ends(source, destination.name)
            for node in endpoints:
                channel = QuantumChannel(f"optical.{node.name}.{middle.name}", self.kernel.timeline,
                                         config.attenuation_db_per_m, config.link_length_m / 2,
                                         frequency=config.excitation_rate_hz)
                channel.set_ends(node, middle.name)

    @property
    def manager(self):
        return self.kernel.timeline.quantum_manager

    def _age_key(self, key):
        previous = self.live_last.get(key)
        if previous is None:
            return
        elapsed = max(0, self.kernel.now - previous)
        if elapsed and math.isfinite(self.config.memory_t2_s):
            channel = dephasing_channel(elapsed, self.config.memory_t2_s)
            _apply_channel(self.manager, [key], [((i,), p) for i, p in enumerate(channel)])
        self.live_last[key] = self.kernel.now

    def _noise(self, keys, error):
        if not error:
            return
        if len(keys) == 1:
            channel = pauli_depolarizing(error)
            items = [((i,), p) for i, p in enumerate(channel)]
        else:
            items = [((i, j), 1-error if i == j == 0 else error/15)
                     for i in range(4) for j in range(4)]
        _apply_channel(self.manager, keys, items)

    def _data_slot(self, coordinate, job):
        node = self.native_nodes[coordinate]
        lease = yield from self._acquire(node.data_resource, job)
        if lease is None:
            return None
        slot = min(node.free_data)
        node.free_data.remove(slot)
        return node, slot, lease

    def _free_data(self, coordinate, slot, lease):
        node = self.native_nodes[coordinate]
        node.data[slot].reset()
        node.free_data.add(slot)
        if not lease.released:
            lease.release()

    def _transport_payload(self, source, destination, message):
        reservation = message.reservation
        target = self.native_by_name[destination]
        bits = 2 + self.config.correction_header_bits if message.msg_type is TeleportMsgType.MEASUREMENT_RESULT else self.config.control_bits
        tag = f"native:{reservation.identity}:{message.msg_type.name}"
        accepted = yield from self.fabric.send(source.coordinate, target.coordinate, bits,
                                               reservation.end_time / PS_PER_SECOND,
                                               str(reservation.identity), tag)
        self.emit(reservation.identity, "native_payload_message", source=source.name,
                  destination=destination, message_type=message.msg_type.name, accepted=accepted,
                  reservation_id=reservation.identity,
                  x_flip=getattr(message, "x_flip", None), z_flip=getattr(message, "z_flip", None))
        if accepted:
            target.receive_message(source.name, message)

    def _native_pair(self, edge, memories, job):
        middle = self.bsms[edge]
        for attempt in range(self.config.max_attempts):
            if not (yield from self._pause(self.config.reset_s, job)):
                return None
            job.counters["epr_attempts"] += 1
            self.sequence_id += 1
            record = {"identity": self.sequence_id}
            middle.active_attempt = record
            done, states = Signal(self.kernel), {}

            def update(node, state):
                states[node] = state
                if len(states) == 2:
                    done.succeed(all(value == "ENTANGLED" for value in states.values()))

            protocols = []
            for index, coordinate in enumerate(edge):
                node, other = self.native_nodes[coordinate], self.native_nodes[edge[1-index]]
                protocol = EntanglementGenerationA.create(node, f"eg.{record['identity']}.{node.name}",
                                                          middle.name, other.name, memories[index])
                protocols.append(protocol)
                node.protocols.append(protocol)
                node.resource_manager.callbacks[protocol.name] = update
            for index, protocol in enumerate(protocols):
                protocol.set_others(protocols[1-index].name, self.native_nodes[edge[1-index]].name,
                                    [memories[1-index].name])
                self.kernel.call_at(self.kernel.now, protocol.start)
            self.emit(job.owner, "native_generation_started", generation_id=record["identity"],
                      protocol_names=[p.name for p in protocols], edge=edge, attempt=attempt)
            self.kernel.call_at(job.request.deadline_s, done.succeed, False)
            accepted = yield done
            self.emit(job.owner, "native_generation_terminal", generation_id=record["identity"],
                      accepted=bool(accepted), edge=edge)
            for protocol in protocols:
                protocol.owner.protocols.remove(protocol)
                protocol.owner.resource_manager.callbacks.pop(protocol.name, None)
                for event in protocol.scheduled_events:
                    self.kernel.timeline.remove_event(event)
            middle.active_attempt = None
            if accepted:
                job.counters["raw_pairs"] += 1
                expires = record.get("first_herald_s", self.kernel.now) + self.config.memory_cutoff_s
                if self.kernel.now > expires:
                    job.reason = "pair_expired_during_native_generation"
                    return None
                for memory in memories:
                    self.live_last[memory.qstate_key] = self.kernel.now
                rho = joint_density(self.manager, [m.qstate_key for m in memories])
                phi = np.array([1, 0, 0, 1], complex) / np.sqrt(2)
                fidelity = float(np.vdot(phi, rho @ phi).real)
                pair = self.pairs.allocate(identity_channel(), self.kernel.now, job.owner, expires)
                self.emit(job.owner, "native_pair_ready", pair_id=pair.pair_id,
                          state_fidelity=fidelity, first_herald_s=record.get("first_herald_s"),
                          generation_id=record["identity"])
                return pair
            # Drain already emitted photons before resetting/reassigning their keys.
            yield self.kernel.delay(self.drain_s)
            for memory in memories:
                memory.reset()
            if self.kernel.now >= job.request.deadline_s:
                job.reason = "native_generation_deadline"
                return None
        job.reason = "native_attempt_bound"
        return None

    def _hop(self, operand, destination, job, phase):
        source, edge = operand.position, edge_key(operand.position, destination)
        leases, allocated_comm, pair = [], [], None
        slot = yield from self._data_slot(destination, job)
        if slot is None:
            return False
        destination_node, destination_slot, destination_lease = slot
        destination_memory = destination_node.data[destination_slot]
        receiver_key, reservation_id = None, None
        try:
            for coordinate in edge:
                lease = yield from self._acquire(self.cores[coordinate].memories, job)
                if lease is None:
                    return False
                leases.append(lease)
                node = self.native_nodes[coordinate]
                index = min(node.free_comm)
                node.free_comm.remove(index)
                allocated_comm.append((node, index))
            lease = yield from self._acquire(self.generators[edge], job)
            if lease is None:
                return False
            leases.append(lease)
            memories = [node.comm[index] for node, index in allocated_comm]
            pair = yield from self._native_pair(edge, memories, job)
            if pair is None:
                return False
            lease.release()
            source_gate = yield from self._acquire(self.cores[source].gate, job)
            if source_gate is None:
                return False
            leases.append(source_gate)
            if not (yield from self._pause_pair(self.config.teleport_s, job, [pair])):
                return False
            for memory in memories:
                self._age_key(memory.qstate_key)
            self._age_key(operand.memory.qstate_key)
            alice_node = self.native_nodes[source]
            alice_memory = memories[edge.index(source)]
            bob_memory = memories[edge.index(destination)]
            self._noise([bob_memory.qstate_key], self.config.teleport_pauli_error)
            self.sequence_id += 1
            reservation_id = self.sequence_id
            reservation = Reservation(alice_node.name, destination_node.name,
                                      self.kernel.timeline.now(), round(job.request.deadline_s*PS_PER_SECOND),
                                      1, 0, identity=reservation_id)
            sender = TeleportProtocol(alice_node, alice=True, data_memory_index=operand.slot,
                                      remote_node_name=destination_node.name)
            sender.set_alice_comm_memory(alice_memory)
            sender.set_bob_comm_memory_name(bob_memory.name)
            receiver = TeleportProtocol(destination_node, alice=False, remote_node_name=alice_node.name)
            receiver.set_bob_comm_memory(bob_memory)
            receiver.set_bob_comm_memory_name(bob_memory.name)
            received, acknowledged = Signal(self.kernel), Signal(self.kernel)
            receiver_key = bob_memory.qstate_key
            destination_node.teleports[bob_memory.name] = receiver
            destination_node.completed_callbacks[receiver_key] = received
            alice_node.acknowledgments[reservation_id] = acknowledged
            self.kernel.call_at(job.request.deadline_s, received.succeed, False)
            self.kernel.call_at(job.request.deadline_s, acknowledged.succeed, False)
            sender.alice_bell_measurement(reservation)
            old_memory = operand.memory
            self.live_last.pop(old_memory.qstate_key, None)
            old_memory.reset()
            self.live_last.pop(alice_memory.qstate_key, None)
            alice_memory.reset()
            operand.memory, operand.position = bob_memory, destination
            self.live_last[receiver_key] = self.kernel.now
            source_gate.release()
            self._consume(pair, job, "native_payload_measurement")
            job.counters["consumed_pairs"] += 1
            job.counters["quantum_hops"] += 1
            self.emit(job.owner, "native_payload_measured", phase=phase, source=source, destination=destination,
                      reservation_id=reservation_id, pair_id=pair.pair_id)
            confirmations = yield self.kernel.all([received, acknowledged])
            if not all(value is True for value in confirmations):
                job.reason = "native_correction_unconfirmed"
                return False
            storage_gate = yield from self._acquire(self.cores[destination].gate, job)
            if storage_gate is None:
                return False
            leases.append(storage_gate)
            self._age_key(receiver_key)
            self.live_last[destination_memory.qstate_key] = self.kernel.now
            # Transfer into a finite physical data slot, never copy state amplitudes.
            for control, target in ((receiver_key, destination_memory.qstate_key),
                                    (destination_memory.qstate_key, receiver_key),
                                    (receiver_key, destination_memory.qstate_key)):
                job.counters["storage_swap_cnot_started"] = job.counters.get("storage_swap_cnot_started", 0) + 1
                self.emit(job.owner, "native_storage_cnot_started", core=destination,
                          gate_resource_used=self.cores[destination].gate.used)
                self.manager.run_circuit(_CNOT, [control, target])
                self._noise([control, target], self.config.gate_pauli_error)
                if not (yield from self._pause(self.config.gate_s, job)):
                    return False
                job.counters["storage_swap_cnot"] = job.counters.get("storage_swap_cnot", 0) + 1
                self.emit(job.owner, "native_storage_cnot_completed", core=destination)
                self._age_key(control)
                self._age_key(target)
            storage_gate.release()
            self.live_last.pop(receiver_key, None)
            self._free_data(operand.data_core, operand.slot, operand.lease)
            operand.memory, operand.slot = destination_memory, destination_slot
            operand.lease, operand.data_core = destination_lease, destination
            return True
        finally:
            if receiver_key is not None:
                destination_node.completed_callbacks.pop(receiver_key, None)
                for name in list(destination_node.teleports):
                    if destination_node.teleports[name].bob_comm_memory.qstate_key == receiver_key:
                        destination_node.teleports.pop(name)
            if reservation_id is not None:
                self.native_nodes[source].acknowledgments.pop(reservation_id, None)
            if pair is not None and pair.pair_id in self.pairs.ready:
                self._consume(pair, job, "native_aborted_unused_pair")
            for node, index in allocated_comm:
                self.live_last.pop(node.comm[index].qstate_key, None)
                node.comm[index].reset()
                node.free_comm.add(index)
            for lease in reversed(leases):
                if not lease.released:
                    lease.release()
            if operand.lease is not destination_lease:
                self.live_last.pop(destination_memory.qstate_key, None)
                self._free_data(destination, destination_slot, destination_lease)

    def _execute(self, request):
        yield self.kernel.delay(max(0, request.arrival_s-self.kernel.now))
        job = Job(request, [])
        references = []
        for name, coordinate in (("a", request.source), ("b", request.destination)):
            result = yield from self._data_slot(coordinate, job)
            if result is None:
                break
            node, index, lease = result
            operand = NativeOperand(name, coordinate, node.data[index], index, lease, coordinate)
            job.operands.append(operand)
            reference = self.manager.new()
            references.append(reference)
            prepare = Circuit(2)
            prepare.h(0)
            prepare.cx(0, 1)
            self.manager.run_circuit(prepare, [reference, operand.memory.qstate_key])
            self.live_last[operand.memory.qstate_key] = self.kernel.now
        controller_start = time.perf_counter()
        meeting, predicted_s, predicted_f = self._meeting(job) if len(job.operands) == 2 else (None, None, None)
        controller_wall = time.perf_counter()-controller_start
        paths = [xy_path(op.position, meeting) for op in job.operands] if meeting is not None else []
        success = False
        rho, fidelity = None, None
        try:
            if len(job.operands) == 2:
                moved = yield self.kernel.all([self.kernel.spawn(self._move(op, path, job, "out"))
                                               for op, path in zip(job.operands, paths)])
                success = all(value is True for value in moved)
            if success:
                lease = yield from self._acquire(self.cores[meeting].gate, job)
                success = lease is not None
                if lease:
                    try:
                        keys = [op.memory.qstate_key for op in job.operands]
                        for key in keys:
                            self._age_key(key)
                        job.counters["useful_cnot_started"] = 1
                        self.emit(job.owner, "native_useful_cnot_started", core=meeting)
                        self.manager.run_circuit(_CNOT, keys)
                        self._noise(keys, self.config.gate_pauli_error)
                        success = yield from self._pause(self.config.gate_s, job)
                        job.counters["useful_cnot_completed"] = int(success)
                        self.emit(job.owner, "native_useful_cnot_finished", core=meeting, completed=bool(success))
                    finally:
                        lease.release()
            if success and self.config.placement == "restored":
                restored = yield self.kernel.all([self.kernel.spawn(self._move(op, list(reversed(path)), job, "return"))
                                                  for op, path in zip(job.operands, paths)])
                success = all(value is True for value in restored)
            if success:
                for operand in job.operands:
                    self._age_key(operand.memory.qstate_key)
                rho = joint_density(self.manager, references + [op.memory.qstate_key for op in job.operands])
                if not np.isclose(np.trace(rho), 1, atol=1e-9) or not np.allclose(rho, rho.conj().T, atol=1e-9):
                    raise RuntimeError("Native output is not a normalized Hermitian density matrix")
                target = ideal_cnot_choi()
                fidelity = float(np.vdot(target, rho @ target).real)
                if not -1e-9 <= fidelity <= 1+1e-9:
                    raise RuntimeError("Invalid native Choi fidelity")
                fidelity = float(np.clip(fidelity, 0, 1))
                if self.config.placement == "restored" and [op.position for op in job.operands] != [request.source, request.destination]:
                    raise RuntimeError("Native restored placement violated")
            self.rows.append({"run_id": self.run_id, "seed": self.seed, "request_id": request.request_id,
                              "policy": self.config.policy, "placement": self.config.placement,
                              "classical": self.config.classical, "source": request.source, "destination": request.destination,
                              "meeting": meeting, "arrival_s": request.arrival_s, "deadline_s": request.deadline_s,
                              "finished_s": self.kernel.now, "latency_s": self.kernel.now-request.arrival_s,
                              "completed": bool(success), "quality_qualified": bool(success and fidelity >= self.config.minimum_process_fidelity),
                              "process_fidelity": fidelity, "average_gate_fidelity": (4*fidelity+1)/5 if success else None,
                              "terminal_reason": "completed" if success else job.reason,
                              "controller_wall_s": controller_wall, "predicted_latency_s": predicted_s,
                              "predicted_process_fidelity": predicted_f,
                              "final_positions": [op.position for op in job.operands],
                              "choi_density_real": rho.real.tolist() if rho is not None else None,
                              "choi_density_imag": rho.imag.tolist() if rho is not None else None, **job.counters})
        finally:
            for operand in job.operands:
                self.live_last.pop(operand.memory.qstate_key, None)
                operand.memory.reset()
                self._free_data(operand.data_core, operand.slot, operand.lease)
            for reference in references:
                self.manager.discard(reference)
                self.manager.remove(reference)

    def run(self):
        result = super().run()
        for node in self.native_nodes.values():
            if node.protocols or node.resource_manager.callbacks or node.teleports or node.acknowledgments:
                raise RuntimeError("Native protocol lifecycle leak")
            if node.data_resource.used or node.data_resource.waiting_units or len(node.free_data) != len(node.data):
                raise RuntimeError("Native data slot leak")
            if len(node.free_comm) != len(node.comm):
                raise RuntimeError("Native communication slot leak")
        if self.live_last:
            raise RuntimeError("Native live-state timing records leaked")
        result["summary"].update(backend="SeQUeNCe 1.3.0 native photonic mesh and density-matrix Choi channel",
                                  native_photon_emissions=self.photons, native_control_messages=self.control_messages,
                                  photon_counter_scope="native send_qubit calls, including null BK photon objects",
                                  native_detector_notifications=self.detector_notifications,
                                  native_quantum_cores=len(self.native_nodes), native_bsm_nodes=len(self.bsms),
                                  full_native_reservation_stack=False, hardware=False,
                                  generation_control="dedicated fixed-delay native sidebands",
                                  payload_control="contended classical FIFO/radio fabric",
                                  pair_dephasing="post-herald only; no microscopic in-generation dephasing",
                                  storage_swap_cnot_started=sum(row.get("storage_swap_cnot_started", 0) for row in self.rows),
                                  storage_swap_cnot_completed=sum(row.get("storage_swap_cnot", 0) for row in self.rows),
                                  native_data_cnot_started=sum(row["quantum_hops"] + row.get("storage_swap_cnot_started", 0)
                                                               + row.get("useful_cnot_started", 0) for row in self.rows),
                                  native_data_cnot_completed=sum(row["quantum_hops"] + row.get("storage_swap_cnot", 0)
                                                                 + row.get("useful_cnot_completed", 0) for row in self.rows),
                                  data_slots_per_core=len(next(iter(self.native_nodes.values())).data))
        return result


def run_native_mesh(config, requests, seed, run_id="native", trace=True,
                    data_slots_per_core=8, control_delay_ps=2000):
    """Run serially in its own process if another native model uses global selectors."""
    with _native_settings():
        _formalism(DENSITY_MATRIX_FORMALISM)
        return _NativeMesh(config, requests, seed, run_id, trace,
                           data_slots_per_core, control_delay_ps).run()
