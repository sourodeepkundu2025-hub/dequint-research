"""Bounded topology/provisioning investigation, NOT full native gate validation.

The binary de Bruijn topology is established, not a novelty claim. NetworkX
provides simple undirected graphs and routes; only Kernel/FifoResource execute
on native SeQUeNCe. Generation is a two-round Bernoulli abstraction, not native
photons, detectors or optical protocols. Optional task quality below is an
independent-Pauli calculation, not a density-matrix/native CNOT execution.

Each node has finite switchable active optical ports shared by its installed
edge terminations. Each physical edge also has exclusive capacity-one channel
service through generation and transfer; a generator is released after heralding.
The global pool is an abstract matched service budget, NOT a free physical
pooled switch. Installed links/terminations/cabling are separately costed.
There is no EPR stockpile, purification, finite data-memory model, memory
cutoff, or contended classical network. Correction
uses an uncontended direct sideband along the same Euclidean edge. No hardware,
energy, topology-novelty or compiled-depth inference follows from this probe.

Run a small comparison (JSON to stdout, no files written)::

    python -m dequint.shortcut_probe --side 4 --requests 8 --seed 19
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass, replace
from numbers import Integral, Real

import networkx as nx

from .kernel import FifoResource, Kernel
from .quantum import (age_channel, compose_pauli, gate_process_fidelity,
                      identity_channel, pauli_depolarizing, werner_channel)
from .workload import RandomStreams, Request, make_workload, workload_hash


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


def _real(value, name, minimum=0, positive=False):
    if (isinstance(value, bool) or not isinstance(value, Real)
            or not math.isfinite(value) or value < minimum or (positive and value == 0)):
        raise ValueError(f"Invalid {name}")
    return float(value)


def _side(side):
    side = _integer(side, "side", 2)
    if side & (side - 1):
        raise ValueError("side must be a power of two; N = side**2")
    return side


@dataclass(frozen=True)
class ProbeConfig:
    side: int = 4
    topology: str = "mesh_debruijn"
    scaling: str = "fixed_pitch"
    pitch_m: float = .001
    footprint_m: float | None = None
    route_metric: str = "hops"
    placement: str = "free"
    ports_per_node: int = 2
    generator_mode: str = "global"
    generator_capacity: int = 1
    excitation_rate_hz: float = 20_000
    reset_s: float = 50e-9
    emission_efficiency: float = .75
    detector_efficiency: float = .8
    source_outage_probability: float = 0
    attenuation_db_per_m: float = .01
    shortcut_insertion_loss_db: float = 0
    propagation_m_per_s: float = 2e8
    raw_bell_fidelity: float = .99
    memory_t2_s: float = .01
    teleport_s: float = 100e-9
    teleport_pauli_error: float = .001
    gate_s: float = 50e-9
    gate_pauli_error: float = .001
    max_attempts: int = 100
    max_events: int = 500_000

    def validate(self):
        _side(self.side)
        for name, options in {
            "topology": {"mesh", "mesh_debruijn"},
            "scaling": {"fixed_pitch", "fixed_footprint"},
            "route_metric": {"hops", "expected_time"},
            "placement": {"free", "restored"},
            "generator_mode": {"global", "per_link"},
        }.items():
            if getattr(self, name) not in options:
                raise ValueError(f"Invalid {name}")
        for name in ("ports_per_node", "generator_capacity", "max_attempts", "max_events"):
            _integer(getattr(self, name), name, 1)
        for name in ("pitch_m", "excitation_rate_hz", "propagation_m_per_s", "memory_t2_s"):
            _real(getattr(self, name), name, positive=True)
        for name in ("reset_s", "attenuation_db_per_m", "shortcut_insertion_loss_db", "teleport_s", "gate_s"):
            _real(getattr(self, name), name)
        for name in ("emission_efficiency", "detector_efficiency", "source_outage_probability",
                     "raw_bell_fidelity", "teleport_pauli_error", "gate_pauli_error"):
            if _real(getattr(self, name), name) > 1:
                raise ValueError(f"Invalid {name}")
        if self.scaling == "fixed_footprint":
            _real(self.footprint_m, "footprint_m", positive=True)
        elif self.footprint_m is not None:
            raise ValueError("footprint_m is only used for fixed_footprint")
        return self

    @property
    def effective_pitch_m(self):
        return self.pitch_m if self.scaling == "fixed_pitch" else self.footprint_m / (self.side - 1)


def link_parameters(config: ProbeConfig, length_m: float, *, is_mesh: bool = True):
    """Combined two-half-arm loss and a declared two-round timing model.

    Each round has excitation + half reset + L/(2v) photon flight + L/(2v)
    herald return. Thus two rounds take 2/rate + reset + 2L/v. The specified
    aggregate generation law uses T_half**2 = 10**(-alpha*L/10), once, not
    squared again for the two rounds. Non-mesh physical edges additionally use
    shortcut_insertion_loss_db as a total two-arm dB penalty ONCE. An edge also
    present in the mesh retains mesh loss. This is not derived/native optics.
    """
    config.validate()
    length_m = _real(length_m, "length_m")
    if not isinstance(is_mesh, bool):
        raise ValueError("is_mesh must be boolean")
    insertion_db = 0 if is_mesh else config.shortcut_insertion_loss_db
    transmission = 10 ** (-(config.attenuation_db_per_m * length_m + insertion_db) / 10)
    success = (.5 * (config.emission_efficiency * config.detector_efficiency)**2
               * transmission * (1 - config.source_outage_probability))
    attempt_s = 2 / config.excitation_rate_hz + config.reset_s + 2 * length_m / config.propagation_m_per_s
    return {"length_m": length_m, "insertion_loss_db": insertion_db, "transmission": transmission,
            "generation_success": success, "attempt_s": attempt_s,
            "transfer_s": config.teleport_s + length_m / config.propagation_m_per_s,
            "expected_time": attempt_s / success + config.teleport_s
            + length_m / config.propagation_m_per_s if success else math.inf}


def build_topology(config: ProbeConfig) -> nx.Graph:
    """Row-major mesh union loop-free, undirected binary de Bruijn edges."""
    config.validate()
    side, n = config.side, config.side**2
    graph = nx.relabel_nodes(nx.grid_2d_graph(side, side),
                             lambda xy: xy[0] * side + xy[1])
    nx.set_edge_attributes(graph, True, "mesh")
    nx.set_edge_attributes(graph, False, "debruijn")
    if config.topology == "mesh_debruijn":
        for source in range(n):
            for bit in (0, 1):
                destination = ((source << 1) | bit) & (n - 1)
                if source == destination:
                    continue
                if not graph.has_edge(source, destination):
                    graph.add_edge(source, destination, mesh=False)
                graph[source][destination]["debruijn"] = True
    for node in graph:
        row, col = divmod(node, side)
        graph.nodes[node]["coordinate_m"] = (row * config.effective_pitch_m,
                                               col * config.effective_pitch_m)
    for a, b, attrs in graph.edges(data=True):
        length = math.dist(graph.nodes[a]["coordinate_m"], graph.nodes[b]["coordinate_m"])
        attrs.update(link_parameters(config, length, is_mesh=attrs["mesh"]))
    return graph


def constructive_path(side: int, source: int, destination: int) -> list[int]:
    """Append destination bits, most significant first: at most log2(N) hops.

    For m=log2(N), after k shifts the register holds the last m-k source bits
    followed by the first k destination bits. After m shifts it is destination.
    Every non-self shift is a de Bruijn edge. Erasing loops only shortens this
    walk. Undirecting preserves it. There are <=2 predecessors + 2 successors,
    hence union with the degree-4 mesh has maximum degree <=8. This proves a
    hop bound, not a physical latency or cost bound.
    """
    n = _side(side)**2
    for value in (source, destination):
        if _integer(value, "node") >= n:
            raise ValueError("Node outside topology")
    path, current = [source], source
    for shift in reversed(range(n.bit_length() - 1)):
        current = ((current << 1) | ((destination >> shift) & 1)) & (n - 1)
        if current in path:
            path = path[:path.index(current) + 1]
        else:
            path.append(current)
    return path


def topology_cost(config: ProbeConfig, graph: nx.Graph | None = None):
    graph = build_topology(config) if graph is None else graph
    lengths = [attrs["length_m"] for _, _, attrs in graph.edges(data=True)]
    edges = graph.number_of_edges()
    return {"nodes": graph.number_of_nodes(), "edges": edges,
            "mesh_edges": sum(bool(d["mesh"]) for _, _, d in graph.edges(data=True)),
            "added_shortcut_edges": sum(not d["mesh"] for _, _, d in graph.edges(data=True)),
            "max_degree": max(dict(graph.degree()).values()),
            "edge_terminations": 2 * edges,
            "switchable_active_ports": graph.number_of_nodes() * config.ports_per_node,
            "ports_per_node": config.ports_per_node,
            "port_model": "shared switchable active ports; installed edge terminations counted separately",
            "generator_mode": config.generator_mode,
            "global_pool_scope": "abstract service budget, not a physical pooled-switch model",
            "channel_capacity_per_physical_edge": 1,
            "total_generator_capacity": config.generator_capacity * (edges if config.generator_mode == "per_link" else 1),
            "total_optical_length_m": math.fsum(lengths), "max_link_m": max(lengths),
            "scaling": config.scaling, "effective_pitch_m": config.effective_pitch_m,
            "footprint_side_m": (config.side - 1) * config.effective_pitch_m}


def probe_workload(side=4, requests=8, seed=19, arrival_rate=1000, deadline_s=.05):
    """Reuse the existing policy-independent source/destination workload API."""
    _side(side)
    _integer(requests, "requests", 1)
    _integer(seed, "seed")
    _real(arrival_rate, "arrival_rate", positive=True)
    _real(deadline_s, "deadline_s", positive=True)
    return make_workload(side, requests, arrival_rate, seed, deadline_s)


class ShortcutProbe:
    """Finite-resource serial-hop provisioning for ordered CNOT(control,target).

    Rendezvous is always the original target node. The target stays put, while
    the control moves outbound and, for restored placement, back on the reversed
    route using fresh pairs. An exclusive local gate timer is modeled, but no
    native quantum gate is executed. Analytic pre/post Pauli channels preserve
    CNOT correlations via the existing gate_process_fidelity helper.
    """

    def __init__(self, config: ProbeConfig, requests: list[Request], seed=19):
        self.config = config.validate()
        self.seed = _integer(seed, "seed")
        self.requests = list(requests)
        if not self.requests:
            raise ValueError("Empty workload")
        identifiers = set()
        for request in self.requests:
            _integer(request.request_id, "request_id")
            if request.request_id in identifiers:
                raise ValueError("Duplicate request_id")
            identifiers.add(request.request_id)
            self._node(request.source)
            self._node(request.destination)
            _real(request.arrival_s, "arrival_s")
            _real(request.deadline_s, "deadline_s")
            if request.deadline_s <= request.arrival_s:
                raise ValueError("Deadline must follow arrival")
        self.graph = build_topology(config)
        horizon = max(r.deadline_s for r in self.requests) + 1e-6
        self.kernel = Kernel(horizon_s=horizon, max_events=config.max_events)
        self.ports = {n: FifoResource(self.kernel, f"port:{n}", config.ports_per_node) for n in self.graph}
        self.gates = {n: FifoResource(self.kernel, f"gate:{n}") for n in self.graph}
        self.links = {tuple(sorted(e)): FifoResource(self.kernel, f"channel:{tuple(sorted(e))}")
                      for e in sorted(self.graph.edges)}
        keys = ["global"] if config.generator_mode == "global" else sorted(tuple(sorted(e)) for e in self.graph.edges)
        self.generators = {key: FifoResource(self.kernel, f"generator:{key}", config.generator_capacity) for key in keys}
        self.streams = RandomStreams(seed)
        self.rows, self.events = [], []
        self._started = False

    def _node(self, xy):
        if not isinstance(xy, (tuple, list)) or len(xy) != 2:
            raise ValueError("Node must be a (row, col) coordinate")
        for value in xy:
            if _integer(value, "coordinate") >= self.config.side:
                raise ValueError("Coordinate outside topology")
        return xy[0] * self.config.side + xy[1]

    def _emit(self, row, action, **fields):
        self.events.append({"request_id": row["request_id"], "time_s": self.kernel.now,
                            "action": action, **fields})

    def _pause(self, duration, row):
        remaining = row["deadline_s"] - self.kernel.now
        if remaining <= 0:
            row["terminal_reason"] = "deadline"
            return False
        # SeQUeNCe ticks are picoseconds. Round once before deadline comparison.
        ticks = max(1, round(duration * 1e12)) if duration else 0
        remaining_ticks = round(remaining * 1e12)
        yield self.kernel.delay(min(ticks, remaining_ticks) / 1e12)
        if ticks > remaining_ticks:
            row["terminal_reason"] = "deadline"
            return False
        return True

    def _acquire(self, resource, row, wait_key):
        before = self.kernel.now
        lease = yield resource.request(str(row["request_id"]), row["deadline_s"])
        waited = self.kernel.now - before
        row["wait_s"] += waited
        row[wait_key] += waited
        self._emit(row, "admission", resource=resource.name, wait_s=waited, admitted=lease is not None)
        if lease is None:
            row["terminal_reason"] = "resource_deadline"
        return lease

    def _hop(self, a, b, row, phase):
        edge = tuple(sorted((a, b)))
        attrs = self.graph[a][b]
        leases = []
        try:
            # Global node order avoids circular port waits across concurrent hops.
            for node in edge:
                lease = yield from self._acquire(self.ports[node], row, "port_wait_s")
                if lease is None:
                    return None
                leases.append(lease)
            lease = yield from self._acquire(self.links[edge], row, "channel_wait_s")
            if lease is None:
                return None
            leases.append(lease)
            generator = self.generators["global" if self.config.generator_mode == "global" else edge]
            lease = yield from self._acquire(generator, row, "generator_wait_s")
            if lease is None:
                return None
            leases.append(lease)
            for attempt in range(self.config.max_attempts):
                row["attempts"] += 1
                row["retries"] += int(attempt > 0)
                if not (yield from self._pause(attrs["attempt_s"], row)):
                    row["aborted_attempts"] += 1
                    return None
                row["completed_attempts"] += 1
                # Common random numbers by request/phase/hop, independent of edge
                # labels/topology; differing routes still consume differing draws.
                accepted = self.streams.random(row["request_id"], phase, row["quantum_hops"], "epr") < attrs["generation_success"]
                self._emit(row, "attempt", edge=edge, phase=phase, accepted=accepted,
                           probability=attrs["generation_success"], length_m=attrs["length_m"])
                if accepted:
                    row["raw_pairs"] += 1
                    break
                row["failed_attempts"] += 1
            else:
                row["terminal_reason"] = "attempt_bound"
                return None
            lease.release()
            if self.kernel.now >= row["deadline_s"]:
                row["pairs_discarded"] += 1
                row["terminal_reason"] = "deadline"
                return None
            row["pairs_consumed"] += 1
            row["control_position"] = None  # Payload measurement: no source retry.
            self._emit(row, "pair_consumed", edge=edge, phase=phase)
            if not (yield from self._pause(attrs["transfer_s"], row)):
                return None
            row["quantum_hops"] += 1
            row["control_position"] = b
            # Declared second-round and two-endpoint post-herald storage aging.
            channel = age_channel(werner_channel(self.config.raw_bell_fidelity),
                                  attrs["attempt_s"] + 2 * attrs["transfer_s"], self.config.memory_t2_s)
            return compose_pauli(channel, pauli_depolarizing(self.config.teleport_pauli_error))
        finally:
            for lease in reversed(leases):
                if not lease.released:
                    lease.release()

    def _move(self, path, row, phase, channel, last_s):
        for a, b in zip(path, path[1:]):
            hop_channel = yield from self._hop(a, b, row, phase)
            if hop_channel is None:
                return None
            channel = compose_pauli(age_channel(channel, self.kernel.now - last_s,
                                                self.config.memory_t2_s), hop_channel)
            last_s = self.kernel.now
        return channel, last_s

    def _execute(self, request):
        yield self.kernel.delay(request.arrival_s - self.kernel.now)
        started_s = self.kernel.now
        source, target = self._node(request.source), self._node(request.destination)
        weight = None if self.config.route_metric == "hops" else "expected_time"
        path = nx.shortest_path(self.graph, source, target, weight=weight)
        row = {"request_id": request.request_id, "source": source, "target": target,
               "control_position": source, "target_position": target,
               "arrival_s": request.arrival_s, "deadline_s": request.deadline_s,
               "route": path, "planned_hops": (len(path) - 1) * (2 if self.config.placement == "restored" else 1),
               "completed": False, "terminal_reason": "", "conditional_process_fidelity": None,
               "conditional_average_gate_fidelity": None,
               **{k: 0 for k in ("attempts", "completed_attempts", "aborted_attempts", "retries",
                                "failed_attempts", "raw_pairs", "pairs_consumed", "pairs_discarded",
                                "quantum_hops", "gate_timers_completed")},
               **{k: 0.0 for k in ("wait_s", "port_wait_s", "channel_wait_s", "generator_wait_s", "gate_wait_s")}}
        try:
            moved = yield from self._move(path, row, "out", identity_channel(), started_s)
            if moved is None:
                return
            gate = yield from self._acquire(self.gates[target], row, "gate_wait_s")
            if gate is None:
                return
            try:
                gate_start = self.kernel.now
                pre_a = age_channel(moved[0], gate_start - moved[1], self.config.memory_t2_s)
                pre_b = age_channel(identity_channel(), gate_start - started_s, self.config.memory_t2_s)
                if not (yield from self._pause(self.config.gate_s, row)):
                    return
                row["gate_timers_completed"] = 1
            finally:
                gate.release()
            post = (identity_channel(), gate_start)
            if self.config.placement == "restored":
                post = yield from self._move(list(reversed(path)), row, "return", *post)
                if post is None:
                    return
            post_a = age_channel(post[0], self.kernel.now - post[1], self.config.memory_t2_s)
            post_b = age_channel(identity_channel(), self.kernel.now - gate_start, self.config.memory_t2_s)
            fidelity = gate_process_fidelity(pre_a, pre_b, self.config.gate_pauli_error,
                                             post_a=post_a, post_b=post_b)
            row.update(completed=True, terminal_reason="completed", conditional_process_fidelity=fidelity,
                       conditional_average_gate_fidelity=(4 * fidelity + 1) / 5)
        finally:
            row.update(finished_s=self.kernel.now, latency_s=max(0, self.kernel.now - request.arrival_s))
            self.rows.append(row)

    def run(self):
        if self._started:
            raise ValueError("Probe instances are single-use")
        self._started = True
        tasks = [self.kernel.spawn(self._execute(r)) for r in self.requests]
        self.kernel.run()
        resources = [*self.ports.values(), *self.links.values(), *self.generators.values(), *self.gates.values()]
        if not all(t.done for t in tasks) or any(r.used or r.waiting_units for r in resources):
            raise RuntimeError("Probe did not drain tasks/resources")
        self.rows.sort(key=lambda r: r["request_id"])
        return {"scope": "finite-resource EPR provisioning and route timing; analytic ordered-CNOT Pauli task",
                "backend": "native SeQUeNCe Kernel/FifoResource, abstract Bernoulli optics",
                "full_native_gate_validation": False, "hardware": False,
                "topology_novelty_claim": False,
                "quality_scope": "conditional independent-Pauli model; no cutoff/purification/data-memory capacity",
                "config": asdict(self.config), "seed": self.seed,
                "workload_hash": workload_hash(self.requests), "cost": topology_cost(self.config, self.graph),
                "rows": self.rows, "events": self.events,
                "summary": {"requests": len(self.rows), "completed": sum(r["completed"] for r in self.rows),
                            "failed": sum(not r["completed"] for r in self.rows),
                            **{k: sum(r[k] for r in self.rows) for k in (
                                "attempts", "completed_attempts", "failed_attempts", "aborted_attempts", "retries",
                                "raw_pairs", "pairs_consumed", "pairs_discarded", "wait_s")}},
                "resources": [{"name": r.name, "capacity": r.capacity, "peak_used": r.peak_used,
                               "used": r.used, "waiting_units": r.waiting_units,
                               "integral_used_s": r.integral_used_s} for r in resources]}


def compare_topologies(config: ProbeConfig, requests: list[Request], seed=19):
    """Same frozen workload/seed; global capacity is matched, per-link is not."""
    requests = list(requests)
    return {"matched_global_generation_capacity": config.generator_mode == "global",
            "runs": {topology: ShortcutProbe(replace(config, topology=topology), requests, seed).run()
                     for topology in ("mesh", "mesh_debruijn")}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--side", type=int, default=4)
    parser.add_argument("--requests", type=int, default=8)
    parser.add_argument("--seed", type=int, default=19)
    parser.add_argument("--scaling", choices=("fixed_pitch", "fixed_footprint"), default="fixed_pitch")
    parser.add_argument("--pitch-m", type=float, default=.001)
    parser.add_argument("--footprint-m", type=float)
    parser.add_argument("--placement", choices=("free", "restored"), default="free")
    parser.add_argument("--route-metric", choices=("hops", "expected_time"), default="hops")
    parser.add_argument("--ports-per-node", type=int, default=2)
    parser.add_argument("--generator-mode", choices=("global", "per_link"), default="global")
    parser.add_argument("--generator-capacity", type=int, default=1)
    parser.add_argument("--attenuation-db-per-m", type=float, default=.01)
    parser.add_argument("--shortcut-insertion-loss-db", type=float, default=0)
    parser.add_argument("--arrival-rate", type=float, default=1000)
    parser.add_argument("--deadline-s", type=float, default=.05)
    args = parser.parse_args(argv)
    config = ProbeConfig(side=args.side, scaling=args.scaling, pitch_m=args.pitch_m,
                         footprint_m=args.footprint_m, placement=args.placement, route_metric=args.route_metric,
                         ports_per_node=args.ports_per_node, generator_mode=args.generator_mode,
                         generator_capacity=args.generator_capacity,
                         attenuation_db_per_m=args.attenuation_db_per_m,
                         shortcut_insertion_loss_db=args.shortcut_insertion_loss_db)
    requests = probe_workload(args.side, args.requests, args.seed, args.arrival_rate, args.deadline_s)
    print(json.dumps(compare_topologies(config, requests, args.seed), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
