"""The minimal epistemic vocabulary; independent of persistence."""
from dataclasses import dataclass
from enum import Enum


class Relation(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"


class BeliefStatus(str, Enum):
    SUPPORTED = "supported"
    OPPOSED = "opposed"
    CONTESTED = "contested"


@dataclass(frozen=True)
class Proposition:
    id: str
    claim: str
    scope: str


@dataclass(frozen=True)
class Observation:
    id: str
    source: str
    report: str
    recorded_at: str


@dataclass(frozen=True)
class Evidence:
    id: str
    observation_id: str
    proposition_id: str
    relation: Relation


def belief_status(relations: set[Relation]) -> BeliefStatus:
    if not relations:
        raise ValueError("A belief requires evidence")
    if len(relations) > 1:
        return BeliefStatus.CONTESTED
    if Relation.SUPPORTS in relations:
        return BeliefStatus.SUPPORTED
    return BeliefStatus.OPPOSED
