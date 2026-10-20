"""Declared parameters; prospective profiles are not validated hardware devices."""

from dataclasses import asdict, dataclass
from math import isfinite


@dataclass(frozen=True)
class ModelConfig:
    mesh_side: int = 4
    policy: str = "hh"
    placement: str = "free"
    classical: str = "wired"
    profile: str = "prospective_parametric"
    communication_memories: int = 8
    link_servers: int = 1
    pooled_servers: int = 0
    excitation_rate_hz: float = 20_000
    reset_s: float = 50e-9
    emission_efficiency: float = .75
    detector_efficiency: float = .8
    attenuation_db_per_m: float = .01
    link_length_m: float = .001
    raw_bell_fidelity: float = .99
    memory_t2_s: float = .01
    memory_cutoff_s: float = .02
    teleport_s: float = 100e-9
    teleport_pauli_error: float = .001
    gate_s: float = 50e-9
    gate_pauli_error: float = .001
    purification_rounds: int = 0
    purification_threshold: float = .8
    purification_local_s: float = 200e-9
    wired_clock_hz: float = 1e9
    wired_width_bits: int = 16
    wired_router_cycles: int = 2
    radio_rate_bps: float = 12e9
    radio_channels: int = 1
    radio_token_s: float = 2e-9
    radio_startup_s: float = 2e-9
    control_bits: int = 128
    herald_bits: int = 64
    correction_header_bits: int = 64
    packet_loss: float = 0
    classical_ack_timeout_s: float = 100e-9
    source_outage_probability: float = 0
    deadline_s: float = .01
    minimum_process_fidelity: float = .90
    quality_weight_s: float = .002
    max_attempts: int = 10_000
    max_events: int = 5_000_000

    def validate(self):
        if self.mesh_side < 2 or self.communication_memories < 1 or self.link_servers < 1 or self.pooled_servers < 0:
            raise ValueError("Invalid topology or capacity")
        if self.policy not in {"hh", "midpoint", "queue", "adaptive", "paper_midpoint"}:
            raise ValueError("Unknown routing policy")
        if self.placement not in {"free", "restored"} or self.classical not in {"wired", "radio"}:
            raise ValueError("Invalid task or network contract")
        if not 0 <= self.purification_rounds <= 2 or self.communication_memories < 2**self.purification_rounds:
            raise ValueError("Purification has insufficient memory capacity")
        for name in ["emission_efficiency", "detector_efficiency", "raw_bell_fidelity", "teleport_pauli_error",
                     "gate_pauli_error", "purification_threshold", "packet_loss", "source_outage_probability",
                     "minimum_process_fidelity"]:
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"Invalid probability: {name}")
        for name in ["excitation_rate_hz", "memory_t2_s", "memory_cutoff_s", "wired_clock_hz", "radio_rate_bps", "deadline_s"]:
            if getattr(self, name) <= 0:
                raise ValueError(f"Nonpositive time/rate: {name}")
        if self.radio_channels < 1 or self.wired_width_bits < 1 or self.max_attempts < 1:
            raise ValueError("Invalid service parameter")
        for name in ["reset_s", "teleport_s", "gate_s", "purification_local_s", "link_length_m",
                     "attenuation_db_per_m", "radio_token_s", "radio_startup_s"]:
            if getattr(self, name) < 0 or not isfinite(getattr(self, name)):
                raise ValueError(f"Invalid delay/length: {name}")
        if self.classical_ack_timeout_s < 0 or self.quality_weight_s < 0:
            raise ValueError("Invalid acknowledgment timeout")
        return self

    @property
    def attempt_s(self):
        return 2 / self.excitation_rate_hz + self.reset_s

    @property
    def generation_success(self):
        arm_transmission = 10 ** (-self.attenuation_db_per_m * self.link_length_m / 20)
        return .5 * (self.emission_efficiency * self.detector_efficiency * arm_transmission)**2 * (1 - self.source_outage_probability)

    @property
    def expected_pair_s(self):
        return self.attempt_s / self.generation_success if self.generation_success else float("inf")

    def to_dict(self):
        return asdict(self)
