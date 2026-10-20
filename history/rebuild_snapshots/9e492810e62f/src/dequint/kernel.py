"""Small coroutine/resource adapter on the native SeQUeNCe event kernel."""

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

from sequence.kernel.event import Event
from sequence.kernel.process import Process
from sequence.kernel.timeline import Timeline


PS_PER_SECOND = 10**12


class Signal:
    def __init__(self, kernel):
        self.kernel = kernel
        self.done = False
        self.value = None
        self.callbacks = []

    def succeed(self, value=None):
        if self.done:
            return False
        self.done = True
        self.value = value
        callbacks, self.callbacks = self.callbacks, []
        for callback in callbacks:
            self.kernel.call_at(self.kernel.now, callback, value)
        return True

    def then(self, callback):
        if self.done:
            self.kernel.call_at(self.kernel.now, callback, self.value)
        else:
            self.callbacks.append(callback)


class _Dispatcher:
    def __init__(self, kernel):
        self.kernel = kernel

    def dispatch(self, callback, args):
        self.kernel.executed += 1
        if self.kernel.executed > self.kernel.max_events:
            raise RuntimeError("Configured simulation event bound exceeded")
        callback(*args)


class Kernel:
    def __init__(self, horizon_s=10, max_events=5_000_000):
        self.timeline = Timeline(stop_time=round(horizon_s * PS_PER_SECOND) + 1,
                                 formalism="density_matrix")
        self.dispatcher = _Dispatcher(self)
        self.sequence = 0
        self.executed = 0
        self.max_events = max_events
        self.errors = []

    @property
    def now(self):
        return self.timeline.now() / PS_PER_SECOND

    def call_at(self, time_s, callback: Callable, *args):
        tick = max(self.timeline.now(), round(time_s * PS_PER_SECOND))
        self.sequence += 1
        event = Event(tick, Process(self.dispatcher, "dispatch", [callback, args]),
                      priority=self.sequence)
        self.timeline.schedule(event)
        return event

    def delay(self, duration_s):
        if duration_s < 0:
            raise ValueError("Negative delay")
        signal = Signal(self)
        duration_ps = max(1, round(duration_s * PS_PER_SECOND)) if duration_s else 0
        self.call_at(self.now + duration_ps / PS_PER_SECOND, signal.succeed)
        return signal

    def spawn(self, generator):
        task = Task(self, generator)
        self.call_at(self.now, task.advance, None)
        return task.done

    def all(self, signals):
        combined = Signal(self)
        signals = list(signals)
        if not signals:
            combined.succeed([])
            return combined
        results = [None] * len(signals)
        remaining = {"count": len(signals)}

        def finish(index, value):
            results[index] = value
            remaining["count"] -= 1
            if remaining["count"] == 0:
                combined.succeed(results)

        for index, signal in enumerate(signals):
            signal.then(lambda value, index=index: finish(index, value))
        return combined

    def run(self):
        self.timeline.init()
        self.timeline.run()
        if self.errors:
            raise RuntimeError("Simulation process failed") from self.errors[0]


class Task:
    def __init__(self, kernel, generator):
        self.kernel = kernel
        self.generator = generator
        self.done = Signal(kernel)

    def advance(self, value):
        try:
            waiting = self.generator.send(value)
            if not isinstance(waiting, Signal):
                raise TypeError("Simulation processes must yield a Signal")
            waiting.then(self.advance)
        except StopIteration as completed:
            self.done.succeed(completed.value)
        except BaseException as error:
            self.kernel.errors.append(error)
            self.done.succeed(error)


@dataclass
class Lease:
    resource: Any
    owner: str
    amount: int
    acquired_at: float
    released: bool = False

    def release(self):
        self.resource.release(self)


class FifoResource:
    """Capacity service with FIFO admission and cancellable deadline requests."""

    def __init__(self, kernel, name, capacity=1):
        if capacity < 1:
            raise ValueError("Resource capacity must be positive")
        self.kernel, self.name, self.capacity = kernel, name, capacity
        self.used = 0
        self.queue = deque()
        self.peak_used = 0
        self.integral_used_s = 0.0
        self.last_change_s = 0.0

    def _account(self):
        self.integral_used_s += self.used * (self.kernel.now - self.last_change_s)
        self.last_change_s = self.kernel.now

    def request(self, owner, deadline_s, amount=1):
        if not 1 <= amount <= self.capacity:
            raise ValueError("Invalid resource request size")
        signal = Signal(self.kernel)
        item = {"owner": owner, "amount": amount, "signal": signal, "active": True}
        if deadline_s <= self.kernel.now:
            signal.succeed(None)
            return signal
        self.queue.append(item)
        self.kernel.call_at(deadline_s, self._expire, item)
        self._admit()
        return signal

    def _expire(self, item):
        if item["active"]:
            item["active"] = False
            item["signal"].succeed(None)
            self._admit()

    def _admit(self):
        while self.queue:
            item = self.queue[0]
            if not item["active"]:
                self.queue.popleft()
                continue
            if self.used + item["amount"] > self.capacity:
                break
            self.queue.popleft()
            item["active"] = False
            self._account()
            self.used += item["amount"]
            self.peak_used = max(self.peak_used, self.used)
            item["signal"].succeed(Lease(self, item["owner"], item["amount"], self.kernel.now))

    def release(self, lease):
        if lease.resource is not self or lease.released:
            raise RuntimeError("Invalid or duplicate resource release")
        self._account()
        self.used -= lease.amount
        lease.released = True
        if self.used < 0:
            raise RuntimeError("Resource accounting underflow")
        self._admit()

    @property
    def waiting_units(self):
        return sum(item["amount"] for item in self.queue if item["active"])
