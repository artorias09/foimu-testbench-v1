"""Capture identity before execution; no dependency on an acquisition runner."""
import hashlib
import platform
import subprocess
import time
from pathlib import Path
from . import __version__
from .core import CodeIdentity, TimePoint, Run, ClockDefinition


def collect_identity(root):
    root=Path(root).resolve()
    hashes={}
    for folder in ('foimu_testbench','tests','configs'):
        for path in sorted((root/folder).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                hashes[path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ('pyproject.toml','requirements.txt','tools/acceptance.py'):
        if (root/name).is_file(): hashes[name]=hashlib.sha256((root/name).read_bytes()).hexdigest()
    def git(*args):
        return subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,check=True,timeout=5).stdout.strip()
    try:
        require_root=Path(git('rev-parse','--show-toplevel')).resolve()
        if require_root!=root:
            raise ValueError('Diretório não é a raiz do repositório solicitado')
        commit,tree=git('rev-parse','HEAD'),git('rev-parse','HEAD^{tree}')
        dirty=bool(git('status','--porcelain','--untracked-files=all'))
        metadata=dict(git_status='available',commit=commit,tree=tree,dirty=dirty)
    except (OSError,subprocess.SubprocessError,ValueError) as exc:
        metadata=dict(git_status='unavailable',unavailable_reason=f'{type(exc).__name__}: Git não disponível para esta raiz')
    return CodeIdentity(app_version=__version__,python=platform.python_version(),os=platform.platform(),
        architecture=platform.machine() or 'unknown',collected_at=TimePoint(clock_id='catalog-utc',meaning='catalog',value=time.time_ns()),hashes=hashes,**metadata)


def new_run(scenario, root, *, run_id):
    """A draft captures identity now; it does not start an experiment or write files."""
    scenario.__post_init__()
    return Run(run_id=run_id,scenario_id=scenario.scenario_id,code_identity=collect_identity(root),
        clocks=[ClockDefinition(clock_id='catalog-utc',kind='utc_catalog',origin='Unix epoch'),
                ClockDefinition(clock_id='experiment',kind=scenario.clock_mode)],
        fidelity=[scenario.fidelity],criteria=list(scenario.acceptance_criteria),
        scenario_sha256=hashlib.sha256(scenario.to_json().encode()).hexdigest(),
        seed=scenario.seed,protocol_profile=scenario.protocol_profile)
