"""Version 2 contracts only. No transport, writer, GUI or simulator execution."""
from dataclasses import dataclass, field, replace
from pathlib import PurePosixPath
import re
from typing import Literal
from .schema import Model, require, unique

Number = int | float
Domain = Literal['control','truth','observed','diagnostic','validation']
ClockKind = Literal['virtual','monotonic_local','utc_catalog','unknown']
Execution = Literal['draft','validated','prepared','armed','running','stopping','finalizing','completed','cancelled','failed','aborted','interrupted_recovered']
Evaluation = Literal['not_evaluated','passed','failed','inconclusive']
Integrity = Literal['unknown','complete','partial','corrupt']
Origin = Literal['code','manual','datasheet','article','measured','synthetic','hypothesis','unknown']


def sha(value, length=64):
    require(value is None or re.fullmatch('[0-9a-f]{'+str(length)+'}',value) is not None, 'Hash hexadecimal inválido')


@dataclass(frozen=True, kw_only=True)
class ClockDefinition(Model):
    clock_id: str
    kind: ClockKind
    origin: str | None = None
    resolution_ns: int | None = None
    def validate(self):
        require(self.resolution_ns is None or self.resolution_ns>0,'resolution_ns deve ser positiva ou desconhecida')


@dataclass(frozen=True, kw_only=True)
class TimePoint(Model):
    clock_id: str
    meaning: Literal['model','physical_sample','conversion','available','gateway_read','packaging','planned_emission','transport_write','host_receive','catalog','control','unknown']
    value: int | None
    unit: Literal['ns'] = 'ns'
    uncertainty_ns: int | None = None
    def validate(self):
        require(self.uncertainty_ns is None or self.uncertainty_ns>=0,'Incerteza negativa')
        require(self.value is not None or self.uncertainty_ns is None,'Tempo desconhecido não possui incerteza numérica')


def validate_time(point, clock):
    require(point.clock_id==clock.clock_id,'clock_id não corresponde à definição')
    require(clock.kind!='utc_catalog' or point.meaning=='catalog','UTC de catálogo não mede amostragem')


def elapsed_ns(start, end, clock):
    validate_time(start,clock)
    validate_time(end,clock)
    require(clock.kind in ('virtual','monotonic_local'),'Intervalo requer clock virtual ou monotônico conhecido')
    require(start.meaning==end.meaning,'Significados temporais diferentes')
    require(start.value is not None and end.value is not None,'Tempo desconhecido')
    require(end.value>=start.value,'Regressão temporal')
    return end.value-start.value


@dataclass(frozen=True, kw_only=True)
class ByteSpan(Model):
    start: int
    end: int
    def validate(self):
        require(0<=self.start<self.end,'byte_span deve ser não vazio [inicio, fim), inicio >= 0')


@dataclass(frozen=True, kw_only=True)
class Event(Model):
    event_id: str
    run_id: str
    producer_id: str
    producer_seq: int
    domain: Domain
    epistemic_status: Literal['observed_fact','simulator_truth','inference','hypothesis','unknown']
    kind: str
    component_path: str
    facet: Literal['Aquisição','Comunicação','Timing','Validade','Protocolo','Armazenamento'] | None = None
    severity: Literal['info','warning','error','critical'] = 'info'
    time: TimePoint | None = None
    stream_id: str | None = None
    epoch_id: str | None = None
    byte_span: ByteSpan | None = None
    observation_refs: list[str] = field(default_factory=list)
    reference_ids: list[str] = field(default_factory=list)
    rule_version: str | None = None
    payload: dict[str, object] = field(default_factory=dict)
    def validate(self):
        require(self.producer_seq>=0,'producer_seq negativo')
        require(self.byte_span is None or (self.stream_id is not None and self.epoch_id is not None),'Span requer stream e época')
        require((self.domain=='truth')==(self.epistemic_status=='simulator_truth'),'Truth requer simulator_truth e vice-versa')
        require(self.domain!='observed' or self.epistemic_status in ('observed_fact','unknown'),'Observed não contém inferência ou truth')
        require(self.domain!='diagnostic' or self.epistemic_status in ('inference','hypothesis','unknown','observed_fact'),'Diagnóstico inválido')


@dataclass(frozen=True, kw_only=True)
class Fidelity(Model):
    component: str
    level: Literal['L0','L1','L2','L3','L4','L5','L6']
    bytes_contract: str | None = None
    timing: Literal['synthetic','modeled','measured','unknown'] = 'unknown'
    electrical: Literal['not_modeled','measured','unknown'] = 'not_modeled'
    sensor_model: Literal['synthetic','modeled','real','unknown'] = 'unknown'
    reference_ids: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class Reference(Model):
    reference_id: str
    kind: Origin
    title: str
    locator: str | None = None
    version: str | None = None
    sha256: str | None = None
    availability: Literal['available','unavailable','unknown'] = 'unknown'
    def validate(self):
        sha(self.sha256)


@dataclass(frozen=True, kw_only=True)
class Provenance(Model):
    provenance_id: str
    target_path: str
    origin_kind: Origin
    reference_ids: list[str] = field(default_factory=list)
    locator: str | None = None
    raw_value: object = None
    resolved_value: object = None
    unit: str | None = None
    transformation: str | None = None
    confidence: Literal['high','medium','low','unknown'] = 'unknown'
    limitations: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class ArtifactReference(Model):
    artifact_id: str
    path: str
    domain: Domain
    sha256: str | None = None
    size_bytes: int | None = None
    integrity: Integrity = 'unknown'
    def validate(self):
        p=PurePosixPath(self.path)
        require(not p.is_absolute() and '..' not in p.parts and '\\' not in self.path and ':' not in self.path and self.path!='.','Caminho deve ser relativo e portátil')
        require(self.size_bytes is None or self.size_bytes>=0,'Tamanho negativo')
        sha(self.sha256)


@dataclass(frozen=True, kw_only=True)
class CodeIdentity(Model):
    app_version: str
    python: str
    os: str
    architecture: str
    collected_at: TimePoint
    git_status: Literal['available','unavailable']
    commit: str | None = None
    tree: str | None = None
    dirty: bool | None = None
    unavailable_reason: str | None = None
    hashes: dict[str,str] = field(default_factory=dict)
    def validate(self):
        require(self.collected_at.meaning=='catalog','Identidade requer tempo de catálogo')
        for value in self.hashes.values(): sha(value)
        if self.git_status=='available':
            require(self.commit is not None and self.tree is not None and self.dirty is not None,'Git disponível requer commit, tree e dirty')
            sha(self.commit,40); sha(self.tree,40)
            require(self.unavailable_reason is None,'Git disponível não deve informar indisponibilidade')
        else:
            require(self.commit is None and self.tree is None and self.dirty is None and self.unavailable_reason is not None,'Git indisponível deve ser explícito')


@dataclass(frozen=True, kw_only=True)
class AcceptanceCriterion(Model):
    criterion_id: str
    metric: str
    domain: Literal['observed','diagnostic','truth','validation']
    operator: Literal['eq','le','ge']
    expected: Number
    unit: str
    min_evidence: int = 1
    origin: Origin = 'synthetic'
    reference_ids: list[str] = field(default_factory=list)
    def validate(self):
        require(self.min_evidence>0,'Critério requer evidência positiva')


@dataclass(frozen=True, kw_only=True)
class EvaluationResult(Model):
    criterion_id: str
    status: Evaluation
    evidence_count: int
    observed: Number | None = None
    reason: str
    observation_refs: list[str] = field(default_factory=list)
    def validate(self):
        require(self.evidence_count>=0,'Contagem de evidência negativa')
        require(self.status not in ('passed','failed') or (self.evidence_count>0 and self.observed is not None),'Conclusão requer evidência e valor observado')


def evaluate(criterion, observed, evidence_count):
    # Validate inputs through the same schema boundary; no truth is looked up.
    probe=EvaluationResult(criterion_id=criterion.criterion_id,status='inconclusive',evidence_count=evidence_count,observed=observed,reason='Evidência insuficiente')
    if observed is None or evidence_count<criterion.min_evidence:
        return probe
    ok={'eq':observed==criterion.expected,'le':observed<=criterion.expected,'ge':observed>=criterion.expected}[criterion.operator]
    return replace(probe,status='passed' if ok else 'failed',reason='Comparação explícita do critério')


TRANSITIONS = {
    'draft': {'validated','cancelled'},
    'validated': {'prepared','cancelled','failed'},
    'prepared': {'armed','cancelled','failed','aborted'},
    'armed': {'running','cancelled','failed','aborted'},
    'running': {'stopping','failed','aborted'},
    'stopping': {'finalizing','failed','aborted'},
    'finalizing': {'completed','cancelled','failed','aborted'},
    'completed': set(), 'cancelled': set(), 'failed': set(), 'aborted': set(),
    'interrupted_recovered': set(),
}


@dataclass(frozen=True, kw_only=True)
class Run(Model):
    run_id: str
    scenario_id: str
    code_identity: CodeIdentity
    clocks: list[ClockDefinition]
    fidelity: list[Fidelity]
    execution_status: Execution = 'draft'
    evaluation_status: Evaluation = 'not_evaluated'
    integrity_status: Integrity = 'unknown'
    criteria: list[AcceptanceCriterion] = field(default_factory=list)
    results: list[EvaluationResult] = field(default_factory=list)
    artifacts: list[ArtifactReference] = field(default_factory=list)
    stop_reason: str | None = None
    parent_run_id: str | None = None
    scenario_sha256: str | None = None
    seed: int | None = None
    protocol_profile: str | None = None
    metric_policy_version: str = 'legacy_v1'
    def validate(self):
        sha(self.scenario_sha256)
        require(self.seed is None or self.seed>=0,'Seed negativa')
        unique([a.artifact_id for a in self.artifacts],'artifacts')
        clocks={c.clock_id:c for c in self.clocks}
        require(self.code_identity.collected_at.clock_id in clocks,'Clock de identidade não registrado')
        validate_time(self.code_identity.collected_at,clocks[self.code_identity.collected_at.clock_id])
        unique([c.clock_id for c in self.clocks],'clocks')
        unique([c.criterion_id for c in self.criteria],'criteria')
        unique([r.criterion_id for r in self.results],'results')
        expected={c.criterion_id:c for c in self.criteria}
        for result in self.results:
            require(result.criterion_id in expected,'Resultado sem critério')
            if result.status in ('passed','failed'):
                actual=evaluate(expected[result.criterion_id],result.observed,result.evidence_count)
                require(actual.status==result.status,'Conclusão incompatível com critério/evidência')
        if self.evaluation_status=='passed':
            require(self.execution_status=='completed' and self.integrity_status=='complete','Aprovação requer execução concluída e integridade completa')
            require(bool(expected) and len(self.results)==len(expected) and all(r.status=='passed' for r in self.results),'Aprovação requer todos os critérios e evidências')
        if self.evaluation_status=='failed':
            require(any(r.status=='failed' for r in self.results),'Reprovação requer resultado reprovado')
        if self.evaluation_status=='not_evaluated':
            require(not self.results,'Resultados exigem avaliação explícita')
        if self.execution_status in ('cancelled','failed','aborted','interrupted_recovered'):
            require(self.stop_reason is not None,'Saída alternativa requer motivo')
        if self.execution_status=='interrupted_recovered':
            require(self.integrity_status!='complete','Recuperação requer integridade parcial/desconhecida')

    def transition(self, target, reason=None):
        self.__post_init__()
        require(target in TRANSITIONS[self.execution_status],f'Transição inválida: {self.execution_status} -> {target}')
        require(target!='prepared' or bool(self.clocks) and bool(self.fidelity),'Preparação requer clocks e fidelidade')
        return replace(self,execution_status=target,stop_reason=reason)

    def validate_event(self, event):
        event.__post_init__()
        require(event.run_id==self.run_id,'Evento pertence a outra Run')
        if event.time is not None:
            clocks={c.clock_id:c for c in self.clocks}
            require(event.time.clock_id in clocks,'Clock do evento não registrado')
            validate_time(event.time,clocks[event.time.clock_id])
