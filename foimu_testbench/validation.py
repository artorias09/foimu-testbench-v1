"""Small explicit metric registry; truth is only accessed for truth criteria."""
from dataclasses import replace
from pathlib import Path
from .core import EvaluationResult, evaluate
from .evidence import loads


REGISTRY = {
    ('observed','frames_accepted'): ('frames','frames_accepted','window'),
    ('observed','raw_bytes'): ('bytes','raw_bytes','window'),
    ('observed','checksum_errors'): ('candidates','checksum_errors','bytes'),
    ('observed','framing_errors'): ('episodes','framing_errors','bytes'),
    ('observed','resync_events'): ('events','resync_events','bytes'),
    ('diagnostic','counter_gap_candidates'): ('frames','packets_lost','frames'),
    ('diagnostic','byte_silence_episodes'): ('episodes','byte_silence_episodes','window'),
    ('diagnostic','valid_frame_silence_episodes'): ('episodes','valid_frame_silence_episodes','window'),
    ('diagnostic','jitter_max_s'): ('s','jitter_max_s','intervals'),
    ('truth','dropped'): ('frames','dropped','window'),
    ('truth','opportunities'): ('opportunities','opportunities','window'),
}


def truth_summary(root):
    path=Path(root)/'truth/summary.jsonl'
    if not path.exists(): return None
    last=None
    with path.open('rb') as f:
        for line in f: last=loads(line)
    return last


def evaluate_run(run, metrics, truth=None):
    results=[]
    for criterion in run.criteria:
        entry=REGISTRY.get((criterion.domain,criterion.metric))
        result=EvaluationResult(criterion_id=criterion.criterion_id,status='inconclusive',
                                evidence_count=0,reason='Métrica/unidade não suportada ou evidência indisponível')
        if entry and entry[0]==criterion.unit and run.integrity_status=='complete':
            _,key,denominator=entry
            source=truth if criterion.domain=='truth' else metrics
            if source is not None and (criterion.domain!='truth' or source.get('complete',False)):
                evidence={'window':1,'bytes':metrics.get('raw_bytes',0),
                          'frames':metrics.get('frames_accepted',0),'intervals':max(0,metrics.get('frames_accepted',0)-1)}[denominator]
                result=evaluate(criterion,source.get(key),evidence)
                result=replace(result,reason=f'{criterion.domain}.{criterion.metric}: {criterion.operator} {criterion.expected} {criterion.unit}; evidência={evidence} ({denominator})')
        elif run.integrity_status!='complete':
            result=replace(result,reason='Registro parcial/corrompido; não há cobertura completa para avaliação')
        results.append(result)
    status='not_evaluated'
    if results:
        if any(r.status=='failed' for r in results): status='failed'
        elif all(r.status=='passed' for r in results) and run.execution_status=='completed': status='passed'
        else: status='inconclusive'
    return replace(run,results=results,evaluation_status=status)
