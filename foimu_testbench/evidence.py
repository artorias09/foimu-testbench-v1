"""Immutable worker boundaries and portable evidence schemas. No simulator imports."""
from dataclasses import dataclass
from typing import Literal
import hashlib
import json
from .core.schema import Model, require, _pairs
from .core import TimePoint, ByteSpan


def dumps(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def loads(value):
    return json.loads(value, object_pairs_hook=_pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('JSON não finito: '+x)))


@dataclass(frozen=True, kw_only=True)
class ChunkRecord(Model):
    kind: Literal['chunk', 'tick', 'epoch', 'end']
    stream_id: str
    epoch_id: str
    read_seq: int
    global_offset: int
    size: int
    time: TimePoint
    transport_origin: str
    sha256: str | None = None

    def validate(self):
        from .core.contracts import sha
        require(self.read_seq >= 0 and self.global_offset >= 0 and 0 <= self.size <= 65536, 'Sequência/offset/tamanho negativo')
        require(self.time.meaning == 'host_receive' and self.time.value is not None, 'Recepção requer clock e tempo conhecido')
        require((self.kind == 'chunk') == (self.size > 0), 'Somente chunk possui bytes')
        require((self.kind == 'chunk') == (self.sha256 is not None), 'Chunk requer hash dos bytes')
        sha(self.sha256)


@dataclass(frozen=True, slots=True)
class ObservedChunk:
    """Metadata is canonical JSON bytes, never a shared dict or P1 mutable list."""
    metadata: bytes
    data: bytes

    def __post_init__(self):
        require(type(self.metadata) is bytes and type(self.data) is bytes, 'Envelope requer bytes imutáveis')
        rec = self.record()
        require(len(self.data) == rec.size, 'Comprimento diferente do índice')
        require(not self.data or hashlib.sha256(self.data).hexdigest() == rec.sha256, 'Hash do chunk inválido')

    def record(self):
        return ChunkRecord.from_json(self.metadata)

    @property
    def weight(self):
        return len(self.metadata) + len(self.data)

    @classmethod
    def make(cls, data, *, ns, offset, seq, kind=None, epoch='0', origin='virtual', clock='experiment'):
        data = bytes(data)
        rec = ChunkRecord(kind=kind or ('chunk' if data else 'tick'), stream_id='wire',
            epoch_id=epoch, read_seq=seq, global_offset=offset, size=len(data),
            time=TimePoint(clock_id=clock, meaning='host_receive', value=ns),
            transport_origin=origin, sha256=hashlib.sha256(data).hexdigest() if data else None)
        return cls(rec.to_json().encode(), data)


@dataclass(frozen=True, kw_only=True)
class ObservedFrame(Model):
    frame_id: str
    stream_id: str
    epoch_id: str
    counter: int
    byte_span: ByteSpan
    chunk_refs: list[int]
    time: TimePoint
    fields: dict[str, object]
    numeric_status: dict[str, str]
    integrity: Literal['header_fletcher_valid'] = 'header_fletcher_valid'

    def validate(self):
        require(0 <= self.counter <= 255, 'Counter fora de uint8')
        require(self.byte_span.end-self.byte_span.start == 53, 'Frame deve possuir 53 bytes')
        require(bool(self.chunk_refs) and all(x >= 0 for x in self.chunk_refs), 'Frame requer referências a chunks')
        require(self.time.meaning == 'host_receive', 'Frame usa recepção do último chunk, não amostragem')


@dataclass(frozen=True, slots=True)
class WriteItem:
    path: str
    body: bytes

    def __post_init__(self):
        require(type(self.path) is str and type(self.body) is bytes, 'Registro requer caminho e bytes imutáveis')


@dataclass(frozen=True, slots=True)
class WriteBatch:
    items: tuple[WriteItem, ...]

    def __post_init__(self):
        require(type(self.items) is tuple and all(type(x) is WriteItem for x in self.items), 'Lote requer tupla imutável de registros')

    @property
    def weight(self):
        return sum(len(x.body) for x in self.items)


def record_item(path, value):
    return WriteItem(path, dumps(value) + b'\n')
