"""Execute targeted source mutations outside the working tree. Require a failing assertion."""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREE = 'evidence_tree.py'
WORST = 'max(states, key=ORDER.index) if states'
ORDER_TEST = 'test_evidence_tree.EvidenceTests.test_order_and_missing'
RULES = (
    (TREE, WORST, "'ok' if 'ok' in states else max(states, key=ORDER.index) if states", ORDER_TEST),
    (TREE, WORST, "max((s for s in states if s != 'failed'), default='ok', key=ORDER.index) if states", ORDER_TEST),
    (TREE, "return 'not_evaluated', 'MISSING_RESULT'", "return 'ok', 'MISSING_RESULT'", ORDER_TEST),
    (TREE, 'return value.result, value.reason', "return ('ok' if value.result == 'unknown' else value.result), value.reason", ORDER_TEST),
    (TREE, 'return value.result, value.reason', "return ('warning' if value.result == 'inconclusive' else value.result), value.reason", ORDER_TEST),
    (TREE, "limits.update(row['limitations'])", 'pass', 'test_evidence_tree.EvidenceTests.test_limits_and_optional'),
    (TREE, "if self.result in ('ok', 'warning'", "if self.result in ('warning'", 'test_evidence_tree.EvidenceTests.test_concrete_ref_required'),
    (TREE, "if r.integrity == 'partial' and not", "if False and not", 'test_evidence_tree.EvidenceTests.test_coverage_and_integrity'),
    (TREE, 'row = visit(child)', 'if child not in results:\n                seen.add(child)\n                continue\n            row = visit(child)', ORDER_TEST),
    (TREE, "'warning', 'inconclusive', 'failed')", "'inconclusive', 'warning', 'failed')", ORDER_TEST),
    (TREE, "return dumps(dict(schema=", "if __import__('os').getenv('SIMULATOR_TRUTH'):\n        rows[manifest.root]['result'] = 'unknown'\n    return dumps(dict(schema=",
     'test_evidence_tree.EvidenceTests.test_truth_independence'),
    (TREE, "return 'unknown', 'MISSING_COVERAGE'", "return value.result, 'MISSING_COVERAGE'", 'test_evidence_tree.EvidenceTests.test_coverage_and_integrity'),
    ('protocol/gateway53.py', 'self._discard(1)', 'self._discard(53)', 'test_protocol.ProtocolTests.test_truncated_then_valid'),
    ('replay.py', 'yield ReadResult(chunk.data,r.time.value,r.kind,r.epoch_id,r.transport_origin)',
     "if r.kind != 'epoch':\n                    yield ReadResult(chunk.data,r.time.value,r.kind,'0',r.transport_origin)",
     'test_p2_backend.BackendTests.test_replay_preserves_epoch_boundaries_and_partial_discard'),
    ('backend.py', 'raise Overload(self.name,self._snapshot(),weight)', 'self.items.popleft()',
     'test_p2_backend.BackendTests.test_bounded_queue_exact_limit_rejection_no_eviction'),
    ('storage.py', 'f.flush(); os.fsync(f.fileno())\n        self.confirmed = entries',
     'self.confirmed = entries\n        f.flush(); os.fsync(f.fileno())',
     'test_p2_storage.CheckpointOrderingTests.test_confirm_only_after_checkpoint_fsync'),
    ('backend.py', 'if writer_thread: writer_thread.join(self.options.shutdown_timeout_ns/1e9)',
     'if writer_thread: writer_thread.join(max(0, self.options.shutdown_timeout_ns-(time.monotonic_ns()-shutdown_start))/1e9)',
     'test_p2_shutdown.ShutdownBudgetTests.test_independent_budgets_allow_healthy_writer_to_drain'),
)


def execute(tmp, target):
    return subprocess.run([sys.executable, '-B', '-m', 'unittest', target], cwd=tmp,
                          capture_output=True, text=True)


def main():
    for number, (name, before, after, test) in enumerate(RULES, 1):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            shutil.copytree(ROOT / 'tests', tmp / 'tests', ignore=shutil.ignore_patterns('__pycache__'))
            pkg = tmp / 'foimu_testbench'
            shutil.copytree(ROOT / pkg.name, pkg, ignore=shutil.ignore_patterns('__pycache__'))
            target = 'tests.' + test
            clean = execute(tmp, target)
            if clean.returncode or 'skipped=' in clean.stderr or 'Ran 1 test in' not in clean.stderr:
                raise RuntimeError(clean.stderr)
            path = pkg / name
            src = path.read_text(encoding='utf-8')
            if src.count(before) != 1:
                raise ValueError(f'Alvo inválido: {number}')
            if number == 17:
                src = src.replace("        for name in ('rx','processing'):", "        shutdown_start = time.monotonic_ns()\n        for name in ('rx','processing'):")
            path.write_text(src.replace(before, after), encoding='utf-8')
            result = execute(tmp, target)
            if result.returncode != 1 or not re.search(r'^FAILED \(failures=[1-9][0-9]*\)$', result.stderr, re.MULTILINE) or f'FAIL: {test.split(".")[-1]} (' not in result.stderr or 'AssertionError' not in result.stderr:
                raise RuntimeError(f'Mutante {number}: sobrevivente ou ensaio inválido\n{result.stderr}')
            print(f'E{number:02d} KILLED {test}', flush=True)


if __name__ == '__main__':
    main()
