"""L1 source and truth ledger. Truth sink is separate from read() output."""
from dataclasses import dataclass
import hashlib
import math
from .protocol import encode
from .simulator import synthetic_packet, Fragmenter
from .fault_injection import Injector
from .config import validate_config
from .core import Event, TimePoint
from .evidence import WriteBatch, WriteItem, record_item
from .scenarios import Scenario


@dataclass(frozen=True, slots=True)
class ReadResult:
    data: bytes
    ns: int
    kind: str = 'chunk'
    epoch: str = '0'
    origin: str = 'virtual'


class VirtualSource:
    def __init__(self, scenario_json, run_id, truth_sink, *, record_emissions=True):
        self.scenario = Scenario.from_json(scenario_json)
        self.run_id = run_id
        self.sink = truth_sink
        self.record_emissions = record_emissions
        self.seq = 0
        self.count = 0
        self.closed = False
        self.end_ns = 0
        self.iterator = self._generate()

    def _truth(self, kind, index, ns, payload, path='truth/faults.jsonl'):
        event = Event(event_id=f'source:{self.seq}', run_id=self.run_id, producer_id='source',
            producer_seq=self.seq, domain='truth', epistemic_status='simulator_truth', kind=kind,
            component_path='FO-IMU/Transporte', time=TimePoint(clock_id='experiment',meaning='model',value=ns),
            rule_version='legacy_v1', payload=dict(opportunity=index, **payload))
        self.seq += 1
        self.sink(WriteBatch((WriteItem(path, event.to_json().encode()+b'\n'),)))

    def _generate(self):
        s = self.scenario
        rate = s.rate.value
        count = s.stop_condition.count
        if count is None:
            # Include opportunities whose nominal delivery is within the duration.
            from decimal import Decimal, ROUND_FLOOR
            count = int((Decimal(str(s.stop_condition.duration.value))*Decimal(str(rate))).to_integral_value(rounding=ROUND_FLOOR))
        cfg = validate_config({})['faults']
        rules = {r.kind:r for r in s.fault_rules}
        for r in rules.values():
            cfg[r.kind] = (r.jitter.value if r.kind=='jitter_s' else r.every) if r.enabled else 0
        injector = Injector(cfg, s.seed)
        fragmenter = Fragmenter(s.fragmentation.chunk_sizes)
        actions = iter(sorted(s.scheduled_actions,key=lambda a:(a.at_opportunity,a.sequence_id)))
        next_action = next(actions, None)
        order = ('jitter_s','drop_every','checksum_every','byte_every','header_every','truncate_every')
        for i in range(count):
            while next_action is not None and next_action.at_opportunity == i:
                rule = next(r for r in rules.values() if r.rule_id==next_action.rule_id)
                cfg[rule.kind] = (rule.jitter.value if rule.kind=='jitter_s' else rule.every) if next_action.enabled else 0
                self._truth('scheduled_action_applied', i, round(i/rate*1e9), next_action.to_dict())
                next_action = next(actions, None)
            frame = encode(synthetic_packet(i,rate))
            due = (i+1)/rate
            try:
                data, delivery = injector.apply(i,frame,due)
            except Exception as exc:
                self._truth('injector_error',i,round(due*1e9),{'result':'error','error':str(exc)})
                raise
            self.count += 1
            self.end_ns = round(delivery*1e9)
            previous = frame
            dropped = False
            for position, name in enumerate(order):
                amount = cfg[name]
                hit = amount > 0 and (name=='jitter_s' or (i+1)%amount==0)
                if not hit:
                    continue
                result = 'suppressed' if dropped else 'applied'
                before = hashlib.sha256(previous).hexdigest()
                if not dropped:
                    b = bytearray(previous)
                    if name=='drop_every': b.clear(); dropped=True
                    elif name=='checksum_every': b[51] ^= 1
                    elif name=='byte_every': b[7] ^= 1
                    elif name=='header_every': b[0] ^= 1
                    elif name=='truncate_every': del b[20:]
                    previous = bytes(b)
                self._truth('fault_application', i, self.end_ns,
                    {'rule_id':rules[name].rule_id,'type':name,'order':position,'result':result,
                     'parameters':{'value':amount,'unit':'s' if name=='jitter_s' else 'opportunities'},
                     'before_sha256':before,'after_sha256':hashlib.sha256(previous).hexdigest(),
                     'planned_s':due,'delivery_s':delivery})
            if previous != data:
                raise RuntimeError('Ledger divergiu do injetor legado')
            if self.record_emissions:
                self.sink(WriteBatch((record_item('truth/emissions.jsonl',
                    dict(schema_version=2, opportunity=i, emission_id=f'emission:{i}', model_profile='synthetic_v1',
                         model_time_ns=round(i/rate*1e9), planned_ns=round(due*1e9), delivery_ns=self.end_ns,
                         before_sha256=hashlib.sha256(frame).hexdigest(), after_sha256=hashlib.sha256(data).hexdigest(),
                         size=len(data), interpretation='Bytes oferecidos ao transporte virtual, não aceite pelo parser')),)))
            if data:
                for fragment in fragmenter.split(data):
                    yield ReadResult(fragment,self.end_ns)
            else:
                yield ReadResult(b'', self.end_ns, 'tick')
        while next_action is not None:
            self._truth('scheduled_action_not_reached',count,self.end_ns,
                        dict(action_id=next_action.action_id,result='not_reached'))
            next_action = next(actions,None)
        self.end_ns = max(self.end_ns, round(count/rate*1e9))
        if s.stop_condition.kind=='duration':
            self.end_ns = max(self.end_ns,round(s.stop_condition.duration.value*1e9))
        yield ReadResult(b'', self.end_ns, 'end')

    def read(self):
        return None if self.closed else next(self.iterator, None)

    def close(self):
        self.closed = True


class IterableSource:
    """Test/replay adapter: only observed bytes and clock values, no truth lookup."""
    def __init__(self, readings):
        self.readings = iter(readings)
        self.closed = False

    def read(self):
        return None if self.closed else next(self.readings, None)

    def close(self):
        self.closed = True
