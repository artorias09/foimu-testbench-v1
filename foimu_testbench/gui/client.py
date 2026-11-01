import queue
import threading
import time
import uuid
from ..ipc import request
from ..evidence import dumps


class Latest:
    def __init__(self):
        self.lock = threading.Lock()
        self.value = None
        self.replaced = 0

    def put(self, value):
        with self.lock:
            self.replaced += self.value is not None
            self.value = value

    def take(self):
        with self.lock:
            value, self.value = self.value, None
            return value


class Client(threading.Thread):
    def __init__(self, port):
        super().__init__(name='gui-ipc', daemon=True)
        self.port = port
        self.closed = threading.Event()
        self.commands = queue.Queue(8)
        self.replies = queue.Queue(8)
        self.latest = Latest()
        self.received = self.skipped = 0
        self.first = self.last = None

    def submit(self, kind, payload):
        cid = uuid.uuid4().hex
        self.commands.put_nowait((kind, dict(payload, command_id=cid)))
        return cid

    def run(self):
        seq = None
        while not self.closed.is_set():
            try:
                kind, payload = self.commands.get_nowait()
            except queue.Empty:
                kind = None
            if kind:
                try:
                    reply = request(self.port, kind, payload, timeout=120 if kind == 'open_run' else 5)
                    result = dict(reply['payload'], successful=reply['message_type'] == 'command_ack')
                except (ValueError, OSError) as exc:
                    result = dict(successful=False, detail=f'Entrega incerta. Consulte o estado. {exc}')
                self.replies.put(dumps(dict(result, command_id=payload['command_id'])))
            try:
                reply = request(self.port, 'snapshot_request')
                if reply['message_type'] != 'snapshot':
                    raise ValueError(reply['payload'].get('detail','Resposta inesperada'))
                snap = reply['payload']
                current = snap['sequence']
                if current != seq:
                    if seq is not None:
                        self.skipped += max(0, current-seq-1)
                    seq = current
                    self.received += 1
                    self.last = time.monotonic()
                    if self.first is None:
                        self.first = self.last
                    self.latest.put(dumps(dict(snap, connected=True)))
            except (ValueError, OSError) as exc:
                seq = None
                self.latest.put(dumps(dict(connected=False, detail=str(exc))))
            self.closed.wait(.2)

    def stats(self):
        interval = self.last-self.first if self.last and self.first else 0
        return dict(received=self.received, replaced=self.latest.replaced, skipped=self.skipped,
                    rate_hz=(self.received-1)/interval if interval else None)
