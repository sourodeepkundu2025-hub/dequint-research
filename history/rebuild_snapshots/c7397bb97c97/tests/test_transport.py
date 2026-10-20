from dataclasses import replace

import pytest

from dequint.config import ModelConfig
from dequint.kernel import Kernel
from dequint.transport import ClassicalFabric
from dequint.workload import RandomStreams, make_workload, workload_hash


def test_frozen_workloads_are_reproducible_and_distinct_endpoints():
    a = make_workload(4, 100, 1000, 7, .01)
    assert workload_hash(a) == workload_hash(make_workload(4, 100, 1000, 7, .01))
    assert workload_hash(a) != workload_hash(make_workload(4, 100, 1000, 8, .01))
    assert all(r.source != r.destination for r in a)


@pytest.mark.parametrize("mode", ["wired", "radio"])
def test_capacity_delays_overlapping_messages(mode):
    kernel = Kernel(.01)
    config = replace(ModelConfig(), classical=mode)
    fabric = ClassicalFabric(kernel, config, RandomStreams(2), lambda *args, **kwargs: None)
    completions = []

    def work(index):
        success = yield from fabric.send((0, 0), (1, 0), 128, .001, str(index), "test")
        completions.append((success, kernel.now))

    kernel.spawn(work(0))
    kernel.spawn(work(1))
    kernel.run()
    assert all(x[0] for x in completions)
    assert completions[1][1] > completions[0][1]
    assert fabric.total_wait_s > 0
    assert all(r.used == 0 for r in fabric.wired.values())


@pytest.mark.parametrize("mode", ["wired", "radio"])
def test_total_packet_loss_has_bounded_retries(mode):
    kernel = Kernel(.01)
    config = replace(ModelConfig(), classical=mode, packet_loss=1, max_attempts=3)
    fabric = ClassicalFabric(kernel, config, RandomStreams(2), lambda *args, **kwargs: None)
    done = kernel.spawn(fabric.send((0, 0), (1, 0), 128, .001, "request", "correction"))
    kernel.run()
    assert done.value is False
    assert fabric.lost_packets == 3


@pytest.mark.parametrize("mode", ["wired", "radio"])
def test_inclusive_exact_service_deadline(mode):
    kernel = Kernel(2)
    config = replace(ModelConfig(), classical=mode, wired_clock_hz=1,
                     wired_router_cycles=0, wired_width_bits=1, radio_rate_bps=1,
                     radio_startup_s=0, radio_token_s=0, link_length_m=0)
    fabric = ClassicalFabric(kernel, config, RandomStreams(2), lambda *args, **kwargs: None)
    done = kernel.spawn(fabric.send((0, 0), (1, 0), 1, 1, "request", "boundary"))
    kernel.run()
    assert done.value is True
    assert fabric.radio_idle


def test_long_token_travel_does_not_leave_worker_beyond_horizon():
    kernel = Kernel(.001001)
    config = replace(ModelConfig(), classical="radio", radio_token_s=1)
    fabric = ClassicalFabric(kernel, config, RandomStreams(2), lambda *args, **kwargs: None)
    done = kernel.spawn(fabric.send((3, 3), (0, 0), 128, .001, "request", "token"))
    kernel.run()
    assert done.value is False
    assert fabric.radio_idle


def test_token_position_survives_expiry_at_exact_arrival():
    kernel = Kernel(10e-9)
    config = replace(ModelConfig(), classical="radio", radio_token_s=2e-9,
                     radio_startup_s=0, radio_rate_bps=1e12, link_length_m=0)
    fabric = ClassicalFabric(kernel, config, RandomStreams(2), lambda *args, **kwargs: None)
    expired = kernel.spawn(fabric.send((0, 1), (0, 0), 1, 1.999e-9, "a", "expires"))
    reachable = kernel.spawn(fabric.send((0, 2), (0, 0), 1, 5e-9, "b", "reachable"))
    kernel.run()
    assert expired.value is False
    assert reachable.value is True
    assert fabric.radio_idle
