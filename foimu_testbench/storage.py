"""Single writer, confirmed prefixes, read-only recovery. No power-loss guarantee."""
from dataclasses import replace
from pathlib import Path
import hashlib
import os
from .core import Run, ArtifactReference
from .core.schema import require
from .scenarios import Scenario
from .evidence import dumps, loads, ChunkRecord, ObservedChunk


def digest_file(path, length=None):
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        remaining = length
        while remaining is None or remaining > 0:
            data = f.read(65536 if remaining is None else min(65536,remaining))
            if not data:
                break
            digest.update(data)
            if remaining is not None:
                remaining -= len(data)
        require(remaining in (None,0), 'Arquivo menor que prefixo confirmado')
    return digest.hexdigest()


def safe_path(root, name):
    ArtifactReference(artifact_id=name,path=name,domain='observed')
    path = root/name
    require(path.resolve().is_relative_to(root.resolve()), 'Artefato fora da Run')
    return path


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary = path.with_name(path.name+'.tmp')
    with temporary.open('wb') as f:
        f.write(dumps(value)+b'\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary,path)


class RunWriter:
    def __init__(self, out, run, scenario, *, checkpoint_every=128, max_disk_bytes=None, hook=None):
        require(type(checkpoint_every) is int and checkpoint_every>0,'Checkpoint requer intervalo inteiro positivo')
        self.root = Path(out)
        self.root.mkdir(parents=True, exist_ok=False)
        self.files = {}
        self.hashes = {}
        self.sizes = {}
        self.generation = self.batches = 0
        self.checkpoint_every = checkpoint_every
        self.max_disk_bytes = max_disk_bytes
        self.hook = hook
        self.closed = False
        self.confirmed = {}
        atomic_json(self.root/'run.json', run.to_dict())
        atomic_json(self.root/'scenario.resolved.json', scenario.to_dict())
        try:
            self.checkpoint()
        except BaseException:
            self.close(checkpoint=False)
            raise

    def _append(self, path, body):
        if self.max_disk_bytes is not None and sum(self.sizes.values())+len(body)>self.max_disk_bytes:
            raise OSError(28, 'Orçamento de disco excedido')
        if self.hook:
            self.hook(path,body)
        if path not in self.files:
            target = safe_path(self.root,path)
            target.parent.mkdir(parents=True,exist_ok=True)
            self.files[path] = target.open('ab',buffering=0)
            self.sizes[path] = 0
            self.hashes[path] = hashlib.sha256()
        written = self.files[path].write(body)
        if written != len(body):
            raise OSError('Escrita parcial; cauda preservada')
        self.hashes[path].update(body)
        self.sizes[path] += written

    def append(self, batch):
        require(not self.closed,'Writer fechado')
        for item in batch.items:
            self._append(item.path,item.body)
        self.batches += 1
        if self.batches%self.checkpoint_every==0:
            self.checkpoint()

    def checkpoint(self):
        entries = {}
        for name,f in self.files.items():
            f.flush()
            os.fsync(f.fileno())
            if name!='storage/checkpoints.jsonl':
                entries[name] = dict(size_bytes=self.sizes[name],sha256=self.hashes[name].hexdigest())
        config = self.root/'scenario.resolved.json'
        entries['scenario.resolved.json'] = dict(size_bytes=config.stat().st_size,sha256=digest_file(config))
        entry = dict(schema_version=2,generation=self.generation,artifacts=entries,
                     durability='flush_fsync_files; directory metadata and power loss not guaranteed')
        self._append('storage/checkpoints.jsonl',dumps(entry)+b'\n')
        f = self.files['storage/checkpoints.jsonl']
        f.flush(); os.fsync(f.fileno())
        self.confirmed = entries
        self.generation += 1

    def close(self, checkpoint=True):
        error = None
        try:
            if checkpoint:
                self.checkpoint()
        except BaseException as exc:
            error = exc
        for f in self.files.values():
            try: f.close()
            except BaseException as exc:
                if error is None: error = exc
        self.closed = True
        if error is not None: raise error

    def manifest(self, integrity):
        result = []
        for p in sorted(self.root.rglob('*')):
            if not p.is_file() or p.name=='run.json' or p.name.endswith('.tmp'):
                continue
            path = p.relative_to(self.root).as_posix()
            folder = path.split('/')[0]
            domain = {'truth':'truth','observed':'observed','diagnostics':'diagnostic','validation':'validation'}.get(folder,'control')
            result.append(ArtifactReference(artifact_id=path,path=path,domain=domain,
                sha256=digest_file(p),size_bytes=p.stat().st_size,integrity=integrity))
        return result


class RunReader:
    def __init__(self, path, *, strict=True):
        self.root = Path(path)
        self.run = Run.from_json((self.root/'run.json').read_bytes())
        self.scenario = Scenario.from_json((self.root/'scenario.resolved.json').read_bytes())
        self.issues = []
        self.confirmed = {}
        self.tails = {}
        terminal = self.run.execution_status in ('completed','cancelled','failed','aborted')
        if terminal:
            self._verify_manifest()
        self._recover_prefix()
        if not terminal:
            self.issues.append('Marcador terminal ausente: execução interrompida')
            self.run = replace(self.run,execution_status='interrupted_recovered',integrity_status='partial',
                evaluation_status='inconclusive' if self.run.criteria else 'not_evaluated',results=[],
                stop_reason='Reabertura de execução sem finalização; originais preservados')
        try:
            self.validate_timeline()
        except (ValueError,OSError) as exc:
            self.issues.append(str(exc))
        if terminal and not self.issues and self.run.integrity_status=='complete':
            self.tails = {}  # The final verified manifest confirms derived artifacts too.
        if self.issues and terminal:
            self.run = replace(self.run,integrity_status='corrupt',
                evaluation_status='inconclusive' if self.run.criteria else 'not_evaluated',results=[])
        if strict:
            require(not self.issues and self.run.integrity_status=='complete',
                    'Run não permite replay fiel: '+'; '.join(self.issues or [self.run.integrity_status]))

    def _verify_manifest(self):
        expected = {a.path for a in self.run.artifacts}
        actual = {p.relative_to(self.root).as_posix() for p in self.root.rglob('*') if p.is_file() and p.name!='run.json'}
        if actual != expected:
            self.issues.append('Manifesto não corresponde aos artefatos presentes')
        for a in self.run.artifacts:
            p = safe_path(self.root,a.path)
            if not p.exists() or p.stat().st_size!=a.size_bytes or digest_file(p)!=a.sha256:
                self.issues.append('Hash/tamanho inválido: '+a.path)
        if self.run.scenario_sha256 != hashlib.sha256(self.scenario.to_json().encode()).hexdigest():
            self.issues.append('Scenario diferente da identidade inicial')

    def _recover_prefix(self):
        path = self.root/'storage/checkpoints.jsonl'
        if not path.exists():
            self.issues.append('Nenhum checkpoint disponível')
            return
        # Scan syntax once, then verify the newest checkpoint. On corruption walk
        # older checkpoint positions, not O(n²) hashing on every healthy reopen.
        positions = []
        with path.open('rb') as f:
            generation = -1
            while True:
                position = f.tell()
                line = f.readline()
                if not line: break
                try:
                    require(line.endswith(b'\n'),'Cauda de checkpoint parcial')
                    row = loads(line)
                    require(set(row)=={'schema_version','generation','artifacts','durability'},'Campos de checkpoint inválidos')
                    require(type(row['schema_version']) is int and row['schema_version']==2,'Schema de checkpoint inválido')
                    require(type(row['generation']) is int and row['generation']==generation+1,'Geração de checkpoint inválida')
                    generation += 1
                    positions.append(position)
                except (ValueError,KeyError):
                    self.issues.append('Checkpoint inválido ou cauda parcial preservada')
                    break
            for position in reversed(positions):
                f.seek(position)
                row = loads(f.readline())
                try:
                    for name,a in row['artifacts'].items():
                        p = safe_path(self.root,name)
                        require(type(a['size_bytes']) is int and a['size_bytes']>=0,'Prefixo inválido')
                        require(digest_file(p,a['size_bytes'])==a['sha256'],'Hash de prefixo inválido: '+name)
                    self.confirmed = row['artifacts']
                    break
                except (ValueError,KeyError,OSError):
                    if 'Prefixo de checkpoint corrompido' not in self.issues:
                        self.issues.append('Prefixo de checkpoint corrompido')
        for p in self.root.rglob('*'):
            if p.is_file() and p.name not in ('run.json','scenario.resolved.json') and p!=path:
                name = p.relative_to(self.root).as_posix()
                start = self.confirmed.get(name,{}).get('size_bytes',0)
                if p.stat().st_size>start:
                    self.tails[name] = dict(confirmed_bytes=start, present_bytes=p.stat().st_size)

    def timeline(self):
        path = self.root/'observed/chunks.jsonl'
        if not path.exists():
            raise ValueError('Índice de chunks ausente')
        with path.open('rb') as f:
            for line in f:
                require(line.endswith(b'\n'),'Cauda de chunks parcial')
                yield ChunkRecord.from_json(line)

    def validate_timeline(self):
        offset = seq = 0
        last_ns = None
        epoch = None
        epochs = set()
        end = False
        wire_path = self.root/'observed/wire.bin'
        length = wire_path.stat().st_size if wire_path.exists() else 0
        for row in self.timeline():
            require(not end,'Registro após fim')
            require(row.stream_id=='wire' and row.time.clock_id=='experiment','Stream/clock desconhecido')
            require(row.read_seq==seq and row.global_offset==offset,'Offset/ordem inválido')
            require(last_ns is None or row.time.value>=last_ns,'Regressão temporal')
            last_ns = row.time.value
            seq += 1
            if row.kind=='epoch':
                require(row.epoch_id not in epochs,'Época repetida')
                epochs.add(row.epoch_id); epoch=row.epoch_id
            else:
                require(epoch is not None and row.epoch_id==epoch,'Época ausente/inválida')
            offset += row.size
            require(offset<=length,'Chunk ultrapassa wire.bin')
            if row.kind=='end': end=True
        require(end,'Marcador de fim ausente')
        require(offset==length,'Cauda wire sem índice')
        # Hash per read is independently checked, even if a manifest was recomputed.
        for _ in self.chunks():
            pass

    def chunks(self):
        path = self.root/'observed/wire.bin'
        f = path.open('rb') if path.exists() else None
        try:
            for row in self.timeline():
                data = f.read(row.size) if f and row.size else b''
                yield ObservedChunk(row.to_json().encode(),data)
        finally:
            if f: f.close()
