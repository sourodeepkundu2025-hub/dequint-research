"""Contended wired mesh and shared token-based radio; no quantum payload bits."""

import math
from collections import defaultdict, deque

from .kernel import FifoResource, PS_PER_SECOND, Signal
from .routing import mesh_edges, xy_path


class ClassicalFabric:
    def __init__(self, kernel, config, streams, emit):
        self.kernel, self.config, self.streams, self.emit = kernel, config, streams, emit
        self.wired = {}
        for a, b in mesh_edges(config.mesh_side):
            for source, destination in [(a, b), (b, a)]:
                self.wired[(source, destination)] = FifoResource(kernel, f"wire:{source}:{destination}")
        self.queues = [defaultdict(deque) for _ in range(config.radio_channels)]
        self.tokens = [0] * config.radio_channels
        self.running = [False] * config.radio_channels
        self.packets = 0
        self.lost_packets = 0
        self.transmitted_bits = 0
        self.total_wait_s = 0.0
        self.busy_radio_s = 0.0

    def _pause(self, duration, deadline):
        remaining = deadline - self.kernel.now
        if remaining <= 0:
            return False
        yield self.kernel.delay(min(duration, remaining))
        return duration <= remaining + 1e-12

    def _radio_expire(self, packet):
        if packet["active"]:
            packet["active"] = False
            packet["signal"].succeed(False)

    def _enqueue_radio(self, source, destination, bits, deadline, owner, tag):
        index = source[0] * self.config.mesh_side + source[1]
        channel = index % self.config.radio_channels
        signal = Signal(self.kernel)
        packet = {"source": source, "destination": destination, "index": index,
                  "bits": bits, "deadline": deadline, "owner": owner, "tag": tag,
                  "enqueued": self.kernel.now, "signal": signal, "active": True}
        self.queues[channel][index].append(packet)
        # Inclusive completion deadlines: a final service event at deadline wins.
        self.kernel.call_at(deadline + 1e-12, self._radio_expire, packet)
        if not self.running[channel]:
            self.running[channel] = True
            self.kernel.spawn(self._radio_worker(channel))
        return signal

    def _radio_worker(self, channel):
        size = self.config.mesh_side**2
        while True:
            for queue in self.queues[channel].values():
                while queue and not queue[0]["active"]:
                    queue.popleft()
            pending = [node for node, queue in self.queues[channel].items() if queue]
            if not pending:
                self.running[channel] = False
                return
            node = min(pending, key=lambda n: (n - self.tokens[channel]) % size)
            rotations = (node - self.tokens[channel]) % size
            earliest = min(p["deadline"] for queue in self.queues[channel].values()
                           for p in queue if p["active"])
            step_ps = round(self.config.radio_token_s * PS_PER_SECOND)
            travel_ps = rotations * step_ps
            expiry_ps = round(earliest * PS_PER_SECOND) + 1
            wait_ps = min(travel_ps, max(0, expiry_ps - self.kernel.timeline.now()))
            yield self.kernel.delay(wait_ps / PS_PER_SECOND)
            # Compare native ticks, not floating seconds at equal-time boundaries.
            steps = wait_ps // step_ps if step_ps else rotations
            self.tokens[channel] = (self.tokens[channel] + steps) % size
            if wait_ps < travel_ps:
                continue
            self.tokens[channel] = node
            queue = self.queues[channel][node]
            if not queue:
                continue
            packet = queue.popleft()
            if not packet["active"]:
                continue
            waiting = self.kernel.now - packet["enqueued"]
            self.total_wait_s += waiting
            a, b = packet["source"], packet["destination"]
            propagation = math.hypot(a[0] - b[0], a[1] - b[1]) * self.config.link_length_m / 1.5e8
            service = self.config.radio_startup_s + packet["bits"] / self.config.radio_rate_bps + propagation
            before = self.kernel.now
            completed = yield from self._pause(service, packet["deadline"])
            self.busy_radio_s += self.kernel.now - before
            self.tokens[channel] = (node + 1) % size
            if packet["active"]:
                packet["active"] = False
                if completed:
                    self.transmitted_bits += packet["bits"]
                self.emit(packet["owner"], "classical_radio", tag=packet["tag"], bits=packet["bits"],
                          source=a, destination=b, wait_s=waiting, completed=completed, channel=channel)
                packet["signal"].succeed(completed)

    def _wired_send(self, source, destination, bits, deadline, owner, tag):
        path = xy_path(source, destination)
        for a, b in zip(path, path[1:]):
            resource = self.wired[(a, b)]
            entered = self.kernel.now
            lease = yield resource.request(owner, deadline)
            if lease is None:
                return False
            waiting = self.kernel.now - entered
            self.total_wait_s += waiting
            try:
                cycles = self.config.wired_router_cycles + math.ceil(bits / self.config.wired_width_bits)
                service = cycles / self.config.wired_clock_hz + self.config.link_length_m / 2e8
                completed = yield from self._pause(service, deadline)
                if not completed:
                    return False
                self.transmitted_bits += bits
                self.emit(owner, "classical_wired", tag=tag, source=a, destination=b, bits=bits, wait_s=waiting)
            finally:
                lease.release()
        return True

    def send(self, source, destination, bits, deadline, owner, tag):
        if bits <= 0:
            raise ValueError("Classical messages need positive size")
        if source == destination:
            return (yield from self._pause(self.config.wired_router_cycles / self.config.wired_clock_hz, deadline))
        for attempt in range(self.config.max_attempts):
            if self.kernel.now >= deadline:
                return False
            self.packets += 1
            if self.config.classical == "radio":
                completed = yield self._enqueue_radio(source, destination, bits, deadline, owner, tag)
            else:
                completed = yield from self._wired_send(source, destination, bits, deadline, owner, tag)
            if not completed:
                return False
            dropped = self.streams.random(owner, "packet_loss", source, destination, tag) < self.config.packet_loss
            if not dropped:
                return True
            self.lost_packets += 1
            self.emit(owner, "classical_packet_loss", source=source, destination=destination, tag=tag, retry=attempt)
            if not (yield from self._pause(self.config.classical_ack_timeout_s, deadline)):
                return False
        return False

    def estimated_wait(self, source, destination, bits):
        if self.config.classical == "radio":
            channel = (source[0] * self.config.mesh_side + source[1]) % self.config.radio_channels
            pending = sum(sum(p["active"] for p in queue) for queue in self.queues[channel].values())
            return pending * (bits / self.config.radio_rate_bps + self.config.radio_token_s)
        path = xy_path(source, destination)
        return sum((resource.used + resource.waiting_units) *
                   (self.config.wired_router_cycles + math.ceil(bits / self.config.wired_width_bits)) /
                   self.config.wired_clock_hz
                   for resource in [self.wired[(a, b)] for a, b in zip(path, path[1:])])

    @property
    def radio_idle(self):
        return not any(self.running) and not any(queue for channel in self.queues for queue in channel.values())
