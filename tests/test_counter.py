import unittest

from foimu_testbench.diagnostics import Diagnostics
from foimu_testbench.simulator import synthetic_packet


class CounterTests(unittest.TestCase):
    def observe(self, values):
        diag = Diagnostics(100)
        packet = synthetic_packet(0, 100)
        for i, value in enumerate(values):
            diag.observe(packet._replace(counter=value), i / 100)
        return diag

    def test_pairs(self):
        # before, current, delta, candidate, duplicate, ambiguity, after
        rows = [(0, 1, 1, 0, 0, 0, 1), (255, 0, 1, 0, 0, 0, 0),
                (10, 10, 0, 0, 1, 0, 10), (10, 11, 1, 0, 0, 0, 11),
                (10, 12, 2, 1, 0, 0, 12), (10, 137, 127, 126, 0, 0, 137),
                (10, 138, 128, 0, 0, 1, None), (10, 139, 129, 0, 0, 1, None)]
        for before, current, delta, lost, duplicate, ambiguity, after in rows:
            with self.subTest(current=current):
                self.assertEqual(self.observe([before]).counter, before)
                self.assertEqual((current - before) % 256, delta)
                d = self.observe([before, current])
                self.assertEqual((d.lost, d.duplicates, d.order_or_reset, d.counter),
                                 (lost, duplicate, ambiguity, after))

    def test_stale_sequence(self):
        d = self.observe([*range(10), *range(200, 240)])
        self.assertEqual((d.received, d.discontinuities, d.order_or_reset, d.counter, d.lost),
                         (50, 1, 1, 239, 0))

    def test_arbitrary_jump_and_reorder(self):
        from foimu_testbench.diagnostics.counter import CounterState, transition
        for values, expected in [
            ([0, 1, 2, 3, 4], ['initial'] + ['contiguous'] * 4),
            ([253, 254, 255, 0, 1], ['initial'] + ['contiguous'] * 4),
            ([10, 10, 11], ['initial', 'duplicate', 'contiguous']),
            ([9, 200, 201, 202], ['initial', 'ambiguous_jump', 'reacquired', 'contiguous']),
            ([10, 11, 12, 11, 13, 14], ['initial', 'contiguous', 'contiguous', 'ambiguous_jump',
                                          'pending', 'reacquired'])]:
            state = CounterState()
            for c, kind in zip(values, expected):
                o = transition(state, c)
                self.assertEqual(o.kind, kind)
                self.assertEqual(o.state.reacquiring, kind in ('pending', 'ambiguous_jump'))
                state = o.state

    def test_epoch_reset(self):
        d = self.observe(range(31))
        d.new_epoch()
        packet = synthetic_packet(0, 100)
        for c in range(200, 221):
            d.observe(packet._replace(counter=c), c/100)
        self.assertEqual((d.lost, d.order_or_reset, d.counter), (0, 0, 220))

    def test_alias_256(self):
        from foimu_testbench.observability import CLAIMS
        baseline = self.observe([10, 11])
        for k in (1, 2, 17):
            aliased = self.observe([10, (10 + 1 + 256*k) % 256])
            self.assertEqual(baseline.report(.1), aliased.report(.1))
        claim = next(c for c in CLAIMS if c.condition == 'loss_multiple_of_256')
        self.assertEqual((claim.detector, claim.status, claim.reason),
                         ('counter8', 'not_observable', 'COUNTER8_ALIASING'))

    def test_timing_separate(self):
        packet = synthetic_packet(0, 100)
        for last_time in (.01, 10.0):
            d = Diagnostics(100)
            d.observe(packet._replace(counter=9), 0)
            o = d.observe(packet._replace(counter=200), last_time)
            self.assertEqual((o.kind, o.candidate_missing, d.lost), ('ambiguous_jump', None, 0))
            self.assertEqual(d.maximum_gap, last_time)

    def test_seeded_transitions(self):
        import random
        from foimu_testbench.diagnostics.counter import CounterState, transition
        for seed in range(100):
            r = random.Random(seed)
            state = CounterState()
            prev = None
            pending = False
            for _ in range(256):
                if r.randrange(25) == 0:
                    state, prev, pending = CounterState(), None, False
                current = ((prev or 0) + r.choice([0, 1, 1, 2, 127, 128, 129, 255, r.randrange(256)])) % 256
                o = transition(state, current)
                delta = None if prev is None else (current - prev) % 256
                self.assertEqual((o.previous, o.delta), (prev, delta))
                gap = not pending and delta in range(2, 128)
                self.assertEqual(o.candidate_missing, delta - 1 if gap else None)
                if pending:
                    self.assertEqual(o.kind, 'reacquired' if delta == 1 else 'pending')
                pending = (pending and delta != 1) or (not pending and delta in range(128, 256))
                self.assertEqual(o.state.reacquiring, pending)
                state, prev = o.state, current

    def test_view_diagnostic_equivalence(self):
        from unittest.mock import patch
        from foimu_testbench.presentation import View, FIELDS
        view = View(None, 100)
        d = Diagnostics(100)
        packet = synthetic_packet(0, 100)
        seq = 0
        for epoch, values in enumerate(([9, 200, 201, 203], [255, 0, 2, 2, 150, 151, 154])):
            d.new_epoch()
            for c in values:
                record = dict(time={'value': seq}, epoch_id=str(epoch), counter=c,
                              byte_span={'start': 53*seq}, fields=dict.fromkeys(FIELDS, 0))
                with patch.object(view, '_lines', side_effect=lambda p: [record] if p == 'observed/frames.jsonl' else []):
                    view.advance()
                d.observe(packet._replace(counter=c), seq / 1e9)
                self.assertEqual(view.metrics['packets_lost'], d.lost)
                self.assertEqual(view.counter_state, d.counter_state)
                seq += 1
