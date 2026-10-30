"""Faithful v2 reprocessing with source configuration and explicit derived overrides."""
from dataclasses import replace
from pathlib import Path
from .backend import RunController
from .storage import RunReader, digest_file
from .emission import IterableSource, ReadResult
from .scenarios import Rate


def replay_run(source, out, *, rate_hz=None, source_root=None, options=None):
    reader=RunReader(source)
    scenario=reader.scenario
    changes={}
    if rate_hz is not None:
        changes['rate']={'original':scenario.rate.to_dict(), 'analysis':Rate(value=rate_hz,unit='Hz').to_dict()}
        scenario=replace(scenario,rate=Rate(value=rate_hz,unit='Hz'))
    def source_factory(_scenario, _run, _sink):
        def readings():
            for chunk in reader.chunks():
                r=chunk.record()
                yield ReadResult(chunk.data,r.time.value,r.kind,r.epoch_id,r.transport_origin)
        return IterableSource(readings())
    controller=RunController(scenario,out,source_root=source_root,options=options,source_factory=source_factory,
        parent_run_id=reader.run.run_id,operation='replay',derivation=dict(schema_version=2,
            source_run_id=reader.run.run_id,source_run_sha256=digest_file(Path(source)/'run.json'),
            source_scenario_sha256=reader.run.scenario_sha256,overrides=changes,
            semantics='Reprocessamento de bytes e recepção; truth de origem não fornecido ao SUT'))
    return controller.execute()
