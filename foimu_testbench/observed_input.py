"""Read-only projection of legacy v2 capture metadata and observed file source."""
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Iterable

from .core import ArtifactReference
from .core.schema import Model, require
from .evidence import ChunkRecord, ObservedChunk, loads
from .protocol import PROFILE


@dataclass(frozen=True, kw_only=True)
class Fingerprint(Model):
    size_bytes: int
    sha256: str

    def validate(self):
        from .core.contracts import sha
        require(self.size_bytes >= 0, 'Tamanho negativo')
        sha(self.sha256)


@dataclass(frozen=True, kw_only=True)
class ObservedProjection(Model):
    protocol_profile: str
    rate_hz: int | float
    timeout_ns: int
    chunks: Fingerprint
    wire: Fingerprint | None

    def validate(self):
        require(self.protocol_profile == PROFILE, 'Perfil incompatível')
        require(self.rate_hz > 0 and self.timeout_ns >= 0, 'Parâmetros temporais inválidos')


def _fixed(root, name):
    path = root / name
    require(path.resolve() == root.resolve() / name, 'Redirecionamento de artefato')
    return path


def project_run(root):
    """Adapter outside the analyzer. Keep only operational values and two references."""
    root = Path(root)
    manifest = loads(_fixed(root, 'run.json').read_bytes())
    require(type(manifest['schema_version']) is int and manifest['schema_version'] == 2,
            'Manifesto v2 necessário')
    names = ('observed/wire.bin', 'observed/chunks.jsonl', 'scenario.resolved.json')
    refs = {}
    for raw in manifest['artifacts']:
        name = raw['path']
        if name in names:
            ref = ArtifactReference.from_dict(raw)
            require(name not in refs and ref.integrity == 'complete', 'Referência ambígua/parcial')
            refs[name] = Fingerprint(size_bytes=ref.size_bytes, sha256=ref.sha256)
    require(all(name in refs for name in names[1:]), 'Índice ou Scenario sem referência')
    data = _fixed(root, names[2]).read_bytes()
    _check(refs[names[2]], len(data), sha256(data))
    scenario = loads(data)
    rate = scenario['rate']
    timeout = scenario['diagnostic_policy']['stream_timeout']
    require(rate['unit'] == 'Hz' and timeout['unit'] == 's'
            and type(timeout['value']) in (int, float) and timeout['value'] > 0,
            'Unidade ou timeout inválido')
    return ObservedProjection(protocol_profile=scenario['protocol_profile'], rate_hz=rate['value'],
                              timeout_ns=round(timeout['value'] * 1e9),
                              wire=refs.get(names[0]), chunks=refs[names[1]])


def _check(ref, size, digest):
    require(size == ref.size_bytes and digest.hexdigest() == ref.sha256,
            'Hash/tamanho da evidência incompatível')


def _records(wire, index, spec):
    seq = offset = index_size = last_ns = 0
    epoch = None
    epochs = set()
    ended = False
    wire_hash, index_hash = sha256(), sha256()
    while line := index.readline(65537):
        require(len(line) <= 65536 and line.endswith(b'\n'), 'Linha de índice inválida')
        index_hash.update(line)
        index_size += len(line)
        row = ChunkRecord.from_json(line)
        require(not ended and row.stream_id == 'wire' and row.time.clock_id == 'experiment'
                and row.global_offset == offset and row.read_seq == seq and row.time.value >= last_ns,
                'Sequência, offset, tempo ou stream inválido')
        if row.kind == 'epoch':
            require(row.epoch_id not in epochs, 'Época repetida')
            epoch = row.epoch_id
            epochs.add(epoch)
        require(row.epoch_id == epoch, 'Época inválida')
        data = wire.read(row.size)
        chunk = ObservedChunk(line.rstrip(b'\n'), data)
        wire_hash.update(data)
        last_ns = row.time.value
        offset += len(data)
        seq += 1
        ended = row.kind == 'end'
        yield chunk
    require(ended and not wire.read(1), 'Fim ausente ou bytes sem índice')
    _check(spec.chunks, index_size, index_hash)
    if spec.wire is not None:
        _check(spec.wire, offset, wire_hash)


@dataclass(frozen=True, slots=True)
class ObservedView:
    projection: ObservedProjection
    chunks: Iterable[ObservedChunk]


@contextmanager
def open_observed(directory, projection):
    """Open only two fixed inputs; consumers must exhaust the iterator for verification."""
    directory = Path(directory)
    require(not directory.is_symlink(), 'Diretório observed redirecionado')
    with ExitStack() as stack:
        wire_path = _fixed(directory, 'wire.bin')
        if projection.wire is None:
            require(not wire_path.exists(), 'Wire sem referência')
            wire = BytesIO()
        else:
            wire = stack.enter_context(wire_path.open('rb'))
        index = stack.enter_context(_fixed(directory, 'chunks.jsonl').open('rb'))
        yield ObservedView(projection, _records(wire, index, projection))
