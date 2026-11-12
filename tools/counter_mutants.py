"""Run each counter mutant in a fresh temporary source tree, requiring assertion failure."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COUNTER = 'diagnostics/counter.py'
MUTANTS = (
    (COUNTER, 'delta < 128', 'delta < 127', 'test_pairs'),
    (COUNTER, 'delta < 128', 'delta < 129', 'test_pairs'),
    (COUNTER, '(current - previous) % 256', 'current - previous', 'test_pairs'),
    (COUNTER, "elif delta == 1:", "elif previous == 255 and current == 0:\n        kind = 'ambiguous_jump'\n    elif delta == 1:", 'test_pairs'),
    (COUNTER, 'missing = delta - 1', 'missing = delta', 'test_pairs'),
    (COUNTER, "kind = 'reacquired' if delta == 1 else 'pending'", "kind = 'pending'", 'test_arbitrary_jump_and_reorder'),
    (COUNTER, "kind in ('ambiguous_jump', 'pending')", "kind == 'pending'", 'test_arbitrary_jump_and_reorder'),
    ('diagnostics/__init__.py', 'def new_epoch(self):\n        self.counter_state = CounterState()',
     'def new_epoch(self):\n        pass', 'test_epoch_reset'),
    ('presentation.py', 'self.counter_state = observation.state',
     "if observation.delta is None or 0 < observation.delta < 128:\n                self.counter_state = CounterState(c)",
     'test_view_diagnostic_equivalence'),
    ('observability.py', "'counter8', 'not_observable', 'COUNTER8_ALIASING'",
     "'counter8', 'observable', 'COUNTER8_ALIASING'", 'test_alias_256'),
)


def run_case(tmp, test):
    return subprocess.run([sys.executable, '-B', '-m', 'unittest', 'test_counter.CounterTests.' + test],
                          cwd=tmp, capture_output=True, text=True)


def main():
    for index, (name, old, new, test) in enumerate(MUTANTS, 1):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / 'foimu_testbench'
            shutil.copytree(ROOT / pkg.name, pkg, ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copy(ROOT / 'tests/test_counter.py', tmp)
            clean = run_case(tmp, test)
            if clean.returncode or 'skipped=' in clean.stderr or 'Ran 1 test in' not in clean.stderr:
                raise RuntimeError(clean.stderr)
            path = pkg / name
            source = path.read_text(encoding='utf8')
            if source.count(old) != 1:
                raise ValueError(f'Alvo de mutação ambíguo M{index}')
            path.write_text(source.replace(old, new), encoding='utf8')
            result = run_case(tmp, test)
            if result.returncode != 1 or not re.search(r'^FAILED \(failures=[1-9][0-9]*\)$', result.stderr, re.MULTILINE) or f'FAIL: {test.split(".")[-1]} (' not in result.stderr or 'AssertionError' not in result.stderr:
                raise RuntimeError(f'M{index}: sobrevivente ou execução inválida\n{result.stderr}')
            print(f'M{index:02} KILLED {test}')


if __name__ == '__main__':
    main()
