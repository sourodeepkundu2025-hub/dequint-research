from itertools import permutations

import pytest

from dequint.kernel import FifoResource, Kernel
from dequint.routing import geodesic_meetings, manhattan, minimax_meeting, nodes, paper_meeting, xy_path


def test_minimax_exhaustively_and_paper_counterexamples():
    failures = 0
    for a, b in permutations(nodes(4), 2):
        meeting = minimax_meeting(a, b, 4)
        bound = (manhattan(a, b) + 1) // 2
        assert max(manhattan(a, meeting), manhattan(b, meeting)) == bound
        assert manhattan(a, meeting) + manhattan(b, meeting) == manhattan(a, b)
        old = paper_meeting(a, b)
        failures += max(manhattan(a, old), manhattan(b, old)) > bound
    assert failures == 32


def test_path_is_neighbor_connected_and_reversible():
    path = xy_path((3, 0), (0, 3))
    assert len(path) == 7
    assert all(manhattan(a, b) == 1 for a, b in zip(path, path[1:]))
    assert path[0] == (3, 0) and path[-1] == (0, 3)


def test_native_resource_contention_and_timeout_cleanup():
    kernel = Kernel(horizon_s=20)
    resource = FifoResource(kernel, "server", 1)
    completed = []

    def work(name, service, deadline):
        lease = yield resource.request(name, deadline)
        if lease is None:
            completed.append((name, "timeout", kernel.now))
            return
        yield kernel.delay(service)
        completed.append((name, "done", kernel.now))
        lease.release()

    kernel.spawn(work("first", 3, 10))
    kernel.spawn(work("expired", 1, 1))
    kernel.spawn(work("third", 2, 10))
    kernel.run()
    assert completed == [("expired", "timeout", 1.0), ("first", "done", 3.0), ("third", "done", 5.0)]
    assert resource.used == 0 and resource.waiting_units == 0
    assert resource.integral_used_s == pytest.approx(5)


def test_parallel_processes_and_failure_propagation():
    kernel = Kernel(horizon_s=10)

    def child(t):
        yield kernel.delay(t)
        return t

    def parent():
        values = yield kernel.all([kernel.spawn(child(1)), kernel.spawn(child(3))])
        return values, kernel.now

    result = kernel.spawn(parent())
    kernel.run()
    assert result.value == ([1, 3], 3.0)
