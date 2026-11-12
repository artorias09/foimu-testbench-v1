"""ObservedCanonicalV1. Compare four canonical files byte for byte, in stream order."""
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from .evidence import dumps, loads
from .processing import Processing

FIELDS = ('counter', 'ifog_x', 'ifog_y', 'ifog_z', 'acc_x', 'acc_y', 'acc_z', 'acc_tap',
          'temperature', 'mems_gyro_x', 'mems_gyro_y', 'mems_gyro_z',
          'mems_acc_x', 'mems_acc_y', 'mems_acc_z')
METRICS = ('frames_accepted', 'raw_bytes', 'packets_received', 'packets_lost', 'duplicates',
           'out_of_order_or_reset', 'counter_discontinuities', 'reconnections', 'checksum_errors',
           'discarded_bytes', 'framing_errors', 'truncated_tails', 'resync_events',
           'byte_silence_episodes', 'valid_frame_silence_episodes', 'jitter_max_s',
           'largest_gap_without_valid_data_s')
PATHS = {'observed/frames.jsonl': 'frames', 'observed/events.jsonl': 'observed_events',
         'diagnostics/events.jsonl': 'diagnostic_events'}
PAYLOAD = {'checksum_candidate_rejected': (), 'discard': (), 'resync': (),
           'counter_discontinuity': ('counter', 'interpretation'),
           'byte_silence': ('threshold_ns', 'deadline_ns', 'detected_ns', 'detection_delay_ns'),
           'valid_frame_silence': ('threshold_ns', 'deadline_ns', 'detected_ns', 'detection_delay_ns')}


def select(data, keys):
    return {key: data[key] for key in keys}


def canonical_record(group, row):
    span = row['byte_span']
    common = dict(epoch_id=row['epoch_id'], byte_span=select(span, ('start', 'end')) if span else None,
                  time=select(row['time'], ('meaning', 'clock_id', 'value', 'unit')))
    if group == 'frames':
        return dict(**common, counter=row['counter'], integrity=row['integrity'],
                    fields=select(row['fields'], FIELDS), numeric_status=select(row['numeric_status'], FIELDS))
    return dict(**common, **select(row, ('kind', 'component_path', 'domain', 'epistemic_status',
                                        'facet', 'severity', 'rule_version')),
                payload=select(row['payload'], PAYLOAD[row['kind']]))


def canonical_metrics(metrics):
    return dict(schema='ObservedCanonicalV1', metrics=select(metrics, METRICS),
                period_s=select(metrics['period_s'], ('n_finite', 'mean', 'std_population', 'maximum', 'minimum')),
                sentinel_suspicions=select(metrics['sentinel_suspicions'], ('ifog_x', 'ifog_y', 'ifog_z', 'acc')))


@dataclass(frozen=True)
class ObservedCanonicalV1:
    directory: Path
    observed_integrity: str = 'complete'


@contextmanager
def reanalyze_observed(view):
    """Publish temporary canonical streams only after verifying every input digest."""
    spec = view.projection
    processing = Processing('observed-reanalysis', spec.rate_hz, spec.timeout_ns)
    with TemporaryDirectory() as tmp:
        directory = Path(tmp)
        with ExitStack() as stack:
            outputs = {path: stack.enter_context((directory / (group + '.jsonl')).open('wb'))
                       for path, group in PATHS.items()}
            for chunk in view.chunks():
                for item in processing.consume(chunk).items:
                    if item.path in outputs:
                        row = canonical_record(PATHS[item.path], loads(item.body))
                        outputs[item.path].write(dumps(row) + b'\n')
        (directory / 'metrics.json').write_bytes(dumps(canonical_metrics(processing.metrics())) + b'\n')
        yield ObservedCanonicalV1(directory)
