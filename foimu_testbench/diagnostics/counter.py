"""Counter8 transitions within one explicitly declared epoch."""
from typing import Literal, NamedTuple


class CounterState(NamedTuple):
    reference: int | None = None
    reacquiring: bool = False


Kind = Literal['initial', 'contiguous', 'duplicate', 'forward_gap_candidate',
               'ambiguous_jump', 'pending', 'reacquired']


class CounterObservation(NamedTuple):
    kind: Kind
    previous: int | None
    current: int
    delta: int | None
    candidate_missing: int | None
    state: CounterState


def transition(state: CounterState, current: int) -> CounterObservation:
    if type(current) is not int or not 0 <= current <= 255:
        raise ValueError('Counter deve ser uint8')
    previous = state.reference
    delta = None if previous is None else (current - previous) % 256
    missing = None
    if previous is None:
        kind = 'initial'
    elif state.reacquiring:
        kind = 'reacquired' if delta == 1 else 'pending'
    elif delta == 1:
        kind = 'contiguous'
    elif delta == 0:
        kind = 'duplicate'
    elif delta < 128:
        kind = 'forward_gap_candidate'
        missing = delta - 1
    else:
        kind = 'ambiguous_jump'
    after = CounterState(current, kind in ('ambiguous_jump', 'pending'))
    return CounterObservation(kind, previous, current, delta, missing, after)
