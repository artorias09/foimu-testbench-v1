import math
from ..protocol import Packet
from .counter import CounterState, transition


class Moments:
    __slots__ = ("n", "mean", "m2", "minimum", "maximum", "nan", "inf", "last", "run", "max_run")

    def __init__(self):
        self.n = self.nan = self.inf = self.run = self.max_run = 0
        self.mean = self.m2 = 0.0
        self.minimum = self.maximum = self.last = None

    def add(self, value):
        if not math.isfinite(value):
            if math.isnan(value):
                self.nan += 1
            else:
                self.inf += 1
            self.last = None
            self.run = 0
            return
        self.run = self.run + 1 if self.last == value else 1
        self.max_run = max(self.max_run, self.run)
        self.last = value
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (value - self.mean)
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)

    def report(self):
        return dict(n_finite=self.n, mean=self.mean if self.n else None,
                    std_population=math.sqrt(max(0.0, self.m2 / self.n)) if self.n else None,
                    minimum=self.minimum, maximum=self.maximum, nan=self.nan, inf=self.inf,
                    max_identical_run=self.max_run)


class Diagnostics:
    def __init__(self, rate_hz, start_s=0.0, expected=None):
        self.period = 1.0 / rate_hz
        self.expected = expected
        self.start_s = start_s
        self.last_s = None
        self.counter_state = CounterState()
        self.reacquisitions = 0
        self.received = self.lost = self.discontinuities = self.duplicates = self.order_or_reset = 0
        self.stream_timeouts = self.reconnections = self.clock_regressions = 0
        self.maximum_gap = self.jitter_max = 0.0
        self.periods = Moments()
        self.sensors = {name: Moments() for name in Packet._fields[1:]}
        self.temperatures = [Moments() for _ in range(8)]
        self.sentinel_suspicions = {name: 0 for name in ("ifog_x", "ifog_y", "ifog_z", "acc")}

    def observe(self, packet, received_s):
        if not math.isfinite(received_s):
            raise ValueError("Reception timestamp must be finite")
        self.received += 1
        if self.last_s is not None:
            dt = received_s - self.last_s
            if dt < 0:
                self.clock_regressions += 1
            else:
                self.periods.add(dt)
                self.jitter_max = max(self.jitter_max, abs(dt - self.period))
                self.maximum_gap = max(self.maximum_gap, dt)
        else:
            self.maximum_gap = max(self.maximum_gap, received_s - self.start_s)
        self.last_s = received_s
        observation = transition(self.counter_state, packet.counter)
        self.counter_state = observation.state
        self.lost += observation.candidate_missing or 0
        self.duplicates += observation.kind == 'duplicate'
        self.order_or_reset += observation.kind == 'ambiguous_jump'
        self.reacquisitions += observation.kind == 'reacquired'
        self.discontinuities += observation.kind in ('duplicate', 'ambiguous_jump', 'forward_gap_candidate')
        for name, value in zip(Packet._fields[1:], packet[1:]):
            self.sensors[name].add(value)
        self.temperatures[(packet.counter - 1) % 8].add(packet.temperature)
        for name, scale in (("ifog_x", -0.9335), ("ifog_y", 0.9683), ("ifog_z", 0.2472)):
            value = getattr(packet, name)
            if any(math.isclose(value, code * scale, abs_tol=1e-5) for code in (-20, 0, 20)):
                self.sentinel_suspicions[name] += 1
        if (packet.acc_y in (304, 408, 1001) or packet.acc_z in (304, 408, 1001)
                or packet.acc_tap in (304, 408, 1001) or packet.acc_x in (3792, 3688, 3095)):
            self.sentinel_suspicions["acc"] += 1

        return observation

    @property
    def counter(self):
        return None if self.counter_state.reacquiring else self.counter_state.reference

    def new_epoch(self):
        self.counter_state = CounterState()

    def report(self, end_s):
        tail = max(0.0, end_s - (self.last_s if self.last_s is not None else self.start_s))
        return {
            "packets_expected": self.expected,
            "packets_received": self.received,
            "packets_lost": self.lost,
            "packets_lost_semantics": "candidate counter gaps within one epoch while locked; assumes ordered forward delta <128",
            "counter_rule_version": "counter8-reacquire-v1",
            "counter_ambiguous_jumps": self.order_or_reset,
            "counter_reacquisitions": self.reacquisitions,
            "counter_reacquiring": self.counter_state.reacquiring,
            "counter_discontinuities": self.discontinuities, "duplicates": self.duplicates,
            "out_of_order_or_reset": self.order_or_reset, "clock_regressions": self.clock_regressions,
            "stream_timeouts": self.stream_timeouts, "reconnections": self.reconnections,
            "timeouts_by_sensor": {name: None for name in ("ifog_x", "ifog_y", "ifog_z", "acc", "mems", "temperature")},
            "timeouts_by_sensor_reason": "Legacy wire has no unambiguous validity/timeout flags",
            "sentinel_suspicions": self.sentinel_suspicions,
            "period_s": self.periods.report(), "jitter_max_s": self.jitter_max,
            "largest_gap_without_valid_data_s": max(self.maximum_gap, tail),
            "latency_mean_s": None, "latency_max_s": None,
            "latency_reason": "No source timestamp on legacy wire; physical sample latency unknown",
            "sensors": {key: value.report() for key, value in self.sensors.items()},
            "temperature_slots": {str(i): value.report() for i, value in enumerate(self.temperatures)},
            "temperature_policy": "(counter-1)%8, valid for complete steady-state cycles of supplied source"
        }
