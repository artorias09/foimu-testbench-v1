"""Limits of individual detectors, independent of the simulator."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class DetectorClaim:
    condition: str
    detector: str
    status: Literal['observable', 'not_observable', 'warning_only']
    reason: str
    premises: tuple[str, ...]
    detection_limit: str
    evidence: str


CLAIMS = (
    DetectorClaim('forward_counter_gap', 'counter8', 'observable', 'MODULAR_FORWARD_GAP',
                  ('same_epoch', 'locked', 'ordered_forward_assumption'),
                  '2 <= delta <= 127; candidate_missing = delta - 1', 'CounterTests.test_pairs'),
    DetectorClaim('loss_multiple_of_256', 'counter8', 'not_observable', 'COUNTER8_ALIASING',
                  ('same_epoch', 'counter_only'), 'k*256 hidden opportunities, k >= 1',
                  'CounterTests.test_alias_256'),
    DetectorClaim('ambiguous_jump_cause', 'counter8', 'not_observable', 'MULTIPLE_COMPATIBLE_CAUSES',
                  ('same_epoch', 'counter_only'), '128 <= delta <= 255',
                  'CounterTests.test_arbitrary_jump_and_reorder'),
    DetectorClaim('long_gap', 'host_receive_timing', 'warning_only', 'HOST_INTERVAL_ONLY',
                  ('preserved_timeline', 'same_epoch', 'calibrated_threshold', 'bounded_buffering'),
                  'configured silence threshold in host receive time', 'CounterTests.test_timing_separate'),
)
