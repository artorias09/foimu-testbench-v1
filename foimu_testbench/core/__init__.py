"""P1 contracts. Legacy executors remain independent of these models."""
from .schema import Model
from .contracts import (
    AcceptanceCriterion, ArtifactReference, ByteSpan, ClockDefinition, CodeIdentity,
    EvaluationResult, Event, Fidelity, Provenance, Reference, Run, TimePoint,
    elapsed_ns, evaluate, validate_time,
)
