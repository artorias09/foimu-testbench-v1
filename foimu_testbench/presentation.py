"""Incremental projection of P2 writer output. No simulator or truth dependency."""
from collections import deque
import math
from .evidence import loads
from .protocol import Packet

FIELDS = Packet._fields[1:]
UNITS = {**{f'ifog_{a}': '°/h' for a in 'xyz'},
         **{f'acc_{a}': 'contagens' for a in ('x','y','z','tap')},
         **{f'mems_gyro_{a}': '°/s' for a in 'xyz'},
         **{f'mems_acc_{a}': 'm/s²' for a in 'xyz'},
         **{f'temp_{i}': '°C' for i in range(8)}}
FRAME_LIMIT = 6000
EVENT_LIMIT = 500
METRICS = ('frames_accepted','packets_lost','checksum_errors','framing_errors','resync_events',
           'jitter_max_s','byte_silence_episodes','valid_frame_silence_episodes')


def series(rows, channel, rate):
    slot = int(channel[-1]) if channel.startswith('temp_') else None
    index = FIELDS.index('temperature' if slot is not None else channel)
    x, y = [], []
    previous = None
    broken = False
    for row in rows:
        ns, epoch, offset, counter, values = row
        if previous is not None:
            t, e, o, c, _ = previous
            broken |= (epoch != e or offset != o + 53 or (counter-c) % 256 != 1
                       or not 0 <= ns-t <= 2e9/rate)
        previous = row
        if slot is not None and (counter-1) % 8 != slot:
            continue
        if broken and x:
            x.append(ns/1e9)
            y.append(math.nan)
        broken = False
        x.append(ns/1e9)
        v = values[index]
        y.append(v if v is not None and math.isfinite(v) else math.nan)
    return x, y


def filtered(events, domain='', component='', severity=''):
    return [e for e in events if (not domain or e['domain'] == domain)
            and component.casefold() in e['component_path'].casefold()
            and (not severity or e['severity'] == severity)]


class View:
    def __init__(self, root, rate, confirmed=None):
        self.root = root
        self.rate = rate
        self.confirmed = confirmed
        self.positions = {}
        self.frames = deque(maxlen=FRAME_LIMIT)
        self.events = deque(maxlen=EVENT_LIMIT)
        self.metrics = dict.fromkeys(METRICS, 0)
        self.anchor = self.epoch = self.last_ns = None
        self.recovering_epoch = None
        self.backlog = 0

    def _lines(self, name):
        path = self.root / name
        if not path.is_file():
            return
        size = path.stat().st_size
        if self.confirmed is not None:
            size = min(size, self.confirmed.get(name, {}).get('size_bytes', 0))
        with path.open('rb') as f:
            f.seek(self.positions.get(name, 0))
            for _ in range(2048):
                remaining = size-f.tell()
                if remaining <= 0:
                    break
                line = f.readline(min(65537, remaining))
                if len(line) > 65536:
                    raise ValueError('Registro visual excede 64 KiB')
                if not line.endswith(b'\n'):
                    break
                yield loads(line)
                self.positions[name] = f.tell()
        self.backlog += size - self.positions.get(name, 0)

    def advance(self):
        self.backlog = 0
        for f in self._lines('observed/frames.jsonl'):
            ns, epoch, c = f['time']['value'], f['epoch_id'], f['counter']
            if epoch != self.epoch:
                self.anchor = None
            delta = (c-self.anchor) % 256 if self.anchor is not None else 1
            if 0 < delta < 128:
                self.metrics['packets_lost'] += delta-1
                self.anchor = c
            if self.last_ns is not None:
                jitter = abs((ns-self.last_ns)/1e9 - 1/self.rate)
                self.metrics['jitter_max_s'] = max(self.metrics['jitter_max_s'], jitter)
            self.epoch, self.last_ns = epoch, ns
            self.metrics['frames_accepted'] += 1
            self.frames.append([ns, epoch, f['byte_span']['start'], c, [f['fields'][k] for k in FIELDS]])
            while self.frames[0][0] < ns-60_000_000_000:
                self.frames.popleft()
        for name in ('control/actions.jsonl','observed/events.jsonl','diagnostics/events.jsonl'):
            for e in self._lines(name):
                self.events.append(e)
                kind = e['kind']
                if kind == 'checksum_candidate_rejected':
                    self.metrics['checksum_errors'] += 1
                elif kind == 'discard' and self.recovering_epoch != e['epoch_id']:
                    self.metrics['framing_errors'] += 1
                    self.recovering_epoch = e['epoch_id']
                elif kind == 'resync':
                    self.metrics['resync_events'] += 1
                    self.recovering_epoch = None
                elif kind in ('byte_silence','valid_frame_silence'):
                    self.metrics[kind+'_episodes'] += 1
