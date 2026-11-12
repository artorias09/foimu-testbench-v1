"""Single-owner observed processing. Deliberately has no truth/simulator dependency."""
from collections import deque
import math
from .protocol import StreamParser
from .core import Event, ByteSpan, TimePoint
from .diagnostics import Diagnostics
from .evidence import ObservedFrame, WriteBatch, WriteItem, record_item


class LocatedParser(StreamParser):
    """Instrument legacy decisions through its discard hook and yielded packets."""
    def __init__(self, emit):
        super().__init__()
        self.cursor = 0
        self.emit = emit
        self.last_checksums = 0

    def _discard(self, count):
        if self.stats['checksum_errors'] != self.last_checksums:
            self.emit('checksum_candidate_rejected', self.cursor, self.cursor+53)
            self.last_checksums = self.stats['checksum_errors']
        if count:
            self.emit('discard', self.cursor, self.cursor+count)
        super()._discard(count)
        self.cursor += count

    def feed(self, data):
        resyncs = self.stats['resync_events']
        for packet in super().feed(data):
            start = self.cursor
            self.cursor += 53
            if self.stats['resync_events'] != resyncs:
                self.emit('resync', start, self.cursor)
                resyncs = self.stats['resync_events']
            yield packet, start, self.cursor


class SilenceWatchdogs:
    def __init__(self, timeout_ns, emit, start_ns=0):
        self.timeout = timeout_ns
        self.emit = emit
        self.last = {'byte_silence': start_ns, 'valid_frame_silence': start_ns}
        self.active = set()
        self.counts = {k: 0 for k in self.last}

    def poll(self, now):
        for name, last in self.last.items():
            deadline = last + self.timeout
            if now >= deadline and name not in self.active:
                self.active.add(name)
                self.counts[name] += 1
                self.emit(name, {'threshold_ns': self.timeout, 'deadline_ns': deadline,
                                 'detected_ns': now, 'detection_delay_ns': now-deadline})

    def arrival(self, name, now):
        self.last[name] = now
        self.active.discard(name)


class Processing:
    def __init__(self, run_id, rate_hz, timeout_ns):
        self.run_id = run_id
        self.items = []
        self.current = None
        self.refs = deque()
        self.seq = self.frames = 0
        self.offset = 0
        self.last_time = 0
        self.epoch = None
        self.parser = LocatedParser(self._parser_event)
        self.diagnostics = Diagnostics(rate_hz)
        self.watchdogs = SilenceWatchdogs(timeout_ns, self._watchdog_event)
        self.ended = False

    def _event(self, kind, domain, payload, span=None, refs=(), epoch_id=None):
        rec = self.current
        e = Event(event_id=f'processing:{self.seq}', run_id=self.run_id, producer_id='processing',
            producer_seq=self.seq, domain=domain, epistemic_status='inference' if domain=='diagnostic' else 'observed_fact',
            kind=kind, component_path='FO-IMU/Host', facet='Timing' if span is None else 'Protocolo',
            severity='info' if kind=='resync' else 'warning', time=rec.time,
            stream_id=rec.stream_id, epoch_id=rec.epoch_id if epoch_id is None else epoch_id, byte_span=span,
            observation_refs=[f'chunk:{n}' for n in refs], rule_version='counter8-reacquire-v1' if kind == 'counter_discontinuity' else 'observed-v2.1', payload=payload)
        self.seq += 1
        folder = 'diagnostics' if domain=='diagnostic' else 'observed'
        self.items.append(WriteItem(folder+'/events.jsonl', e.to_json().encode()+b'\n'))

    def _parser_event(self, kind, start, end):
        refs = [n for a,b,n in self.refs if a < end and b > start]
        # new_epoch() discards the previous connection's buffered bytes. Detection
        # time belongs to the new read, but the byte span retains its old epoch.
        self._event(kind, 'observed', {}, ByteSpan(start=start, end=end), refs, epoch_id=self.epoch)

    def _watchdog_event(self, kind, payload):
        self._event(kind, 'diagnostic', payload)

    def consume(self, chunk):
        rec = chunk.record()
        if self.ended or rec.global_offset != self.offset or rec.time.value < self.last_time:
            raise ValueError('Ordem, offset ou tempo inválido no processamento')
        self.current = rec
        self.items = []
        self.last_time = rec.time.value
        if rec.kind=='epoch':
            self.parser.new_epoch()
            self.diagnostics.new_epoch()
            self.refs.clear()
            if self.epoch is not None:
                self.diagnostics.reconnections += 1
            self.epoch = rec.epoch_id
        elif self.epoch != rec.epoch_id:
            raise ValueError('Chunk sem declaração de época')
        if chunk.data:
            self.items.append(WriteItem('observed/wire.bin', chunk.data))
        self.items.append(WriteItem('observed/chunks.jsonl', chunk.metadata+b'\n'))
        self.watchdogs.poll(rec.time.value)
        if chunk.data:
            self.watchdogs.arrival('byte_silence', rec.time.value)
            self.refs.append((self.offset, self.offset+rec.size, rec.read_seq))
            for packet, start, end in self.parser.feed(chunk.data):
                before = self.diagnostics.discontinuities
                counter = self.diagnostics.observe(packet, rec.time.value / 1e9)
                self.watchdogs.arrival('valid_frame_silence', rec.time.value)
                refs = [n for a,b,n in self.refs if a < end and b > start]
                fields, status = {}, {}
                for name, value in packet._asdict().items():
                    fields[name] = value if math.isfinite(value) else None
                    status[name] = 'finite' if math.isfinite(value) else ('nan' if math.isnan(value) else 'pos_inf' if value>0 else 'neg_inf')
                frame = ObservedFrame(frame_id=f'frame:{self.frames}',stream_id=rec.stream_id,
                    epoch_id=rec.epoch_id,counter=packet.counter,byte_span=ByteSpan(start=start,end=end),
                    chunk_refs=refs,time=rec.time,fields=fields,numeric_status=status)
                self.frames += 1
                self.items.append(WriteItem('observed/frames.jsonl', frame.to_json().encode()+b'\n'))
                if before != self.diagnostics.discontinuities:
                    self._event('counter_discontinuity', 'diagnostic',
                        {'counter': packet.counter, 'interpretation': counter.kind,
                         'delta': counter.delta, 'candidate_missing': counter.candidate_missing,
                         'cause_status': 'inconclusive'},
                        frame.byte_span, refs)
            self.offset += rec.size
            while self.refs and self.refs[0][1] <= self.parser.cursor:
                self.refs.popleft()
        if rec.kind=='end':
            self.parser.finish()
            self.ended = True
        return WriteBatch(tuple(self.items))

    def metrics(self):
        result = self.diagnostics.report(self.last_time / 1e9)
        result.pop('packets_expected')
        result.update(self.parser.stats)
        result.update(frames_accepted=self.frames, raw_bytes=self.offset,
                      byte_silence_episodes=self.watchdogs.counts['byte_silence'],
                      valid_frame_silence_episodes=self.watchdogs.counts['valid_frame_silence'],
                      definition_version='observed-v2.1', clock_id='experiment')
        return result
