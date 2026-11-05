"""Pure observed-check contracts and deterministic manifest-based aggregation."""
from dataclasses import dataclass
from typing import Literal

from .core import ByteSpan
from .core.schema import Model, require
from .evidence import dumps
from .observability import DetectorSpec, REGISTRY

Result = Literal['not_evaluated', 'unknown', 'inconclusive', 'ok', 'warning', 'failed']
ORDER = ('ok', 'not_evaluated', 'unknown', 'warning', 'inconclusive', 'failed')


@dataclass(frozen=True, kw_only=True)
class EvidenceRef(Model):
    schema_version: Literal[1] = 1
    check_id: str
    check_version: str
    source: Literal['observed'] = 'observed'
    artifact: Literal['wire', 'frames', 'chunks']
    sample_count: int
    integrity: Literal['complete', 'partial', 'invalid']
    coverage: ByteSpan | None = None
    epoch: str | None = None
    confirmed_prefix_end: int | None = None

    def validate(self):
        require(self.sample_count >= 0, 'Contagem negativa')
        if self.confirmed_prefix_end is not None:
            require(self.confirmed_prefix_end >= 0, 'Prefixo negativo')


@dataclass(frozen=True, kw_only=True)
class CheckResult(Model):
    schema_version: Literal[1] = 1
    result: Result
    reason: str
    evidence: list[EvidenceRef]
    violation: str | None = None
    premises_met: bool = False

    def validate(self):
        if self.result in ('ok', 'warning', 'failed', 'inconclusive'):
            require(bool(self.evidence), 'Conclusão exige EvidenceRef')
        require((self.result == 'failed') == (self.violation is not None), 'Violação incompatível')
        if self.result == 'not_evaluated':
            require(not self.evidence, 'Check não executado com evidência')


@dataclass(frozen=True)
class Check:
    check_id: str
    detector: DetectorSpec
    minimum_samples: int = 1
    version: str = '1'


@dataclass(frozen=True)
class Node:
    node_id: str
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    checks: tuple[Check, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class Manifest:
    root: str
    nodes: tuple[Node, ...]
    version: str = '1'


def _reference(ref):
    span = ref.coverage
    return dict(check_id=ref.check_id, check_version=ref.check_version, source=ref.source, artifact=ref.artifact,
                integrity=ref.integrity, epoch=ref.epoch, sample_count=ref.sample_count,
                coverage=None if span is None else [span.start, span.end],
                confirmed_prefix_end=ref.confirmed_prefix_end, schema_version=1)


def _evaluate(check, value):
    spec = check.detector
    if value is None:
        return 'not_evaluated', 'MISSING_RESULT', [], None
    value.validate()
    require(value.result in spec.possible_results, 'Resultado fora do limite do detector')
    refs = []
    for ref in value.evidence:
        require((ref.check_id, ref.check_version, ref.artifact) ==
                (check.check_id, check.version, spec.evidence_type), 'Referência incompatível')
        refs.append(_reference(ref))
    if value.result in ('ok', 'failed', 'warning', 'inconclusive'):
        if not all(r.coverage is not None for r in value.evidence):
            return 'unknown', 'MISSING_COVERAGE', refs, None
        for r in value.evidence:
            if r.integrity == 'invalid' or r.sample_count == 0 or r.coverage.end <= r.coverage.start:
                return 'unknown', 'INSUFFICIENT_EVIDENCE', refs, None
            if r.integrity == 'partial' and not (
                    spec.prefix_local and r.confirmed_prefix_end is not None
                    and r.coverage.end <= r.confirmed_prefix_end):
                return 'unknown', 'UNCONFIRMED_SCOPE', refs, None
        if value.result in ('ok', 'failed') and (
                not value.premises_met or max(r.sample_count for r in value.evidence) < check.minimum_samples):
            return 'unknown', 'PREMISES_OR_COVERAGE', refs, None
    return value.result, value.reason, refs, value.violation


def aggregate(manifest, results):
    """Return EvidenceTreeCanonicalV1 bytes. Optional descendants retain their own rows."""
    nodes = {n.node_id: n for n in manifest.nodes}
    require(len(nodes) == len(manifest.nodes), 'Nó duplicado')
    seen, checks, rows = set(), set(), {}

    def visit(key):
        require(key in nodes and key not in seen, 'Nó ausente, cíclico ou compartilhado')
        seen.add(key)
        node = nodes[key]
        states, reasons, detectors = [], set(), set()
        limits, partial, evidence, details = set(node.limitations), set(), {}, []
        detectable = set()
        for child in sorted(node.required + node.optional):
            row = visit(child)
            if child in node.required and row['applicable']:
                states.append(row['result'])
                reasons.update(row['reasons'])
            limits.update(row['limitations'])
            detectable.update(row['detectable_conditions'])
            partial.update(row['partial_checks'])
            detectors.update(row['detectors'])
            for ref in row['evidence']:
                evidence[dumps(ref)] = ref
        for check in sorted(node.checks, key=lambda c: c.check_id):
            require(check.check_id not in checks and type(check.minimum_samples) is int and
                    check.minimum_samples > 0, 'Check duplicado ou mínimo inválido')
            checks.add(check.check_id)
            spec = check.detector
            claim = spec.claim
            detectors.add(claim.detector)
            status, reason, refs, violation = _evaluate(check, results.get(check.check_id))
            if claim.status == 'not_observable':
                limits.add(claim.condition)
            else:
                states.append(status)
                if claim.status == 'observable':
                    detectable.add(claim.condition)
            reasons.add(reason)
            details.append(dict(check_id=check.check_id, version=check.version, result=status,
                                reason=reason, violation=violation, detector=claim.detector,
                                condition=claim.condition, detection_limit=claim.detection_limit,
                                premises=sorted(claim.premises), minimum_samples=check.minimum_samples))
            for ref in refs:
                evidence[dumps(ref)] = ref
                if ref['integrity'] == 'partial':
                    partial.add(check.check_id)
        status = max(states, key=ORDER.index) if states else 'not_evaluated'
        # A declared blind detector contributes a limit. An empty required slot
        # without such a declaration still blocks approval.
        applicable = bool(states) or not (limits and (node.checks or node.required or node.limitations))
        row = dict(node_id=key, result=status, applicable=applicable, evidence=[evidence[k] for k in sorted(evidence)],
                   limitations=sorted(limits), undetected_conditions=len(limits - detectable),
                   detectable_conditions=sorted(detectable),
                   partial_checks=sorted(partial), detectors=sorted(detectors), reasons=sorted(reasons),
                   checks=details, required=sorted(node.required), optional=sorted(node.optional))
        rows[key] = row
        return row

    visit(manifest.root)
    require(len(seen) == len(nodes) and set(results) <= checks, 'Nó desconectado ou resultado desconhecido')
    return dumps(dict(schema='EvidenceTreeCanonicalV1', manifest_version=manifest.version,
                      root=manifest.root, nodes=[rows[k] for k in sorted(rows)]))


def _checks(detectors, *, indicators=False):
    return tuple(Check(s.claim.condition, s, 2 if s.claim.detector == 'counter8' else 1)
                 for s in REGISTRY if s.claim.detector in detectors and (s.claim.status == 'warning_only') == indicators)


SENSORS = ('IFOG X', 'IFOG Y', 'IFOG Z', 'ACC', 'MEMS', 'Temperatura')
MANIFEST_V1 = Manifest('FO-IMU', (
    Node('FO-IMU', required=('Protocolo', 'Transporte'), optional=SENSORS + ('Host',)),
    Node('Protocolo', checks=_checks(('parser_framing', 'fletcher16_legacy', 'counter8'))),
    Node('Transporte', optional=('Indicadores',), checks=_checks(('host_receive_timing',))),
    Node('Indicadores', checks=_checks(('host_receive_timing',), indicators=True)),
    Node('Host', limitations=('host_storage_health',)),
    *(Node(sensor, limitations=(sensor + '_physical_validity',)) for sensor in SENSORS),
))
