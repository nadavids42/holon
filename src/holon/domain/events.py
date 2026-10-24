"""A revision records the full evidence set used by a deterministic policy."""
from dataclasses import dataclass


@dataclass(frozen=True)
class BeliefRevision:
    sequence: int
    status: str
    evidence_ids: list[str]
    recorded_at: str
    policy: str = "presence-v1"
