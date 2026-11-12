"""Cross-platform CI entry point. Store individual test IDs and process logs."""
import argparse
from fnmatch import fnmatchcase
import json
from pathlib import Path
import platform
import subprocess
import sys
import unittest

from .conservation import run as conservation
from .counter_mutants import MUTANTS
from .evidence_mutants import RULES


def cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from cases(item)
        else:
            yield item


def tests(out, label, include=('*',), exclude=(), exact=None, min_count=1):
    found = cases(unittest.defaultTestLoader.discover('tests'))
    selected = [t for t in found if any(fnmatchcase(t.id(), p) for p in include)
                and not any(fnmatchcase(t.id(), p) for p in exclude)]
    with (out / (label + '.log')).open('w', encoding='utf-8') as log:
        r = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.TestSuite(selected))
    summary = dict(total=r.testsRun, passed=r.testsRun-len(r.errors)-len(r.failures)-len(r.skipped),
                   failed=len(r.errors)+len(r.failures), skipped=[(t.id(), why) for t, why in r.skipped])
    (out / (label + '.json')).write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(label, summary, flush=True)
    if (not r.wasSuccessful() or r.skipped or r.testsRun < min_count
            or (exact is not None and r.testsRun != exact)):
        raise RuntimeError('Gate falhou: ' + label)


def mutants(out):
    table = []
    errors = []
    def record(key, component, expected, result):
        table.append(dict(id=key, component=component, expected_killer=expected, actual_result=result))
    for module, specs in [('counter_mutants', MUTANTS), ('evidence_mutants', RULES)]:
        proc = subprocess.run([sys.executable, '-m', 'tools.' + module], capture_output=True, text=True)
        (out / (module + '.log')).write_text(proc.stdout + proc.stderr, encoding='utf-8')
        lines = proc.stdout.splitlines()
        for i, spec in enumerate(specs, 1):
            key = ('M' if module == 'counter_mutants' else 'E') + f'{i:02}'
            expected = spec[-1]
            valid = lines.count(f'{key} KILLED {expected}') == 1
            record(key, spec[0], expected, 'killed' if valid else 'unconfirmed')
        if proc.returncode or len(lines) != len(specs):
            errors.append(module)
    target = 'test_observed_boundary.BoundaryTests.test_live_truth_mutant_killed_by_file_source'
    try:
        tests(out, 'T01', (target,), exact=1)
    except RuntimeError:
        errors.append('T01')
    record('T01', 'processing', target, 'unconfirmed' if 'T01' in errors else 'killed')
    (out / 'matrix.json').write_text(json.dumps(table, indent=2), encoding='utf-8')
    if errors or len(table) != 28 or any(r['actual_result'] != 'killed' for r in table):
        raise RuntimeError('Matriz incompleta/inválida: ' + str(errors))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('job', choices=('core', 'gui', 'mutants', 'properties', 'boundary'))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if platform.python_implementation() != 'CPython' or sys.version_info[:2] != (3, 12) or not __debug__:
        parser.error('Requer CPython 3.12 sem otimização')
    out = args.out
    out.mkdir(parents=True, exist_ok=False)
    if args.job == 'core':
        tests(out, 'core', exclude=('test_p3_window.*',), min_count=158)
        for label, pattern, minimum in [('P1','test_p1*',31), ('P2','test_p2*',47), ('P3','test_p3.*',18),
                ('boundary','test_observed_boundary.*',11), ('counter','test_counter.*',8),
                ('state','test_evidence_tree.*',9)]:
            tests(out, label, (pattern,), min_count=minimum)
    elif args.job == 'gui':
        tests(out, 'window', ('test_p3_window.*',), exact=4)
        tests(out, 'full-suite-gui', exact=162)
    elif args.job == 'boundary':
        tests(out, 'boundary', ('test_observed_boundary.*',), min_count=11)
    elif args.job == 'properties':
        tests(out, 'properties', ('test_evidence_tree.*','test_counter.*','test_protocol.*','test_corpus.*'))
        result = conservation()
        result.update(counter_seeds=100, counter_transitions=25600, tree_seeds=40, trees=2000)
        (out / 'properties-summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    else:
        mutants(out)


if __name__ == '__main__':
    main()
