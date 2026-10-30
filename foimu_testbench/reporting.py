"""Derived pt-BR report. Raw bytes remain primary evidence."""
import json


def report_text(run, scenario, metrics, truth, health, events=()):
    identity=run.code_identity
    lines=['# Relatório FO-IMU Testbench P2','',f'Run: `{run.run_id}`',
        f'Cenário: {scenario.name_pt_br} (`{scenario.scenario_id}`)',
        f'Perfil: `{scenario.protocol_profile}`. Fidelidade: {scenario.fidelity.level}, sinais sintéticos.',
        f'Seed: {scenario.seed}. Taxa nominal virtual: {scenario.rate.value} Hz.',
        f'Código inicial: versão {identity.app_version}, commit {identity.commit or "indisponível"}, tree {identity.tree or "indisponível"}, dirty={identity.dirty}.',
        f'Ambiente: Python {identity.python}; {identity.os}; {identity.architecture}.',
        f'Mudança de fontes detectada ao final: {run.sources_changed}.',
        f'Início UTC (ns): {run.started_at.value if run.started_at else "desconhecido"}. Fim UTC (ns): {run.ended_at.value if run.ended_at else "desconhecido"}.',
        '',f'Execução: **{run.execution_status}**. Avaliação: **{run.evaluation_status}**. Integridade: **{run.integrity_status}**.',
        f'Motivo de parada: {run.stop_reason}.','',
        '## Métricas observadas e inferidas','', '| Métrica | Valor |','|---|---:|']
    for key in ('frames_accepted','raw_bytes','packets_lost','counter_discontinuities','checksum_errors','framing_errors','resync_events',
                'byte_silence_episodes','valid_frame_silence_episodes','jitter_max_s','largest_gap_without_valid_data_s'):
        lines.append(f'| {key} | {metrics.get(key,"indisponível")} |')
    lines+=['','Perdas por counter são lacunas candidatas. Tempos são de recepção no domínio registrado, nunca de amostragem física.',
        'Estatísticas por canal e slots térmicos estão em diagnostics/metrics.json.',
        '', '## Critérios e conclusão','']
    if not run.results: lines.append('Sem critérios declarados: não avaliado. Concluir o ensaio não aprova o sistema.')
    for r in run.results:
        lines.append(f'- {r.criterion_id}: {r.status}. Valor={r.observed}. {r.reason}.')
    lines+=['','## Truth do simulador, separado de observed','',
        'Ausente nesta execução.' if truth is None else '```json\n'+json.dumps(truth,ensure_ascii=False,indent=2)+'\n```',
        '', '## Saúde do pipeline','',
        'Três threads: RX, processamento e writer. O controlador coordena o ciclo de vida.',
        'Tempo virtual e barreiras não demonstram taxa sustentada do computador nem do hardware.',
        '```json',json.dumps(health,ensure_ascii=False,indent=2),'```','',
        '## Localização de eventos','',
        'observed/events.jsonl localiza rejeições e ressincronizações por intervalo [início, fim).',
        'diagnostics/events.jsonl registra inferências e watchdogs. control/actions.jsonl registra transições e ACKs.',
        'Arquivos sem ocorrências podem estar ausentes. storage/terminal.jsonl registra resultado efetivo e falhas operacionais.',
        '', '## Artefatos e hashes','', '| Arquivo | Bytes | SHA-256 |','|---|---:|---|']
    for a in run.artifacts: lines.append(f'| {a.path} | {a.size_bytes} | {a.sha256} |')
    lines+=['','## Eventos relevantes (amostra limitada)','']
    for event in events:
        span=event.get('byte_span')
        where=f"[{span['start']}, {span['end']})" if span else 'sem intervalo de bytes'
        point=event.get('time') or {}
        lines.append(f"- {event.get('kind')}: {event.get('component_path')}; {where}; {point.get('value')} ns em {point.get('clock_id')}; {event.get('epistemic_status')}.")
    if not events: lines.append('Nenhum evento selecionado. Isso não constitui aprovação.')
    lines+=['','O hash deste relatório consta em run.json. run.json é a raiz do manifesto e não possui auto-hash.',
        '', '## Limitações e desconhecidos','',
        '- Nenhum modelo óptico, sincronismo físico, timeout por sensor ou idade física foi demonstrado.',
        '- Fletcher válido não prova validade de medição. Counter8 não revela toda perda, inclusive perdas finais.',
        '- Checkpoints usam flush/fsync de arquivos. Não há garantia de atomicidade de todo o diretório ou resistência a queda elétrica.',
        '- Integridade e hashes não autenticam o equipamento. Windows e duração prolongada ainda exigem validação própria.',
        '- Tempos em ns são representação; não implicam resolução física de 1 ns.',
        *['- '+x for x in run.limitations]]
    return '\n'.join(lines)+'\n'
