"""Exercise intake on the frozen synthetic checksum corpus only."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil

from foimu_testbench.observed_analysis import reanalyze_observed
from foimu_testbench.observed_input import ObservedProjection, open_observed


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True, type=Path)
    dst = parser.parse_args().out
    source = Path(__file__).resolve().parents[1] / 'tests/corpus/checksum'
    original = source / 'wire.bin'
    before = digest(original)
    size = original.stat().st_size
    meta = json.loads((source / 'metadata.json').read_bytes())
    if before != meta['sha256']['wire.bin']:
        raise ValueError('Hash de origem divergente')
    if dst.resolve().is_relative_to(source.parents[2]):
        raise ValueError('Usar workspace externo ao repositório')
    dst.mkdir(parents=True, exist_ok=False)
    for name in ('raw', 'analysis', 'divergences'):
        (dst / name).mkdir()
    manifest = dict.fromkeys(('firmware_version', 'firmware_hash', 'hardware_revision', 'baud',
                              'converter', 'duration_expected', 'physical_condition', 'orientation',
                              'operator'), 'unknown')
    manifest.update(capture_id='dry-checksum-v1', schema_version=1, received_at=datetime.now(timezone.utc).isoformat(),
                    source='tests/corpus/checksum v1', sha256=before, size_bytes=size, transport='file',
                    notes='Ensaio sintético de custódia', authorization_scope='dry-run sintético local')
    save(dst / 'capture.manifest.json', manifest)
    raw = dst / 'raw'
    for name in ('wire.bin', 'chunks.jsonl'):
        expected = meta['sha256'][name]
        if digest(source / name) != expected:
            raise ValueError('Origem inválida')
        shutil.copyfile(source / name, raw / name)
        if digest(raw / name) != expected:
            raise ValueError('Cópia inválida')
        (raw / name).chmod(0o444)
    wire = (raw / 'wire.bin').read_bytes()
    signatures = [i for i in range(len(wire)-1) if wire[i:i+2] == bytes.fromhex('a0a0')]
    with open_observed(raw, ObservedProjection.from_dict(meta['profile'])) as view, reanalyze_observed(view) as result:
        for p in result.directory.iterdir():
            target = dst / 'analysis' / p.name
            shutil.copyfile(p, target)
            if digest(target) != meta['sha256'][p.name]:
                raise ValueError('Saída canônica divergiu: ' + p.name)
    events = [json.loads(line) for line in (dst/'analysis/observed_events.jsonl').read_bytes().splitlines()]
    rejected, = [e for e in events if e['kind']=='checksum_candidate_rejected']
    span = rejected['byte_span']
    save(dst/'divergences/D-01.json', dict(divergence_id='D-01', capture_id=manifest['capture_id'],
         scope='checksum', observation='Candidato rejeitado', expected='Checksum coincide com payload',
         byte_span=[span['start'],span['end']], frame_range='unknown', classification='UNKNOWN',
         evidence=f'wire.bin SHA-256 {before}, observed_events.jsonl', impact_on_claim='Causa indeterminada',
         status='open'))
    after = digest(original)
    if after != before or digest(raw/'wire.bin') != before:
        raise ValueError('Falha de integridade final')
    save(dst/'analysis/intake.json',dict(source_before=before, source_after=after, copy_sha256=before,
         header_offsets=signatures, size_bytes=size, canonical_files_verified=4, divergences=1))


if __name__ == '__main__':
    main()
