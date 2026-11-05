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


@dataclass(frozen=True)
class DetectorSpec:
    claim: DetectorClaim
    evidence_type: str
    prefix_local: bool
    version: str = '1'

    @property
    def possible_results(self):
        base = ('not_evaluated', 'unknown', 'inconclusive')
        if self.claim.status == 'observable':
            return base + ('ok', 'warning', 'failed')
        if self.claim.status == 'warning_only':
            return base + ('warning',)
        return base


def _spec(condition, detector, limit, premises, test, artifact, local=True):
    return DetectorSpec(DetectorClaim(condition, detector, 'observable', 'DIGITAL_PREDICATE',
                                     premises, limit, test), artifact, local)


REGISTRY_VERSION = 1
REGISTRY = tuple(DetectorSpec(c, 'chunks' if c.detector == 'host_receive_timing' else 'frames',
                              c.detector != 'host_receive_timing') for c in CLAIMS) + (
    _spec('contiguous_progression', 'counter8', 'delta = 1', ('locked', 'same_epoch'),
          'CounterTests.test_arbitrary_jump_and_reorder', 'frames'),
    _spec('duplicate_observed', 'counter8', 'delta = 0', ('locked', 'same_epoch'),
          'CounterTests.test_pairs', 'frames'),
    _spec('ambiguous_jump', 'counter8', '128 <= delta <= 255', ('locked', 'same_epoch'),
          'CounterTests.test_pairs', 'frames'),
    _spec('checksum_mismatch', 'fletcher16_legacy', 'computed != received, bytes [2,51)',
          ('complete_candidate', 'legacy_profile'), 'ProtocolTests.test_corrupt_then_valid', 'wire'),
    DetectorSpec(DetectorClaim('byte_corruption_00_ff_equivalent', 'fletcher16_legacy',
                 'not_observable', 'FLETCHER_MOD_255', ('payload_byte',),
                 'single substitution 00 <-> FF', 'ProtocolTests.test_checksum_known_collision_is_not_hidden'),
                 'wire', True),
    *(_spec(condition, 'host_receive_timing', 'now >= last + threshold_ns',
            ('recorded_experiment_clock', 'positive_threshold', 'recorded_poll'),
            'EvidenceTests.test_watchdogs_garbage_and_total_silence', 'chunks', False)
      for condition in ('byte_silence', 'valid_frame_silence')),
    *(_spec(condition, 'parser_framing', limit, ('legacy_profile', 'known_start_state'),
            test, 'wire') for condition, limit, test in (
                ('valid_frame', '53 bytes, header and Fletcher valid', 'ProtocolTests.test_all_split_positions'),
                ('framing_loss', 'first discard in recovery episode', 'ProtocolTests.test_wrong_header_is_framing_not_checksum'),
                ('resynchronization', 'first accepted candidate after discard', 'ProtocolTests.test_corrupt_then_valid'))),
)
