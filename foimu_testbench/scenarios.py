"""L1 schema and explicit v1 adapter; no scenario execution engine."""
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Literal
from .core.schema import Model, require, unique
from .core.contracts import AcceptanceCriterion, Fidelity, Provenance, Number

PROFILE='gateway53-fletcher16-le-v1'


@dataclass(frozen=True, kw_only=True)
class Rate(Model):
    value: Number
    unit: Literal['Hz']
    def validate(self):
        require(self.value>0,'Taxa deve ser positiva')


@dataclass(frozen=True, kw_only=True)
class Duration(Model):
    value: Number
    unit: Literal['s']
    def validate(self):
        require(self.value>=0,'Duração negativa')


@dataclass(frozen=True, kw_only=True)
class StopCondition(Model):
    kind: Literal['opportunities','duration']
    count: int | None = None
    duration: Duration | None = None
    def validate(self):
        if self.kind=='opportunities':
            require(self.count is not None and self.count>=0 and self.duration is None,'Oportunidades requer count >= 0 e sem duração')
        else:
            require(self.count is None and self.duration is not None and self.duration.value>0,'Duração requer valor positivo e sem count')


@dataclass(frozen=True, kw_only=True)
class Transport(Model):
    kind: Literal['virtual','tcp']
    host: str | None = None
    port: int | None = None
    def validate(self):
        if self.kind=='virtual':
            require(self.host is None and self.port is None,'Virtual não usa host/port')
        else:
            require(self.host is not None and self.port is not None and 1<=self.port<=65535,'TCP requer host e porta 1..65535')


@dataclass(frozen=True, kw_only=True)
class Fragmentation(Model):
    chunk_sizes: list[int]
    def validate(self):
        require(bool(self.chunk_sizes) and all(1<=x<=65536 for x in self.chunk_sizes),'Fragmentos devem estar em 1..65536')


@dataclass(frozen=True, kw_only=True)
class FaultRule(Model):
    rule_id: str
    kind: Literal['drop_every','checksum_every','byte_every','header_every','truncate_every','jitter_s']
    enabled: bool
    every: int | None = None
    jitter: Duration | None = None
    def validate(self):
        if self.kind=='jitter_s':
            require(self.every is None and self.jitter is not None,'Jitter requer duração, não every')
        else:
            require(self.jitter is None and self.every is not None and self.every>=0,'Falha periódica requer every >= 0')
            require(not self.enabled or self.every>0,'Falha habilitada requer every > 0')


@dataclass(frozen=True, kw_only=True)
class ScheduledAction(Model):
    action_id: str
    at_opportunity: int
    rule_id: str
    enabled: bool
    sequence_id: int
    def validate(self):
        require(self.at_opportunity>=0 and self.sequence_id>=0,'Índice/ordem negativos')


@dataclass(frozen=True, kw_only=True)
class DiagnosticPolicy(Model):
    counter_policy: Literal['forward_delta_lt128_v1']
    temperature_policy: Literal['firmware_previous_counter']
    stream_timeout: Duration
    def validate(self):
        require(self.stream_timeout.value>0,'Timeout deve ser positivo')


@dataclass(frozen=True, kw_only=True)
class ResourceLimits(Model):
    max_memory_bytes: int | None = None
    max_disk_bytes: int | None = None
    def validate(self):
        require(all(x is None or x>0 for x in (self.max_memory_bytes,self.max_disk_bytes)),'Limites devem ser positivos ou não definidos')


@dataclass(frozen=True, kw_only=True)
class ImportRecord(Model):
    source_schema_version: Literal[1]
    source_sha256: str
    source_path: str | None
    normalizations: list[str]
    def validate(self):
        from .core.contracts import sha
        sha(self.source_sha256)


@dataclass(frozen=True, kw_only=True)
class Scenario(Model):
    scenario_id: str
    name_pt_br: str
    protocol_profile: Literal['gateway53-fletcher16-le-v1']
    fidelity: Fidelity
    clock_mode: Literal['virtual','monotonic_local']
    rate: Rate
    stop_condition: StopCondition
    seed: int
    signals: Literal['synthetic_v1']
    transport: Transport
    fragmentation: Fragmentation
    fault_rules: list[FaultRule]
    scheduled_actions: list[ScheduledAction]
    diagnostic_policy: DiagnosticPolicy
    acceptance_criteria: list[AcceptanceCriterion]
    resource_limits: ResourceLimits
    provenance: list[Provenance]
    composition_profile: Literal['legacy_v1'] = 'legacy_v1'
    imported_from: ImportRecord | None = None
    def validate(self):
        require(self.seed>=0,'Seed negativa')
        require(self.fidelity.level=='L1' and self.fidelity.sensor_model=='synthetic' and self.fidelity.electrical=='not_modeled' and self.fidelity.bytes_contract==self.protocol_profile,'Scenario P1 suporta somente L1 sintético e contrato legado')
        require((self.clock_mode=='virtual')==(self.transport.kind=='virtual'),'Clock incompatível com transporte')
        unique([r.rule_id for r in self.fault_rules],'fault_rules')
        unique([r.kind for r in self.fault_rules],'fault kinds')
        unique([a.action_id for a in self.scheduled_actions],'actions')
        unique([a.sequence_id for a in self.scheduled_actions],'action sequence')
        unique([c.criterion_id for c in self.acceptance_criteria],'criteria')
        ids={r.rule_id for r in self.fault_rules}
        for action in self.scheduled_actions:
            require(action.rule_id in ids,'Ação referencia regra inexistente')
        for rule in self.fault_rules:
            if rule.kind=='jitter_s':
                require(rule.jitter.value<.5/self.rate.value,'Jitter deve ser menor que meio período')


def import_v1(supplied, *, scenario_id='imported-v1', source_path=None):
    from .config import validate_config
    require(type(supplied) is dict,'Config v1 deve ser objeto')
    require(type(supplied.get('schema_version',1)) is int and supplied.get('schema_version',1)==1,'schema_version v1 deve ser inteiro 1, nunca bool')
    # Canonical snapshot also rejects non-JSON objects/nonfinite values before defaults.
    from .core.schema import json_value
    json_value(supplied)
    source_hash=hashlib.sha256(json.dumps(supplied,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    cfg=validate_config(supplied)
    rules=[]
    for kind,value in cfg['faults'].items():
        rules.append(FaultRule(rule_id=kind,kind=kind,enabled=value>0,
            every=value if kind!='jitter_s' else None,
            jitter=Duration(value=value,unit='s') if kind=='jitter_s' else None))
    return Scenario(scenario_id=scenario_id,name_pt_br='Configuração v1 importada',protocol_profile=PROFILE,
        fidelity=Fidelity(component='gateway_output',level='L1',bytes_contract=PROFILE,timing='synthetic',sensor_model='synthetic'),
        clock_mode='virtual',rate=Rate(value=cfg['rate_hz'],unit='Hz'),
        stop_condition=StopCondition(kind='opportunities',count=cfg['packets']),seed=cfg['seed'],signals='synthetic_v1',
        transport=Transport(kind='virtual'),fragmentation=Fragmentation(chunk_sizes=list(cfg['chunk_sizes'])),
        fault_rules=rules,scheduled_actions=[],diagnostic_policy=DiagnosticPolicy(counter_policy='forward_delta_lt128_v1',
            temperature_policy='firmware_previous_counter',stream_timeout=Duration(value=cfg['stream_timeout_s'],unit='s')),
        acceptance_criteria=[],resource_limits=ResourceLimits(),
        provenance=[Provenance(provenance_id='v1',target_path='scenario',origin_kind='synthetic',
            transformation='Defaults v1 e unidades explícitas; não especificação física',confidence='high')],
        imported_from=ImportRecord(source_schema_version=1,source_sha256=source_hash,source_path=source_path,
            normalizations=['Defaults v1 resolvidos','Unidades Hz/s explícitas','Modo virtual selecionado; v1 não identifica transporte','Sem critérios de aprovação implícitos']))


def load_v1(path):
    from .core.schema import _pairs
    return import_v1(json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=_pairs),source_path=str(path))


def to_v1(scenario):
    """Compatibility projection, not a v2 runner. Refuses features v1 cannot represent."""
    from .config import validate_config
    scenario.__post_init__()
    require(scenario.stop_condition.kind=='opportunities' and not scenario.scheduled_actions,'v1 não representa duração/ações agendadas')
    require(scenario.transport.kind=='virtual','Projeção v1 cobre somente demo virtual')
    faults={}
    for rule in scenario.fault_rules:
        faults[rule.kind]=(rule.jitter.value if rule.kind=='jitter_s' else rule.every) if rule.enabled else 0
    return validate_config(dict(schema_version=1,protocol=scenario.protocol_profile,seed=scenario.seed,
        rate_hz=scenario.rate.value,packets=scenario.stop_condition.count,
        chunk_sizes=list(scenario.fragmentation.chunk_sizes),faults=faults,
        stream_timeout_s=scenario.diagnostic_policy.stream_timeout.value))
