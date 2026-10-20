"""Failure-aware multicore gate execution on SeQUeNCe's native event kernel.

The link protocol reserves complete two-round attempt slots. Optical heralding
uses an explicitly declared Bernoulli abstraction; state quality is an exact
Pauli-channel calculation within the declared model, not a hardware estimate.
"""

import math
import time
from dataclasses import dataclass, field

import numpy as np

from .config import ModelConfig
from .kernel import FifoResource, Kernel
from .quantum import (age_channel, bbpssw, compose_pauli, gate_average_fidelity,
                      gate_process_fidelity, identity_channel, pauli_depolarizing, werner_channel)
from .routing import (edge_key, geodesic_meetings, manhattan, mesh_edges,
                      minimax_meeting, nodes, paper_meeting, xy_path)
from .transport import ClassicalFabric
from .workload import RandomStreams, Request, workload_hash


@dataclass
class Operand:
    name: str
    position: tuple[int, int]
    channel: np.ndarray
    last_update_s: float

    def age(self, now, t2):
        elapsed = max(0, now - self.last_update_s)
        self.channel = age_channel(self.channel, elapsed, t2)
        self.last_update_s = now


@dataclass
class Pair:
    pair_id: int
    channel: np.ndarray
    created_s: float
    expires_s: float = math.inf


@dataclass
class Job:
    request: Request
    operands: list[Operand]
    counters: dict = field(default_factory=lambda: {"epr_attempts": 0, "raw_pairs": 0,
        "purification_attempts": 0, "purification_accepts": 0, "consumed_pairs": 0,
        "quantum_hops": 0, "quantum_queue_wait_s": 0.0})
    reason: str = ""

    @property
    def owner(self):
        return str(self.request.request_id)


class EPRGenTable:
    """Single-use resource records; association does not certify entanglement."""

    def __init__(self):
        self.next_id = 0
        self.ready = {}
        self.consumed = set()

    def allocate(self, channel, now, owner, expires_s=math.inf):
        pair = Pair(self.next_id, channel, now, expires_s)
        self.next_id += 1
        self.ready[pair.pair_id] = owner
        return pair

    def consume(self, pair, owner):
        if self.ready.pop(pair.pair_id, None) != owner or pair.pair_id in self.consumed:
            raise RuntimeError("Bell pair reused or associated with a different request")
        self.consumed.add(pair.pair_id)


class QuantumCore:
    def __init__(self, kernel, coordinate, communication_memories):
        self.coordinate = coordinate
        self.memories = FifoResource(kernel, f"memory:{coordinate}", communication_memories)
        self.gate = FifoResource(kernel, f"gate:{coordinate}", 1)


class Network:
    def __init__(self, config: ModelConfig, requests: list[Request], seed, run_id="run", trace=False):
        self.config = config.validate()
        if not requests:
            raise ValueError("Empty experiment workload")
        valid = set(nodes(config.mesh_side))
        if any(r.source not in valid or r.destination not in valid or r.deadline_s <= r.arrival_s for r in requests):
            raise ValueError("Workload violates the topology or deadline contract")
        if len({r.request_id for r in requests}) != len(requests):
            raise ValueError("Duplicate request identifier")
        self.requests = requests
        self.seed, self.run_id = seed, run_id
        self.horizon_s = max(r.deadline_s for r in requests) + 1e-6
        self.kernel = Kernel(self.horizon_s, config.max_events)
        self.streams = RandomStreams(seed)
        self.cores = {n: QuantumCore(self.kernel, n, config.communication_memories) for n in valid}
        self.generators = {edge: FifoResource(self.kernel, f"bsm:{edge}", config.link_servers)
                           for edge in mesh_edges(config.mesh_side)}
        self.pool = FifoResource(self.kernel, "pooled_bsm", config.pooled_servers) if config.pooled_servers else None
        self.pairs = EPRGenTable()
        self.trace_enabled = trace
        self.events, self.rows = [], []
        self.fabric = ClassicalFabric(self.kernel, config, self.streams, self.emit)
        self.teleport_noise = pauli_depolarizing(config.teleport_pauli_error)

    def emit(self, owner, action, **fields):
        if self.trace_enabled:
            self.events.append({"run_id": self.run_id, "seed": self.seed, "request_id": owner,
                                "time_s": self.kernel.now, "action": action, **fields})

    def _pause(self, duration, job):
        remaining = job.request.deadline_s - self.kernel.now
        if remaining <= 0:
            job.reason = "deadline"
            return False
        yield self.kernel.delay(min(duration, remaining))
        if duration > remaining + 1e-12:
            job.reason = "deadline"
            return False
        return True

    def _acquire(self, resource, job, amount=1):
        before = self.kernel.now
        lease = yield resource.request(job.owner, job.request.deadline_s, amount)
        waited = self.kernel.now - before
        job.counters["quantum_queue_wait_s"] += waited
        self.emit(job.owner, "resource_admission", resource=resource.name, amount=amount,
                  wait_s=waited, admitted=lease is not None)
        if lease is None:
            job.reason = "resource_deadline"
        return lease

    def _send(self, source, destination, bits, job, tag):
        result = yield from self.fabric.send(source, destination, bits, job.request.deadline_s, job.owner, tag)
        if not result:
            job.reason = f"classical_unconfirmed:{tag}"
        return result

    def _new_pair(self, channel, job, expires_s):
        pair = self.pairs.allocate(channel, self.kernel.now, job.owner, expires_s)
        self.emit(job.owner, "pair_ready", pair_id=pair.pair_id, bell_fidelity=float(channel[0]))
        return pair

    def _pause_pair(self, duration, job, pairs):
        remaining = min(pair.expires_s for pair in pairs) - self.kernel.now
        if remaining < 0:
            job.reason = "pair_expired"
            return False
        if not (yield from self._pause(min(duration, remaining), job)):
            return False
        if duration > remaining + 1e-12:
            job.reason = "pair_expired"
            return False
        return True

    def _consume(self, pair, job, reason):
        self.pairs.consume(pair, job.owner)
        self.emit(job.owner, "pair_consumed", pair_id=pair.pair_id, reason=reason)

    def _raw_pair(self, edge, job, phase):
        gateway, other = edge
        for attempt in range(self.config.max_attempts):
            job.counters["epr_attempts"] += 1
            intermediate_at = None
            for round_index in range(2):
                interval = 1 / self.config.excitation_rate_hz + self.config.reset_s / 2
                interval += self.config.link_length_m / (2 * 2e8)
                if not (yield from self._pause(interval, job)):
                    return None
                signals = [self.kernel.spawn(self._send(gateway, endpoint, self.config.herald_bits, job,
                                                       f"herald:{phase}:{round_index}"))
                           for endpoint in edge]
                acknowledged = yield self.kernel.all(signals)
                if not all(acknowledged):
                    return None
                if round_index == 0:
                    intermediate_at = self.kernel.now
            accepted = self.streams.random(job.owner, "epr", edge, phase) < self.config.generation_success
            self.emit(job.owner, "complete_epr_attempt", edge=edge, phase=phase, attempt=attempt, accepted=accepted)
            if accepted:
                job.counters["raw_pairs"] += 1
                expires_s = intermediate_at + self.config.memory_cutoff_s
                if self.kernel.now > expires_s:
                    job.reason = "pair_expired_during_generation"
                    self.emit(job.owner, "pair_expired_during_generation", edge=edge)
                    return None
                # The accepted-pair abstraction includes coherence during the second round.
                channel = age_channel(werner_channel(self.config.raw_bell_fidelity),
                                      2 * (self.kernel.now - intermediate_at), self.config.memory_t2_s)
                return self._new_pair(channel, job, expires_s)
            if self.kernel.now >= job.request.deadline_s:
                return None
        job.reason = "epr_attempt_bound"
        return None

    def _prepare_level(self, level, edge, job, phase):
        if level == 0:
            return (yield from self._raw_pair(edge, job, phase))
        for _ in range(self.config.max_attempts):
            first = yield from self._prepare_level(level - 1, edge, job, phase)
            if first is None:
                return None
            second = yield from self._prepare_level(level - 1, edge, job, phase)
            if second is None:
                self._consume(first, job, "aborted_purification")
                return None
            if not (yield from self._pause_pair(self.config.purification_local_s, job, [first, second])):
                self._consume(first, job, "aborted_purification")
                self._consume(second, job, "aborted_purification")
                return None
            a = age_channel(first.channel, 2 * (self.kernel.now - first.created_s), self.config.memory_t2_s)
            b = age_channel(second.channel, 2 * (self.kernel.now - second.created_s), self.config.memory_t2_s)
            # Ideal bilateral input twirls preserve Phi+ weight and restore Werner form.
            self.emit(job.owner, "ideal_werner_input_twirl", first_id=first.pair_id,
                      second_id=second.pair_id, first_fidelity=float(a[0]), second_fidelity=float(b[0]))
            fidelity, probability = bbpssw(float(a[0]), float(b[0]))
            self._consume(first, job, "purification_input")
            self._consume(second, job, "purification_input")
            measured_at = self.kernel.now
            job.counters["purification_attempts"] += 1
            if not (yield from self._send(edge[0], edge[1], 2 + self.config.correction_header_bits, job,
                                         f"purification:{phase}")):
                return None
            accepted = self.streams.random(job.owner, "purification", edge, phase, level) < probability
            self.emit(job.owner, "purification", level=level, accepted=accepted, probability=probability,
                      output_fidelity=fidelity)
            if accepted:
                job.counters["purification_accepts"] += 1
                expires_s = min(first.expires_s, second.expires_s)
                if self.kernel.now > expires_s:
                    job.reason = "pair_expired_during_purification"
                    return None
                # An ideal isotropic twirl is part of the stated Werner-input model.
                channel = age_channel(werner_channel(fidelity), 2 * (self.kernel.now - measured_at),
                                      self.config.memory_t2_s)
                return self._new_pair(channel, job, expires_s)
        job.reason = "purification_attempt_bound"
        return None

    def _hop(self, operand, destination, job, phase):
        source = operand.position
        edge = edge_key(source, destination)
        rounds = self.config.purification_rounds if self.config.raw_bell_fidelity < self.config.purification_threshold else 0
        leases, pair = [], None
        try:
            # All requests lock communication memories in global node order.
            for endpoint in edge:
                lease = yield from self._acquire(self.cores[endpoint].memories, job, 2**rounds)
                if lease is None:
                    return False
                leases.append(lease)
            generator = self.pool if self.pool is not None else self.generators[edge]
            lease = yield from self._acquire(generator, job)
            if lease is None:
                return False
            leases.append(lease)
            if not (yield from self._send(source, edge[0], self.config.control_bits, job, f"control:{phase}")):
                return False
            pair = yield from self._prepare_level(rounds, edge, job, phase)
            if pair is None:
                return False
            lease.release()
            if self.kernel.now > pair.expires_s:
                job.reason = "pair_expired"
                return False
            if not (yield from self._pause_pair(self.config.teleport_s, job, [pair])):
                return False
            operand.age(self.kernel.now, self.config.memory_t2_s)
            pair_channel = age_channel(pair.channel, 2 * (self.kernel.now - pair.created_s), self.config.memory_t2_s)
            operand.channel = compose_pauli(compose_pauli(operand.channel, pair_channel), self.teleport_noise)
            self._consume(pair, job, "payload_bell_measurement")
            job.counters["consumed_pairs"] += 1
            job.counters["quantum_hops"] += 1
            operand.position = destination
            bits = int(self.streams.random(job.owner, "measurement", edge, phase) * 4)
            self.emit(job.owner, "payload_measured", pair_id=pair.pair_id, source=source,
                      destination=destination, measurement_bits=bits, operand=operand.name)
            if not (yield from self._send(source, destination, 2 + self.config.correction_header_bits, job,
                                         f"correction:{phase}:{bits}")):
                # The measured unknown input is never retried from its source.
                return False
            operand.age(self.kernel.now, self.config.memory_t2_s)
            self.emit(job.owner, "pauli_frame_confirmed", operand=operand.name, pair_id=pair.pair_id)
            return True
        finally:
            if pair is not None and pair.pair_id in self.pairs.ready:
                self._consume(pair, job, "aborted_unused_pair")
            for lease in reversed(leases):
                if not lease.released:
                    lease.release()

    def _move(self, operand, path, job, phase):
        if operand.position != path[0]:
            raise RuntimeError("Path starts at a different quantum-state location")
        for destination in path[1:]:
            if not (yield from self._hop(operand, destination, job, f"{operand.name}:{phase}")):
                return False
        return True

    def _expected_path(self, path):
        base = self.config.expected_pair_s
        if not math.isfinite(base):
            return float("inf")
        total = 0.0
        for a, b in zip(path, path[1:]):
            generator = self.pool if self.pool is not None else self.generators[edge_key(a, b)]
            queue = (generator.used + generator.waiting_units) / generator.capacity
            memory_queue = max(max(0, (self.cores[n].memories.used + self.cores[n].memories.waiting_units + 1 -
                                      self.cores[n].memories.capacity) / self.cores[n].memories.capacity) for n in (a, b))
            total += base * (1 + queue + memory_queue) + self.config.teleport_s
            total += self.fabric.estimated_wait(a, b, self.config.control_bits)
        return total

    def _estimate(self, job, meeting):
        paths = [xy_path(operand.position, meeting) for operand in job.operands]
        travel = max(self._expected_path(path) for path in paths)
        gate_queue = self.cores[meeting].gate.used + self.cores[meeting].gate.waiting_units
        before_gate = travel + gate_queue * self.config.gate_s
        elapsed = before_gate + self.config.gate_s
        if self.config.placement == "restored":
            elapsed += travel
        if not math.isfinite(elapsed):
            return elapsed, 0.0
        elementary = age_channel(werner_channel(self.config.raw_bell_fidelity),
                                 2 / self.config.excitation_rate_hz, self.config.memory_t2_s)
        elementary = compose_pauli(elementary, self.teleport_noise)
        channels = []
        for path in paths:
            channel = identity_channel()
            for _ in path[1:]:
                channel = compose_pauli(channel, elementary)
            channels.append(age_channel(channel, before_gate, self.config.memory_t2_s))
        posts = [age_channel(identity_channel(), self.config.gate_s, self.config.memory_t2_s)
                 for _ in range(2)]
        if self.config.placement == "restored":
            for index, path in enumerate(paths):
                for _ in path[1:]:
                    posts[index] = compose_pauli(posts[index], elementary)
                posts[index] = age_channel(posts[index], travel, self.config.memory_t2_s)
        quality = gate_process_fidelity(*channels, self.config.gate_pauli_error, post_a=posts[0], post_b=posts[1])
        return elapsed, quality

    def _meeting(self, job):
        a, b = job.request.source, job.request.destination
        if self.config.policy == "hh":
            return b, None, None
        if self.config.policy == "paper_midpoint":
            return paper_meeting(a, b), None, None
        if self.config.policy == "midpoint":
            return minimax_meeting(a, b, self.config.mesh_side), None, None
        candidates = []
        weight = self.config.quality_weight_s if self.config.policy == "adaptive" else 0
        for meeting in geodesic_meetings(a, b, self.config.mesh_side):
            elapsed, quality = self._estimate(job, meeting)
            candidates.append((elapsed + weight * (1 - quality), elapsed, -quality, meeting))
        _, elapsed, negative_quality, meeting = min(candidates)
        return meeting, elapsed if math.isfinite(elapsed) else None, -negative_quality

    def _execute(self, request):
        yield self.kernel.delay(max(0, request.arrival_s - self.kernel.now))
        job = Job(request, [Operand("a", request.source, identity_channel(), self.kernel.now),
                            Operand("b", request.destination, identity_channel(), self.kernel.now)])
        self.emit(job.owner, "request_arrived", source=request.source, destination=request.destination,
                  deadline_s=request.deadline_s)
        planning_start = time.perf_counter()
        meeting, predicted_s, predicted_quality = self._meeting(job)
        controller_wall_s = time.perf_counter() - planning_start
        paths = [xy_path(operand.position, meeting) for operand in job.operands]
        self.emit(job.owner, "route_decision", meeting=meeting, predicted_latency_s=predicted_s,
                  predicted_process_fidelity=predicted_quality, observable_state_only=True)
        moved = yield self.kernel.all([self.kernel.spawn(self._move(op, path, job, "out"))
                                      for op, path in zip(job.operands, paths)])
        success = all(value is True for value in moved)
        input_channels = None
        if success:
            gate_lease = yield from self._acquire(self.cores[meeting].gate, job)
            if gate_lease is None:
                success = False
            else:
                try:
                    for operand in job.operands:
                        operand.age(self.kernel.now, self.config.memory_t2_s)
                    input_channels = [operand.channel.copy() for operand in job.operands]
                    for operand in job.operands:
                        operand.channel = identity_channel()
                        operand.last_update_s = self.kernel.now
                    success = yield from self._pause(self.config.gate_s, job)
                    self.emit(job.owner, "two_qubit_gate", meeting=meeting, completed=success)
                finally:
                    gate_lease.release()
        if success and self.config.placement == "restored":
            restored = yield self.kernel.all([self.kernel.spawn(self._move(op, list(reversed(path)), job, "return"))
                                             for op, path in zip(job.operands, paths)])
            success = all(value is True for value in restored)
        fidelity = None
        average = None
        if success:
            for operand in job.operands:
                operand.age(self.kernel.now, self.config.memory_t2_s)
            fidelity = gate_process_fidelity(*input_channels, self.config.gate_pauli_error,
                                            post_a=job.operands[0].channel, post_b=job.operands[1].channel)
            average = (4 * fidelity + 1) / 5
            if self.config.placement == "restored" and [o.position for o in job.operands] != [request.source, request.destination]:
                raise RuntimeError("Restored-placement task ended at incorrect cores")
        good = bool(success and fidelity >= self.config.minimum_process_fidelity)
        self.rows.append({"run_id": self.run_id, "seed": self.seed, "request_id": request.request_id,
                          "source": request.source, "destination": request.destination, "meeting": meeting,
                          "policy": self.config.policy, "placement": self.config.placement,
                          "classical": self.config.classical, "arrival_s": request.arrival_s,
                          "deadline_s": request.deadline_s, "finished_s": self.kernel.now,
                          "latency_s": self.kernel.now - request.arrival_s, "completed": success,
                          "quality_qualified": good, "process_fidelity": fidelity,
                          "average_gate_fidelity": average, "terminal_reason": "completed" if success else job.reason,
                          "controller_wall_s": controller_wall_s,
                          "predicted_latency_s": predicted_s, "predicted_process_fidelity": predicted_quality,
                          **job.counters})
        self.emit(job.owner, "request_terminal", completed=success, quality_qualified=good,
                  process_fidelity=fidelity, reason=job.reason)

    def run(self):
        started = time.perf_counter()
        for request in self.requests:
            self.kernel.spawn(self._execute(request))
        self.kernel.run()
        if len(self.rows) != len(self.requests):
            raise RuntimeError("A request did not terminate within the declared simulation horizon")
        resources = [*self.generators.values(), *(r for c in self.cores.values() for r in [c.memories, c.gate]),
                     *self.fabric.wired.values()]
        if self.pool is not None:
            resources.append(self.pool)
        if any(r.used or r.waiting_units for r in resources) or self.pairs.ready or not self.fabric.radio_idle:
            raise RuntimeError("Experiment terminated with leaked resources")
        self.rows.sort(key=lambda row: row["request_id"])
        completed = [r for r in self.rows if r["completed"]]
        observation_s = max(r.deadline_s for r in self.requests)
        summary = {"run_id": self.run_id, "seed": self.seed, "backend": "SeQUeNCe 1.3.0 native Timeline",
                   "config": self.config.to_dict(), "workload_sha256": workload_hash(self.requests),
                   "requests": len(self.rows), "completed": len(completed),
                   "quality_qualified": sum(r["quality_qualified"] for r in self.rows),
                   "observation_s": observation_s, "raw_pair_rate_s": sum(r["raw_pairs"] for r in self.rows) / observation_s,
                   "completed_gate_rate_s": len(completed) / observation_s,
                   "quality_gate_rate_s": sum(r["quality_qualified"] for r in self.rows) / observation_s,
                   "mean_completed_latency_s": float(np.mean([r["latency_s"] for r in completed])) if completed else None,
                   "p95_completed_latency_s": float(np.percentile([r["latency_s"] for r in completed], 95)) if completed else None,
                   "mean_completed_process_fidelity": float(np.mean([r["process_fidelity"] for r in completed])) if completed else None,
                   "attempts": sum(r["epr_attempts"] for r in self.rows),
                   "consumed_pairs": sum(r["consumed_pairs"] for r in self.rows),
                   "quantum_queue_wait_s": sum(r["quantum_queue_wait_s"] for r in self.rows),
                   "classical_wait_s": self.fabric.total_wait_s, "classical_packets": self.fabric.packets,
                   "classical_lost_packets": self.fabric.lost_packets,
                   "classical_bit_hops": self.fabric.transmitted_bits,
                   "radio_busy_s": self.fabric.busy_radio_s, "native_events": self.kernel.timeline.run_counter,
                   "wall_time_s": time.perf_counter() - started,
                   "generator_capacity": self.config.pooled_servers or len(self.generators) * self.config.link_servers,
                   "resource_leaks": 0}
        return {"summary": summary, "requests": self.rows, "events": self.events}
