import json
import socket
import time
from pathlib import Path
from .acquisition import Capture
from .simulator import FakeFOIMU, Fragmenter


def demo(config, out, record=True):
    simulator = FakeFOIMU(config)
    fragmenter = Fragmenter(config["chunk_sizes"])
    capture = Capture(out, config, "virtual_deterministic", config["packets"], record)
    start = time.perf_counter()
    end_s = 0.0
    completed = False
    last_bytes_s = 0.0
    timeout_active = False
    try:
        for event in simulator.events():
            end_s = event.delivery_s
            if end_s - last_bytes_s >= config["stream_timeout_s"] and not timeout_active:
                capture.timeout(last_bytes_s + config["stream_timeout_s"])
                timeout_active = True
            for chunk in fragmenter.split(event.data):
                capture.ingest(chunk, end_s)
                last_bytes_s = end_s
                timeout_active = False
        completed = True
    finally:
        elapsed = time.perf_counter() - start
        result = capture.finish(max(end_s, config["packets"] / config["rate_hz"]),
                                truth={"planned": config["packets"], **simulator.injector.counts},
                                extra={"wall_elapsed_s": elapsed, "completed": completed,
                                       "real_time_soak": False})
    return result


def serve(config, host, port, disconnect_at=None):
    simulator = FakeFOIMU(config)
    fragmenter = Fragmenter(config["chunk_sizes"])
    client = None
    connections = 0
    sent_bytes = 0
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((host, port))
        listener.listen(1)
        listener.settimeout(0.1)
        print(f"READY {host}:{listener.getsockname()[1]} protocol={config['protocol']}", flush=True)
        start = None
        try:
            for event in simulator.events():
                if disconnect_at is not None and event.index == disconnect_at and client:
                    client.close()
                    client = None
                while client is None:
                    try:
                        client, _ = listener.accept()
                        client.settimeout(1.0)
                        client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        connections += 1
                    except socket.timeout:
                        continue
                if start is None:
                    start = time.monotonic()
                remaining = start + event.delivery_s - time.monotonic()
                if remaining > 0:
                    time.sleep(remaining)
                try:
                    for chunk in fragmenter.split(event.data):
                        client.sendall(chunk)
                        sent_bytes += len(chunk)
                except (OSError, socket.timeout):
                    client.close()
                    client = None
        finally:
            if client is not None:
                client.close()
    return {"planned": config["packets"], "connections": connections,
            "bytes_written_to_tcp": sent_bytes, "faults": simulator.injector.counts,
            "note": "TCP write completion is not proof of host parser acceptance"}


def acquire(config, out, host, port, seconds, max_packets=None):
    capture = Capture(out, config, "tcp_real_clock", expected=None)
    start = time.monotonic()
    deadline = start + seconds
    last_bytes = start
    timeout_active = False
    connected_once = False
    connection = None
    status = "completed"
    try:
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now - last_bytes >= config["stream_timeout_s"] and not timeout_active:
                capture.timeout(now - start)
                timeout_active = True
            if connection is None:
                try:
                    connection = socket.create_connection((host, port), timeout=min(0.1, max(0.001, deadline - now)))
                    connection.settimeout(0.05)
                    capture.new_epoch(time.monotonic() - start, reconnect=connected_once)
                    connected_once = True
                except OSError:
                    connection = None
                    time.sleep(min(0.05, max(0, deadline - time.monotonic())))
                    continue
            try:
                data = connection.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                data = b""
            now = time.monotonic()
            if not data:
                capture.event("disconnected", now - start)
                connection.close()
                connection = None
                continue
            last_bytes = now
            timeout_active = False
            capture.ingest(data, now - start)
            if max_packets is not None and capture.diagnostics.received >= max_packets:
                break
    except KeyboardInterrupt:
        status = "interrupted"
    except BaseException:
        status = "error"
        raise
    finally:
        if connection is not None:
            connection.close()
        result = capture.finish(time.monotonic() - start, extra={"status": status,
                                 "host": host, "port": port, "requested_seconds": seconds,
                                 "max_packets": max_packets,
                                 "real_time_soak": seconds >= 28800 and status == "completed" and max_packets is None})
    return result


def replay(config, out, input_path, timing=None):
    capture = Capture(out, config, "replay_observed_chunks" if timing else "replay_bytes_synthetic_timing")
    end_s = 0.0
    status = "completed"
    try:
        with Path(input_path).open("rb") as wire:
            if timing:
                with Path(timing).open(encoding="utf-8") as timeline:
                    for line in timeline:
                        event = json.loads(line)
                        end_s = event["received_s"]
                        if event["event"] == "chunk":
                            if wire.tell() != event["offset"]:
                                raise ValueError("Timeline offset does not match wire position")
                            data = wire.read(event["length"])
                            if len(data) != event["length"]:
                                raise ValueError("Timeline extends beyond raw file")
                            capture.ingest(data, end_s)
                        elif event["event"] == "connection":
                            capture.new_epoch(end_s, event["reconnect"])
                        elif event["event"] == "stream_timeout":
                            capture.timeout(end_s)
                        elif event["event"] == "disconnected":
                            capture.event("disconnected", end_s)
                        elif event["event"] == "end":
                            pass
                        else:
                            raise ValueError("Unknown timeline event")
                if wire.read(1):
                    raise ValueError("Raw bytes remaining after end of timeline")
            else:
                # Invented replay timing is explicitly labelled; this is not the original arrival timing.
                while data := wire.read(53):
                    end_s += 1 / config["rate_hz"]
                    capture.ingest(data, end_s)
    except BaseException:
        status = "error"
        raise
    finally:
        result = capture.finish(end_s, extra={"status": status, "input": str(input_path),
                                 "timing_source": str(timing) if timing else "synthetic 53-byte chunks"})
    return result
