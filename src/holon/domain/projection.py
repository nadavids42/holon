"""Pure, nondecaying binary Beta readout of a single proposition's ledger.

Mass is stipulated impact, not calibrated probability. Cluster assignments and
eligibility are supplied by the caller; this module does not infer independence.
"""
from dataclasses import dataclass
import math
from typing import Iterable

from holon.domain.records import Relation

DYNAMICS_VERSION = "binary-beta-v1"


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonblank text")


def _number(value, label, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    try:
        value = float(value)
    except OverflowError as error:
        raise ValueError(f"{label} is outside the numeric range") from error
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f"{label} must be finite and {'positive' if positive else 'nonnegative'}")
    return value


def _sum(values):
    try:
        result = math.fsum(values)
    except OverflowError as error:
        raise ValueError("Projection aggregate exceeds the numeric range") from error
    if not math.isfinite(result):
        raise ValueError("Projection aggregate exceeds the numeric range")
    return result


@dataclass(frozen=True)
class ProjectionPolicy:
    version: str = "binary-beta-v1"
    alpha0: float = 1.0
    beta0: float = 1.0
    cluster_cap: float = 1.0

    def __post_init__(self):
        _text(self.version, "policy version")
        for name in ("alpha0", "beta0", "cluster_cap"):
            object.__setattr__(self, name, _number(getattr(self, name), name, positive=True))
        _sum((self.alpha0, self.beta0))


@dataclass(frozen=True)
class ProjectionEvidence:
    evidence_id: str
    proposition_id: str
    cluster_id: str
    relation: Relation
    mass: float = 1.0
    active: bool = True
    exclusion_reason: str | None = None

    def __post_init__(self):
        for name in ("evidence_id", "proposition_id", "cluster_id"):
            _text(getattr(self, name), name)
        try:
            object.__setattr__(self, "relation", Relation(self.relation))
        except (TypeError, ValueError) as error:
            raise ValueError("Invalid evidence relation") from error
        object.__setattr__(self, "mass", _number(self.mass, "mass"))
        if not isinstance(self.active, bool):
            raise ValueError("active must be a boolean")
        if self.exclusion_reason is not None:
            _text(self.exclusion_reason, "exclusion reason")


@dataclass(frozen=True)
class ClusterSummary:
    cluster_id: str
    evidence_ids: tuple[str, ...]
    raw_support: float
    raw_contradiction: float
    effective_support: float
    effective_contradiction: float
    support_multiplier: float
    contradiction_multiplier: float


@dataclass(frozen=True)
class ProjectionResult:
    proposition_id: str
    dynamics_version: str
    policy: ProjectionPolicy
    alpha: float
    beta: float
    mean: float
    variance: float
    evidence_strength: float
    posterior_concentration: float
    raw_support: float
    raw_contradiction: float
    effective_support: float
    effective_contradiction: float
    conflict_balance: float
    opposing_mass: float
    active_count: int
    withdrawn_count: int
    excluded_count: int
    evidence_ids: tuple[str, ...]
    withdrawn_ids: tuple[str, ...]
    exclusions: tuple[tuple[str, str], ...]
    clusters: tuple[ClusterSummary, ...]


def project_binary(proposition_id: str, evidence: Iterable[ProjectionEvidence],
                   policy: ProjectionPolicy = ProjectionPolicy()) -> ProjectionResult:
    """Project one ledger snapshot without mutating inputs or consulting time.

    IDs must be unique: repeated IDs are input errors, not extra evidence.
    Distinct repeated reports remain raw records and share their declared cap.
    Withdrawn records take precedence over exclusion reasons in disjoint counts.
    Active count includes excluded links; contributing IDs exclude those links.
    """
    _text(proposition_id, "proposition_id")
    if not isinstance(policy, ProjectionPolicy):
        raise ValueError("policy must be a ProjectionPolicy")
    records = list(evidence)
    if any(not isinstance(item, ProjectionEvidence) for item in records):
        raise ValueError("evidence must contain ProjectionEvidence records")
    records.sort(key=lambda item: item.evidence_id)
    if len({item.evidence_id for item in records}) != len(records):
        raise ValueError("Duplicate evidence ID in projection snapshot")
    if any(item.proposition_id != proposition_id for item in records):
        raise ValueError("Projection snapshot mixes propositions")
    withdrawn = tuple(item.evidence_id for item in records if not item.active)
    exclusions = tuple((item.evidence_id, item.exclusion_reason) for item in records
                       if item.active and item.exclusion_reason is not None)
    contributing = [item for item in records if item.active and item.exclusion_reason is None]
    groups = {}
    for item in contributing:
        groups.setdefault(item.cluster_id, []).append(item)
    clusters = []
    for cluster_id, items in sorted(groups.items()):
        positive = _sum(item.mass for item in items if item.relation == Relation.SUPPORTS)
        negative = _sum(item.mass for item in items if item.relation == Relation.CONTRADICTS)
        support, contradiction = min(positive, policy.cluster_cap), min(negative, policy.cluster_cap)
        clusters.append(ClusterSummary(cluster_id, tuple(item.evidence_id for item in items),
                                       positive, negative, support, contradiction,
                                       support / positive if positive else 0.0,
                                       contradiction / negative if negative else 0.0))
    raw_support = _sum(c.raw_support for c in clusters)
    raw_contradiction = _sum(c.raw_contradiction for c in clusters)
    support = _sum(c.effective_support for c in clusters)
    contradiction = _sum(c.effective_contradiction for c in clusters)
    alpha, beta = _sum((policy.alpha0, support)), _sum((policy.beta0, contradiction))
    strength, concentration = _sum((support, contradiction)), _sum((alpha, beta))
    mean = alpha / concentration
    # Product form avoids overflowing alpha*beta or concentration squared.
    variance = mean * (beta / concentration) / (concentration + 1.0)
    opposing = min(support, contradiction)
    balance = 2.0 * (opposing / strength) if strength else 0.0
    return ProjectionResult(
        proposition_id, DYNAMICS_VERSION, policy, alpha, beta, mean, variance,
        strength, concentration, raw_support, raw_contradiction, support, contradiction,
        balance, opposing, len(records) - len(withdrawn), len(withdrawn), len(exclusions),
        tuple(item.evidence_id for item in contributing), withdrawn, exclusions, tuple(clusters))
