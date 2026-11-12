"""Fixed PRE-GATE corpus, seeds 0..199."""
import json
import random
from foimu_testbench.protocol import StreamParser, encode
from foimu_testbench.simulator import synthetic_packet


def run():
    total = frames = 0
    for seed in range(200):
        rng = random.Random(seed)
        data = bytearray()
        for i in range(32):
            frame = encode(synthetic_packet(i, 100))
            bad = bytearray(frame)
            bad[-1] ^= 1
            parts = [frame, bad, b'\xa0'+frame, rng.randbytes(rng.randrange(80)),
                     b'\xa0'*rng.randrange(1,60), b'\0\xff'*17, frame[:rng.randrange(1,53)]]
            rng.shuffle(parts)
            data.extend(b''.join(parts))
        p = StreamParser()
        n = accepted = 0
        while n < len(data):
            chunk = data[n:n+rng.randrange(1,101)]
            accepted += sum(1 for _ in p.feed(chunk))
            n += len(chunk)
            assert n == 53*accepted+p.stats['discarded_bytes']+len(p.buffer)
        p.finish()
        assert n == 53*accepted+p.stats['discarded_bytes']
        total += n
        frames += accepted
    if (total, frames) != (1854905, 12801):
        raise AssertionError('Corpus de referência divergente')
    return dict(seeds=200, first_seed=0, last_seed=199, bytes=total, frames=frames, violations=0)


if __name__ == '__main__':
    print(json.dumps(run()))
