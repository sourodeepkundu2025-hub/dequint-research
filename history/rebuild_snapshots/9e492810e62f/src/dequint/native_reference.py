"""Bounded official SeQUeNCe 1.3.0 reference submodels, not a mesh simulator.

Uses native photons/detectors/generation, TeleportApp/TeleportProtocol, native
BBPSSW and swapping circuits. No dependency on DEQUINT's scheduler or channel
implementation. Run serially: upstream protocol/formalism selectors are global.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import inspect
import io
import json
import os
import subprocess
import tarfile
from contextlib import contextmanager
from numbers import Integral
from pathlib import Path
from threading import RLock

import numpy as np
import sequence
from sequence.app.teleport_app import TeleportApp
from sequence.components.detector import Detector
from sequence.components.memory import Memory, MemoryArray
from sequence.components.optical_channel import ClassicalChannel, QuantumChannel
from sequence.constants import BARRET_KOK, DENSITY_MATRIX_FORMALISM, KET_VECTOR_FORMALISM, MILLISECOND
from sequence.entanglement_management.generation import EntanglementGenerationA, EntanglementGenerationB
from sequence.entanglement_management.purification import PurificationProtocol
from sequence.entanglement_management.swapping import EntanglementSwappingA, EntanglementSwappingB
from sequence.entanglement_management.teleportation import TeleportProtocol
from sequence.kernel.event import Event
from sequence.kernel.process import Process
from sequence.kernel.quantum_manager import QuantumManager
from sequence.kernel.timeline import Timeline
from sequence.topology.dqc_net_topo import DQCNetTopo
from sequence.topology.node import BSMNode, Node
from sequence.utils import metrics


UPSTREAM_COMMIT = "88f92cca8aaa6dbf82bccc6a759465120afbdd34"
_LOCK = RLock()
_PHI_PLUS = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)


@contextmanager
def _native_settings():
    """Restore upstream global selectors and metrics' time-provider on all exits."""
    with _LOCK:
        if metrics._enabled:
            raise RuntimeError("Run native reference in a separate process from enabled native metrics")
        settings = (QuantumManager.get_active_formalism(),
                    EntanglementGenerationA.get_global_type(), EntanglementGenerationB.get_global_type(),
                    PurificationProtocol.get_formalism(), EntanglementSwappingA.get_formalism(),
                    EntanglementSwappingB.get_formalism())
        had_provider = hasattr(metrics, "time_provider")
        provider = getattr(metrics, "time_provider", None)
        try:
            _formalism(KET_VECTOR_FORMALISM)
            EntanglementGenerationA.set_global_type(BARRET_KOK)
            EntanglementGenerationB.set_global_type(BARRET_KOK)
            yield
        finally:
            QuantumManager.set_global_manager_formalism(settings[0])
            EntanglementGenerationA.set_global_type(settings[1])
            EntanglementGenerationB.set_global_type(settings[2])
            PurificationProtocol.set_formalism(settings[3])
            EntanglementSwappingA.set_formalism(settings[4])
            EntanglementSwappingB.set_formalism(settings[5])
            if had_provider:
                metrics.register_time_provider(provider)
            elif hasattr(metrics, "time_provider"):
                del metrics.time_provider


def _formalism(formalism):
    QuantumManager.set_global_manager_formalism(formalism)
    PurificationProtocol.set_formalism(formalism)
    EntanglementSwappingA.set_formalism(formalism)
    EntanglementSwappingB.set_formalism(formalism)


def _complex_array(array):
    array = np.asarray(array)
    return {"real": array.real.tolist(), "imag": array.imag.tolist()}


def _pair_density(fidelity):
    # Direct isotropic density matrix, without calling DEQUINT's Pauli formulas.
    projector = np.outer(_PHI_PLUS, _PHI_PLUS.conj())
    return fidelity * projector + (1 - fidelity) * (np.eye(4) - projector) / 3


def _overlap(manager, memories):
    state = manager.get(memories[0].qstate_key)
    expected_keys = {m.qstate_key for m in memories}
    if set(state.keys) != expected_keys:
        return None
    array = np.asarray(state.state, dtype=complex)
    # Phi+ is invariant to swapping the two qubits; key order cannot change this overlap.
    if array.ndim == 1:
        return float(abs(np.vdot(_PHI_PLUS, array)) ** 2)
    return float(np.vdot(_PHI_PLUS, array @ _PHI_PLUS).real)


def _resource_event(timeline, node, protocol, memory, state):
    return {"time_ps": int(timeline.now()), "kind": "resource_update", "node": node,
            "protocol": type(protocol).__name__ if protocol is not None else None,
            "memory": memory.name, "state": state, "metadata_fidelity": float(memory.fidelity),
            "remote_node": memory.entangled_memory["node_id"]}


class _ResourceRecorder:
    """Minimal lifecycle adapter, like upstream protocol unit-test node harnesses."""

    def __init__(self, owner, records):
        self.owner, self.records = owner, records

    def update(self, protocol, memory, state):
        self.records.append(_resource_event(self.owner.timeline, self.owner.name, protocol, memory, state))
        if state == "RAW":
            memory.reset()


class _ReferenceNode(Node):
    def __init__(self, name, timeline, seed, records):
        super().__init__(name, timeline, seed=seed)
        self.resource_manager = _ResourceRecorder(self, records)
        self.memory_array = None

    def init(self):
        if self.memory_array is not None:
            self.memory_array.add_receiver(self)

    def get(self, photon, **kwargs):
        self.send_qubit(kwargs["dst"], photon)


class _Clicks:
    def __init__(self, records):
        self.records = records

    def trigger(self, detector, info):
        self.records.append({"time_ps": int(detector.timeline.now()), "kind": "detector_click",
                             "detector": detector.name, "resolved_time_ps": int(info["time"])})


def _observe(timeline, nodes, records, *, resources=False):
    """Per-instance observation only; delegate all state evolution to native code."""
    for node in nodes:
        original_send = node.send_message

        def send(destination, message, *args, _send=original_send, _node=node, **kwargs):
            row = {"time_ps": int(timeline.now()), "kind": "classical_send", "node": _node.name,
                   "destination": destination, "message": type(message).__name__,
                   "message_type": message.msg_type.name}
            for field in ("x_flip", "z_flip", "meas_res", "fidelity"):
                value = getattr(message, field, None)
                if value is not None:
                    row[field] = value
            records.append(row)
            return _send(destination, message, *args, **kwargs)

        node.send_message = send
        original_qubit = node.send_qubit

        def send_qubit(destination, photon, *args, _send=original_qubit, _node=node, **kwargs):
            records.append({"time_ps": int(timeline.now()), "kind": "photon_emission",
                            "node": _node.name, "destination": destination,
                            "is_null": bool(photon.is_null)})
            return _send(destination, photon, *args, **kwargs)

        node.send_qubit = send_qubit
        if resources and hasattr(node, "resource_manager"):
            original_update = node.resource_manager.update

            def update(protocol, memory, state, _update=original_update, _node=node):
                records.append(_resource_event(timeline, _node.name, protocol, memory, state))
                return _update(protocol, memory, state)

            node.resource_manager.update = update
    observer = _Clicks(records)
    for entity in timeline.entities.values():
        if isinstance(entity, Detector):
            entity.attach(observer)


def _components(timeline):
    records = []
    attributes = ("raw_fidelity", "frequency", "efficiency", "coherence_time", "wavelength",
                  "dark_count", "count_rate", "time_resolution", "distance", "attenuation", "delay")
    for entity in timeline.entities.values():
        if isinstance(entity, (Memory, Detector, QuantumChannel, ClassicalChannel)):
            row = {"name": entity.name, "class": type(entity).__name__}
            for key in attributes:
                if hasattr(entity, key):
                    row[key] = float(getattr(entity, key))
            records.append(row)
    return records


def _counters(timeline, events):
    return {"scheduled_events": timeline.schedule_counter, "executed_events": timeline.run_counter,
            "final_simulation_time_ps": int(timeline.now()),
            "photon_emissions": sum(e["kind"] == "photon_emission" for e in events),
            "detector_clicks": sum(e["kind"] == "detector_click" for e in events),
            "classical_messages": sum(e["kind"] == "classical_send" for e in events)}


def _classical(nodes, timeline, delay_ps=10_000_000):
    for source in nodes:
        for target in nodes:
            if source is not target:
                channel = ClassicalChannel(f"cc.{source.name}.{target.name}", timeline, 0, delay=delay_ps)
                channel.set_ends(source, target.name)


def _generation_trial(seeds):
    _formalism(KET_VECTOR_FORMALISM)
    timeline, events = Timeline(10 * MILLISECOND), []
    alice = _ReferenceNode("alice", timeline, seeds[0], events)
    bob = _ReferenceNode("bob", timeline, seeds[1], events)
    middle = BSMNode("middle", timeline, [alice.name, bob.name], seed=seeds[2],
        component_templates={"SingleAtomBSM": {"detectors": [
            {"efficiency": 1, "dark_count": 0, "count_rate": 1e11, "time_resolution": 1} for _ in range(2)]}})
    _classical([alice, bob, middle], timeline)
    for node in (alice, bob):
        node.memory_array = MemoryArray(f"{node.name}.memory", timeline, num_memories=1,
                                       fidelity=1, efficiency=1, coherence_time=-1)
        node.memory_array.owner = node
        channel = QuantumChannel(f"qc.{node.name}", timeline, 0, 500)
        channel.set_ends(node, middle.name)
    _observe(timeline, [alice, bob, middle], events)
    timeline.init()
    protocols = [EntanglementGenerationA.create(node, f"{node.name}.generation", middle.name,
                  other.name, node.memory_array[0]) for node, other in ((alice, bob), (bob, alice))]
    for node, other, protocol, remote in ((alice, bob, protocols[0], protocols[1]),
                                          (bob, alice, protocols[1], protocols[0])):
        node.protocols.append(protocol)
        protocol.set_others(remote.name, other.name, [other.memory_array[0].name])
        timeline.schedule(Event(0, Process(protocol, "start", [])))
    config = _components(timeline)
    timeline.run()
    updates = [e for e in events if e["kind"] == "resource_update"]
    accepted = len(updates) == 2 and all(e["state"] == "ENTANGLED" for e in updates)
    fidelity = _overlap(timeline.quantum_manager, [alice.memory_array[0], bob.memory_array[0]]) if accepted else None
    return {"model": "generation", "seeds": seeds, "success": accepted,
            "state_fidelity": fidelity, "latency_ps": max((e["time_ps"] for e in updates), default=None),
            "output_state": _complex_array(timeline.quantum_manager.get(alice.memory_array[0].qstate_key).state)
                if accepted else None,
            "protocol_classes": [type(p).__name__ for p in protocols] + [type(middle.eg).__name__],
            "native_manager": type(timeline.quantum_manager).__name__,
            "counters": _counters(timeline, events), "components": config, "events": events}


def _teleport_trial(seeds, psi, template):
    _formalism(KET_VECTOR_FORMALISM)
    config = json.loads(json.dumps(template))
    config["stop_time"] = 201 * MILLISECOND
    for node, seed in zip(config["nodes"], seeds):
        node["seed"] = seed
    topology = DQCNetTopo(config)
    timeline, events = topology.tl, []
    nodes = topology.nodes[DQCNetTopo.DQC_NODE]
    alice = next(node for node in nodes if node.name == "alice")
    bob = next(node for node in nodes if node.name == "bob")
    all_nodes = nodes + topology.nodes[DQCNetTopo.BSM_NODE]
    _observe(timeline, all_nodes, events, resources=True)
    alice.get_component_by_name(alice.data_memo_arr_name)[0].update_state(psi)
    sender, receiver = TeleportApp(alice), TeleportApp(bob)
    sender.start(bob.name, MILLISECOND, 200 * MILLISECOND, 1, 0.01, 0)
    timeline.init()
    components = _components(timeline)
    timeline.run()
    output = np.asarray(receiver.results[0][1]) if receiver.results else None
    fidelity = float(abs(np.vdot(psi, output)) ** 2) if output is not None else None
    heralds = [e["time_ps"] for e in events if e["kind"] == "resource_update"
               and e["state"] == "ENTANGLED" and "BarretKok" in (e["protocol"] or "")]
    return {"model": "teleportation", "seeds": seeds, "input_state": _complex_array(psi),
        "output_state": _complex_array(output) if output is not None else None,
        "success": bool(receiver.results), "result_count": len(receiver.results), "state_fidelity": fidelity,
        "reservation_start_ps": MILLISECOND, "reservation_end_ps": 200 * MILLISECOND,
        "completion_time_ps": int(receiver.results[0][0]) if receiver.results else None,
        "latency_ps": int(receiver.results[0][0] - MILLISECOND) if receiver.results else None,
        "first_herald_time_ps": min(heralds) if heralds else None,
        "native_manager": type(timeline.quantum_manager).__name__,
        "protocol_class": TeleportProtocol.__name__, "topology_config": config,
        "components": components, "counters": _counters(timeline, events), "events": events}


def _memory(name, timeline, node, fidelity):
    memory = Memory(name, timeline, fidelity, 0, 1, -1, 500)
    memory.owner = node
    memory.fidelity = fidelity
    return memory


def _pair(timeline, left, right, state):
    left.entangled_memory = {"node_id": right.owner.name, "memo_id": right.name}
    right.entangled_memory = {"node_id": left.owner.name, "memo_id": left.name}
    timeline.quantum_manager.set([left.qstate_key, right.qstate_key], state)


def _purification_trial(seeds, fidelity=0.8):
    _formalism(DENSITY_MATRIX_FORMALISM)
    timeline, events = Timeline(MILLISECOND), []
    alice, bob = [_ReferenceNode(name, timeline, seed, events) for name, seed in zip(("alice", "bob"), seeds)]
    _classical([alice, bob], timeline)
    kept_a, kept_b, measured_a, measured_b = [
        _memory(name, timeline, node, fidelity) for name, node in
        (("kept_a", alice), ("kept_b", bob), ("measured_a", alice), ("measured_b", bob))]
    _pair(timeline, kept_a, kept_b, _pair_density(fidelity))
    _pair(timeline, measured_a, measured_b, _pair_density(fidelity))
    a = PurificationProtocol.create(alice, "alice.bbpssw", kept_a, measured_a)
    b = PurificationProtocol.create(bob, "bob.bbpssw", kept_b, measured_b)
    for node, other, own, remote, memories in ((alice, bob, a, b, [kept_b, measured_b]),
                                               (bob, alice, b, a, [kept_a, measured_a])):
        node.protocols.append(own)
        own.set_others(remote.name, other.name, [memory.name for memory in memories])
        timeline.schedule(Event(0, Process(own, "start", [])))
    _observe(timeline, [alice, bob], events)
    timeline.init()
    config = _components(timeline)
    timeline.run()
    success = a.meas_res == b.meas_res
    state_fidelity = _overlap(timeline.quantum_manager, [kept_a, kept_b]) if success else None
    return {"model": "bbpssw", "seeds": seeds, "input_fidelity": fidelity, "success": success,
        "measurements": [int(a.meas_res), int(b.meas_res)], "state_fidelity": state_fidelity,
        "metadata_fidelity": float(kept_a.fidelity) if success else None,
        "output_state": _complex_array(timeline.quantum_manager.get(kept_a.qstate_key).state) if success else None,
        "latency_ps": int(timeline.now()), "protocol_class": type(a).__name__,
        "native_manager": type(timeline.quantum_manager).__name__, "components": config,
        "counters": _counters(timeline, events), "events": events}


def _swapping_trial(seeds, fidelity_a=0.8, fidelity_b=0.9, success_probability=0.6):
    _formalism(DENSITY_MATRIX_FORMALISM)
    timeline, events = Timeline(MILLISECOND), []
    alice, middle, bob = [_ReferenceNode(name, timeline, seed, events)
                           for name, seed in zip(("alice", "middle", "bob"), seeds)]
    _classical([alice, middle, bob], timeline)
    left, middle_left, middle_right, right = [
        _memory(name, timeline, node, fidelity) for name, node, fidelity in
        (("left", alice, fidelity_a), ("middle_left", middle, fidelity_a),
         ("middle_right", middle, fidelity_b), ("right", bob, fidelity_b))]
    _pair(timeline, left, middle_left, _pair_density(fidelity_a))
    _pair(timeline, middle_right, right, _pair_density(fidelity_b))
    a = EntanglementSwappingA.create(middle, "middle.swap", middle_left, middle_right,
                                     success_prob=success_probability, degradation=1)
    l = EntanglementSwappingB.create(alice, "alice.swap", left)
    r = EntanglementSwappingB.create(bob, "bob.swap", right)
    for node, protocol in ((middle, a), (alice, l), (bob, r)):
        node.protocols.append(protocol)
    l.set_others(a.name, middle.name, [middle_left.name, middle_right.name])
    r.set_others(a.name, middle.name, [middle_left.name, middle_right.name])
    a.set_others(l.name, alice.name, [left.name])
    a.set_others(r.name, bob.name, [right.name])
    _observe(timeline, [alice, middle, bob], events)
    timeline.init()
    config = _components(timeline)
    timeline.schedule(Event(0, Process(a, "start", [])))
    timeline.run()
    state_fidelity = _overlap(timeline.quantum_manager, [left, right]) if a.is_success else None
    return {"model": "swapping", "seeds": seeds, "input_fidelities": [fidelity_a, fidelity_b],
        "configured_success_probability": success_probability, "configured_degradation": 1,
        "success": bool(a.is_success), "state_fidelity": state_fidelity,
        "metadata_fidelity": float(left.fidelity) if a.is_success else None,
        "output_state": _complex_array(timeline.quantum_manager.get(left.qstate_key).state)
            if a.is_success else None,
        "latency_ps": int(timeline.now()), "protocol_class": type(a).__name__,
        "native_manager": type(timeline.quantum_manager).__name__, "components": config,
        "counters": _counters(timeline, events), "events": events}


def _provenance(root):
    reviewed = ["sequence/kernel/timeline.py", "sequence/kernel/quantum_manager/ket_vector.py",
        "sequence/kernel/quantum_manager/density_matrix.py", "sequence/components/memory.py",
        "sequence/components/photon.py", "sequence/components/detector.py", "sequence/components/bsm.py",
        "sequence/components/optical_channel.py", "sequence/topology/node.py", "sequence/topology/dqc_net_topo.py",
        "sequence/entanglement_management/generation/barret_kok.py",
        "sequence/entanglement_management/generation/generation_base.py",
        "sequence/entanglement_management/purification/bbpssw_circuit.py",
        "sequence/entanglement_management/swapping/swapping_circuit.py",
        "sequence/entanglement_management/teleportation.py", "sequence/app/teleport_app.py",
        "example/demo_for_beginners/teleport_2node.json"]
    installed = Path(sequence.__file__).resolve().parent.parent
    actual_head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                                   check=True, capture_output=True, text=True, timeout=10).stdout.strip()
    ancestry = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", UPSTREAM_COMMIT, actual_head],
                              check=False, capture_output=True, timeout=10)
    if ancestry.returncode != 0:
        raise RuntimeError("Native reference HEAD must descend from the pinned official commit")
    dirty_sources = subprocess.run(["git", "-C", str(root), "diff", UPSTREAM_COMMIT, "--name-only", "--", *reviewed],
                                   check=True, capture_output=True, text=True, timeout=10).stdout.splitlines()
    if dirty_sources:
        raise RuntimeError(f"Reviewed upstream source files have local modifications: {dirty_sources}")
    # Read pinned Git blobs in one call, without extracting or modifying the checkout.
    pinned_archive = subprocess.run(["git", "-C", str(root), "archive", UPSTREAM_COMMIT, "--", *reviewed],
                                   check=True, capture_output=True, timeout=10).stdout
    with tarfile.open(fileobj=io.BytesIO(pinned_archive), mode="r:") as archive:
        pinned = {relative: archive.extractfile(relative).read() for relative in reviewed}
    hashes = []
    for relative in reviewed:
        source, loaded = root / relative, installed / relative
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        is_module = relative.startswith("sequence/")
        loaded_hash = hashlib.sha256(loaded.read_bytes()).hexdigest() if is_module else None
        source_text_hash = hashlib.sha256(source.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        pinned_text = pinned[relative].decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        pinned_text_hash = hashlib.sha256(pinned_text.encode("utf-8")).hexdigest()
        loaded_text_hash = (hashlib.sha256(loaded.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
                            if is_module else pinned_text_hash)
        hashes.append({"path": relative, "reviewed_sha256": source_hash,
                       "installed_sha256": loaded_hash, "raw_bytes_match": source_hash == loaded_hash,
                       "pinned_blob_sha256": hashlib.sha256(pinned[relative]).hexdigest(),
                       "normalized_lf_sha256": pinned_text_hash,
                       "matches": source_text_hash == loaded_text_hash == pinned_text_hash})
    if not all(row["matches"] for row in hashes):
        raise RuntimeError("Installed SeQUeNCe differs from the reviewed local checkout")
    if importlib.metadata.version("sequence") != "1.3.0":
        raise RuntimeError("Native reference requires reviewed SeQUeNCe 1.3.0")
    return {"pinned_source_commit": UPSTREAM_COMMIT, "actual_head": actual_head, "version": "1.3.0",
            "pinned_commit_is_ancestor": True,
            "reviewed_sources_clean": True,
            "source_comparison": "UTF-8 text with CRLF/LF normalized; raw byte hashes retained",
            "installed_package": str(installed / "sequence"), "reviewed_checkout": str(root),
            "timeline_source": inspect.getfile(Timeline), "source_hashes": hashes}


def _sequence_root(start=None):
    override = os.environ.get("DEQUINT_SEQUENCE_ROOT")
    if override:
        root = Path(override).expanduser().resolve()
        if not (root / "sequence/kernel/timeline.py").is_file():
            raise ValueError("DEQUINT_SEQUENCE_ROOT must name an official SeQUeNCe checkout root")
        return root
    location = Path(__file__ if start is None else start).resolve()
    for parent in (location, *location.parents):
        for candidate in (parent, parent / "SeQUeNCe"):
            if (candidate / "sequence/kernel/timeline.py").is_file():
                return candidate
    raise FileNotFoundError("Cannot locate SeQUeNCe checkout; set DEQUINT_SEQUENCE_ROOT")


def _aggregate(records, model, expected_probability, expected_fidelity):
    rows = [row for row in records if row["model"] == model]
    successes = [row for row in rows if row["success"]]
    measured = [row["state_fidelity"] for row in successes]
    conditional = float(np.mean(measured)) if measured else None
    p = len(successes) / len(rows)
    # Wilson interval: finite-trial rates are not exact analytical probabilities.
    n, z = len(rows), 1.959963984540054
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return {"trials": n, "successes": len(successes), "observed_success_fraction": p,
            "wilson_95_interval": [max(0, center - half), min(1, center + half)],
            "expected_success_probability": expected_probability,
            "conditional_state_fidelity": conditional, "expected_conditional_fidelity": expected_fidelity,
            "max_fidelity_error": max((abs(f - expected_fidelity) for f in measured), default=None),
            "mean_success_latency_s": float(np.mean([row["latency_ps"] for row in successes])) * 1e-12 if successes else None}


def run_native_reference(output_dir, seed=20261020, trials=32):
    """Run four bounded native submodels and write raw JSON/CSV plus provenance.

    trials is the number of independent attempts *per* submodel, including
    failures; teleportation attempts may internally retry generation until the
    reservation deadline. Purification/swapping use directly prepared density
    matrices, not photonic generation. Fidelity is conditional on acceptance.
    """
    for name, value in (("seed", seed), ("trials", trials)):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
            raise ValueError(f"{name} must be an integer")
    if seed < 0 or not 1 <= trials <= 256:
        raise ValueError("seed must be nonnegative and trials must be in [1, 256]")
    seed, trials = int(seed), int(trials)
    root = _sequence_root()
    provenance = _provenance(root)
    template = json.loads((root / "example/demo_for_beginners/teleport_2node.json").read_text())
    rng = np.random.default_rng(seed)
    records = []
    with _native_settings():
        for index in range(trials):
            seeds = rng.integers(0, 2**31 - 1, size=(4, 3)).tolist()
            psi = rng.normal(size=2) + 1j * rng.normal(size=2)
            psi /= np.linalg.norm(psi)
            rows = [_generation_trial(seeds[0]), _teleport_trial(seeds[1], psi, template),
                    _purification_trial(seeds[2][:2]), _swapping_trial(seeds[3])]
            for row in rows:
                row["trial"] = index
                records.append(row)
    q = 0.2 / 3
    acceptance = (0.8 + q) ** 2 + 4 * q * q
    purified = (0.8 ** 2 + q * q) / acceptance
    models = {"generation": _aggregate(records, "generation", 0.5, 1),
              "teleportation": _aggregate(records, "teleportation", None, 1),
              "bbpssw": _aggregate(records, "bbpssw", acceptance, purified),
              "swapping": _aggregate(records, "swapping", 0.6, 0.8 * 0.9 + 0.2 * 0.1 / 3)}
    fidelity_ok = all(row["max_fidelity_error"] is not None and row["max_fidelity_error"] < 1e-9
                      for row in models.values())
    summary = {"seed": seed, "trials_per_model": trials, "native_execution": True,
        "whole_mesh_validated": False, "hardware": False, "models": models,
        "conditional_fidelity_checks_passed": fidelity_ok,
        "all_models_observed_success": all(row["successes"] > 0 for row in models.values()),
        "rate_agreement_certified": False,
        "known_discrepancies": ["Native circuit swapping scalar metadata uses F_a*F_b*degradation, "
            "whereas its ideal Werner quantum-manager state includes Pauli cancellation: F_a*F_b+(1-F_a)*(1-F_b)/3."],
        "assumptions": ["native time unit picoseconds; exported seconds use 1e-12",
            "generation is one complete two-round Barrett-Kok attempt, ideal detectors/emission and zero attenuation",
            "teleportation uses official example parameters, native reservation/retries and classical correction bits",
            "input amplitudes are prepared once; never transported in classical messages",
            "BBPSSW starts from equal independent Werner density matrices, ideal operations, no output twirl applied",
            "BBPSSW metadata requires Werner twirling before another recurrence; native start rejects F<=0.5",
            "swapping prepares independent Werner matrices, configured success=0.6 and degradation=1",
            "rate estimates include failures; small-sample rate agreement is not certified",
            "photon_emissions counts native send-qubit calls, including null-encoded BK photon objects; clicks are separate",
            "standalone protocol resource recorder resets RAW memories; not a full resource-manager/network validation",
            "run serially or in isolated process; native global settings are restored on exit"]}
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, value in (("native_summary.json", summary), ("native_raw.json", records),
                             ("native_provenance.json", provenance)):
        (output_dir / filename).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    fields = ["model", "trial", "success", "state_fidelity", "metadata_fidelity", "latency_ps", "seeds"]
    with (output_dir / "native_trials.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({**row, "seeds": json.dumps(row["seeds"])} for row in records)
    return summary
