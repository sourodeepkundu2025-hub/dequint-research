"""Frozen, policy-independent arrivals and stable component random streams."""

import hashlib
import json
import random
from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class Request:
    request_id: int
    source: tuple[int, int]
    destination: tuple[int, int]
    arrival_s: float
    deadline_s: float

    def to_dict(self):
        return asdict(self)


def make_workload(side, requests, arrival_rate, seed, deadline_s):
    if side < 2 or requests < 1 or arrival_rate <= 0 or deadline_s <= 0:
        raise ValueError("Invalid workload parameters")
    rng = np.random.default_rng(np.random.SeedSequence([seed, 161803]))
    arrivals = np.cumsum(rng.exponential(1 / arrival_rate, requests))
    output = []
    for index, arrival in enumerate(arrivals):
        first = int(rng.integers(side**2))
        second = int(rng.integers(side**2 - 1))
        second += second >= first
        output.append(Request(index, divmod(first, side), divmod(second, side), float(arrival), float(arrival + deadline_s)))
    return output


def workload_hash(requests):
    data = json.dumps([r.to_dict() for r in requests], sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()


class RandomStreams:
    def __init__(self, seed):
        self.seed = seed
        self.streams = {}

    def random(self, *key):
        if key not in self.streams:
            data = json.dumps([self.seed, key], sort_keys=True).encode()
            derived = int.from_bytes(hashlib.sha256(data).digest()[:16], "big")
            self.streams[key] = random.Random(derived)
        return self.streams[key].random()
