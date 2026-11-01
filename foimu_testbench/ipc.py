"""One loopback request per connection. Network-order length + strict UTF-8 JSON."""
import socket
import struct
import time
import uuid
from .core.schema import require
from .evidence import dumps, loads

LIMIT = 4 * 1024 * 1024
QUERIES = {'hello', 'get_status', 'snapshot_request'}
COMMANDS = {'start_run', 'stop_run', 'open_run'}
PARTS = {'run_state', 'metrics_snapshot', 'signal_snapshot', 'event_snapshot', 'pipeline_health', 'run_finished'}
KINDS = QUERIES | COMMANDS | PARTS | {'hello_ack', 'command_ack', 'snapshot', 'error'}


def envelope(kind, payload, ident=None):
    return dict(schema_version=1, message_type=kind, id=ident or uuid.uuid4().hex,
                catalog_ns=time.time_ns(), payload=payload)


def validate(row):
    require(type(row) is dict and set(row) == {'schema_version','message_type','id','catalog_ns','payload'}, 'Envelope inválido')
    require(type(row['schema_version']) is int and row['schema_version'] == 1, 'Versão IPC inválida')
    require(type(row['message_type']) is str and row['message_type'] in KINDS, 'Mensagem desconhecida')
    require(type(row['id']) is str and 0 < len(row['id']) <= 128, 'ID inválido')
    require(type(row['catalog_ns']) is int and row['catalog_ns'] >= 0, 'Tempo de catálogo inválido')
    require(type(row['payload']) is dict, 'Payload deve ser objeto')
    return row


def exact(sock, size):
    out = bytearray()
    while len(out) < size:
        part = sock.recv(size - len(out))
        if not part:
            raise ConnectionError('Conexão encerrada durante a leitura')
        out.extend(part)
    return bytes(out)


def receive(sock):
    size, = struct.unpack('!I', exact(sock, 4))
    require(0 < size <= LIMIT, 'Comprimento fora do limite')
    return validate(loads(exact(sock, size)))


def send(sock, row):
    data = dumps(validate(row))
    require(len(data) <= LIMIT, 'Mensagem excede 4 MiB')
    sock.sendall(struct.pack('!I', len(data)) + data)


def request(port, kind, payload=None, timeout=5):
    row = envelope(kind, {} if payload is None else payload)
    with socket.create_connection(('127.0.0.1', port), timeout=timeout) as sock:
        send(sock, row)
        reply = receive(sock)
    require(reply['id'] == row['id'], 'Resposta fora de correlação')
    return reply
