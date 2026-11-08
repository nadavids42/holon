"""Immutable derivation contracts; no storage, inference, or belief updates."""
from dataclasses import dataclass
import heapq
from typing import Iterable

from holon.domain.records import Relation

CONTRACT_VERSION = 'derivation-v1'


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be nonblank text')


def _identifier(value, label):
    _text(value, label)
    if value != value.strip():
        raise ValueError(f'{label} must not contain surrounding whitespace')


@dataclass(frozen=True)
class SignedClaim:
    """An explicit positive/negative stance toward one scoped proposition.

    `contradicts` is an explicit negative stance, never absence of support.
    This is a reference, not an evidence link or a truth assertion by Holon.
    """
    proposition_id: str
    relation: Relation = Relation.SUPPORTS

    def __post_init__(self):
        _identifier(self.proposition_id, 'proposition_id')
        if not isinstance(self.relation, str):
            raise ValueError('relation must be supports or contradicts')
        object.__setattr__(self, 'relation', Relation(self.relation))


@dataclass(frozen=True)
class Justification:
    """All premises jointly justify one signed conclusion under a supplied rule."""
    id: str
    conclusion: SignedClaim
    premises: tuple[SignedClaim, ...]
    rule: str
    actor: str
    reason: str

    def __post_init__(self):
        _identifier(self.id, 'justification id')
        if not isinstance(self.conclusion, SignedClaim):
            raise ValueError('conclusion must be a SignedClaim')
        if not isinstance(self.premises, (tuple, list)):
            raise ValueError('premises must be a tuple or list of SignedClaim references')
        premises = tuple(self.premises)
        if not premises or any(not isinstance(p, SignedClaim) for p in premises):
            raise ValueError('premises must contain at least one SignedClaim')
        if len(set(premises)) != len(premises):
            raise ValueError('Duplicate premise')
        if any(p.proposition_id == self.conclusion.proposition_id for p in premises):
            raise ValueError('Circular dependency: a conclusion cannot be its own premise')
        for name in ('rule', 'actor', 'reason'):
            _text(getattr(self, name), name)
        object.__setattr__(self, 'premises', tuple(sorted(premises, key=_claim_key)))


def _claim_key(claim):
    return claim.proposition_id, claim.relation.value


@dataclass(frozen=True)
class DerivationGraph:
    """Validated snapshot of supplied proposition identities and justifications.

    Every edge is premise → conclusion. Cycle checking ignores polarity and
    includes every alternative: even a grounded cycle is outside this contract.
    """
    proposition_ids: frozenset[str]
    justifications: tuple[Justification, ...] = ()

    def __post_init__(self):
        if not isinstance(self.proposition_ids, (frozenset, set, tuple, list)):
            raise ValueError('proposition_ids must be a collection of identifiers')
        ids = tuple(self.proposition_ids)
        for identifier in ids:
            _identifier(identifier, 'proposition id')
        if len(set(ids)) != len(ids):
            raise ValueError('Duplicate proposition id')
        if not isinstance(self.justifications, (tuple, list)):
            raise ValueError('justifications must be a tuple or list')
        justifications = tuple(self.justifications)
        if any(not isinstance(j, Justification) for j in justifications):
            raise ValueError('Expected Justification records')
        if len({j.id for j in justifications}) != len(justifications):
            raise ValueError('Duplicate justification id')
        known = frozenset(ids)
        for j in justifications:
            if any(p.proposition_id not in known for p in (j.conclusion, *j.premises)):
                raise ValueError(f'Unknown proposition reference in justification {j.id}')
        object.__setattr__(self, 'proposition_ids', known)
        object.__setattr__(self, 'justifications', tuple(sorted(justifications, key=lambda j: j.id)))
        self.topological_order()  # Also validates acyclicity, without recursion limits.

    def topological_order(self) -> tuple[str, ...]:
        successors = {pid: set() for pid in self.proposition_ids}
        indegree = {pid: 0 for pid in self.proposition_ids}
        for j in self.justifications:
            target = j.conclusion.proposition_id
            for premise in j.premises:
                source = premise.proposition_id
                if target not in successors[source]:
                    successors[source].add(target)
                    indegree[target] += 1
        ready = [pid for pid, degree in indegree.items() if degree == 0]
        heapq.heapify(ready)
        order = []
        while ready:
            pid = heapq.heappop(ready)
            order.append(pid)
            for target in sorted(successors[pid]):
                indegree[target] -= 1
                if indegree[target] == 0:
                    heapq.heappush(ready, target)
        if len(order) != len(self.proposition_ids):
            raise ValueError('Circular dependency in derivation graph')
        return tuple(order)

    def with_justification(self, justification: Justification):
        """Return a validated new snapshot; never mutate the original on failure."""
        return DerivationGraph(self.proposition_ids, (*self.justifications, justification))

    def alternatives(self, conclusion: SignedClaim) -> tuple[Justification, ...]:
        self._known_claim(conclusion)
        return tuple(j for j in self.justifications if j.conclusion == conclusion)

    def matching_justifications(self, conclusion: SignedClaim,
                                available: Iterable[SignedClaim]) -> tuple[Justification, ...]:
        """Structural AND/OR check against explicitly supplied available premises.

        Each returned justification has ALL premises present; ANY returned
        justification is an alternative. No status policy, closure, propagation,
        independent mass, or truth confidence is inferred from this result.
        """
        alternatives = self.alternatives(conclusion)
        try:
            supplied = tuple(available)
        except TypeError as error:
            raise ValueError('available must be an iterable of SignedClaim references') from error
        for claim in supplied:
            self._known_claim(claim)
        present = frozenset(supplied)
        return tuple(j for j in alternatives if all(p in present for p in j.premises))

    def _known_claim(self, claim):
        if not isinstance(claim, SignedClaim) or claim.proposition_id not in self.proposition_ids:
            raise ValueError('Expected a signed reference to a known proposition')
