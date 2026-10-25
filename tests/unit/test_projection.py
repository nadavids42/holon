import dataclasses
import math
import random
import unittest

from holon.domain.projection import ProjectionEvidence, ProjectionPolicy, project_binary


def record(identifier, sign='supports', mass=1, cluster='source-A', **kwargs):
    return ProjectionEvidence(str(identifier), 'p', cluster, sign, mass, **kwargs)


class ProjectionTests(unittest.TestCase):
    def project(self, records=(), policy=ProjectionPolicy()):
        return project_binary('p', records, policy)

    def test_prior_and_one_sided_evidence(self):
        prior = self.project()
        self.assertEqual((prior.alpha, prior.beta, prior.mean), (1, 1, .5))
        self.assertAlmostEqual(prior.variance, 1 / 12)
        self.assertEqual(prior.evidence_strength, 0)
        self.assertEqual(prior.posterior_concentration, 2)
        positive = self.project([record(1)])
        negative = self.project([record(1, 'contradicts')])
        self.assertAlmostEqual(positive.mean, 2 / 3)
        self.assertAlmostEqual(negative.mean, 1 / 3)
        self.assertAlmostEqual(positive.variance, 1 / 18)

    def test_ignorance_and_balanced_conflict_are_distinct(self):
        records = [record(i, sign, cluster=f'{sign}-{i}') for i in range(10)
                   for sign in ('supports', 'contradicts')]
        # Unique IDs are ledger identities, independent of cluster membership.
        records = [dataclasses.replace(item, evidence_id=str(i)) for i, item in enumerate(records)]
        state = self.project(records)
        self.assertEqual(state.mean, self.project().mean)
        self.assertEqual((state.evidence_strength, state.opposing_mass, state.conflict_balance), (20, 10, 1))
        self.assertLess(state.variance, self.project().variance)

    def test_repetition_caps_per_cluster_and_sign(self):
        repeated = self.project([record(i) for i in range(1000)])
        self.assertEqual((repeated.raw_support, repeated.effective_support), (1000, 1))
        self.assertEqual(repeated.clusters[0].support_multiplier, .001)
        independent = self.project([record(i, cluster=str(i)) for i in range(10)])
        self.assertEqual(independent.effective_support, 10)
        self.assertGreater(independent.mean, repeated.mean)
        both = self.project([record(1, mass=10), record(2, 'contradicts', mass=20)])
        self.assertEqual((both.effective_support, both.effective_contradiction), (1, 1))
        self.assertEqual((both.raw_support, both.raw_contradiction), (10, 20))

    def test_zero_mass_and_cap_boundary(self):
        for mass in (0, .5, 1, 1.5):
            state = self.project([record(1, mass=mass)])
            self.assertEqual(state.effective_support, min(mass, 1))
            self.assertEqual(state.clusters[0].contradiction_multiplier, 0)
        self.assertEqual(self.project([record(1, mass=0)]).mean, .5)

    def test_withdrawals_exclusions_and_immutability(self):
        items = [record(1), record(2, 'contradicts', active=False),
                 record(3, 'contradicts', exclusion_reason='Not eligible'),
                 record(4, active=False, exclusion_reason='Also excluded')]
        original = tuple(items)
        state = self.project(items)
        self.assertEqual((state.active_count, state.withdrawn_count, state.excluded_count), (2, 2, 1))
        self.assertEqual(state.evidence_ids, ('1',))
        self.assertEqual(state.withdrawn_ids, ('2', '4'))
        self.assertEqual(state.exclusions, (('3', 'Not eligible'),))
        self.assertEqual(tuple(items), original)
        self.assertEqual(self.project([dataclasses.replace(items[0], active=False)]).mean, .5)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            state.policy.alpha0 = 2

    def test_permutations_and_partitioned_raw_evidence(self):
        rng = random.Random(42)
        items = [record(i, rng.choice(['supports', 'contradicts']), rng.random(), str(i % 7))
                 for i in range(100)]
        expected = self.project(items)
        for _ in range(20):
            rng.shuffle(items)
            self.assertEqual(self.project(iter(items)), expected)
        # Combine raw ledger partitions before projection; never merge capped totals.
        partitions = [items[i::3] for i in range(3)]
        self.assertEqual(self.project(item for part in partitions for item in part), expected)
        same_cluster = [record(1, mass=.75), record(2, mass=.75)]
        self.assertEqual(self.project(same_cluster).effective_support, 1)
        self.assertEqual(sum(self.project([item]).effective_support for item in same_cluster), 1.5)

    def test_directionality_under_random_additions(self):
        rng = random.Random(7)
        items = []
        for i in range(100):
            sign = rng.choice(['supports', 'contradicts'])
            before = self.project(items).mean
            items.append(record(i, sign, rng.random() * 2, str(i % 8)))
            after = self.project(items).mean
            if sign == 'supports':
                self.assertGreaterEqual(after + 1e-12, before)
            else:
                self.assertLessEqual(after - 1e-12, before)

    def test_custom_prior_and_policy(self):
        policy = ProjectionPolicy('experimental-v2', 2, 3, 4)
        state = self.project([record(1, mass=10)], policy)
        self.assertEqual((state.alpha, state.beta), (6, 3))
        self.assertTrue(math.isclose(state.mean, 2/3, rel_tol=1e-12, abs_tol=1e-12))
        self.assertEqual(state.policy, policy)

    def test_invalid_inputs(self):
        for value in (-1, math.inf, -math.inf, math.nan, True, '1', 10**1000):
            with self.subTest(value=str(value)[:20]):
                with self.assertRaises(ValueError):
                    record(1, mass=value)
        for field in ('alpha0', 'beta0', 'cluster_cap'):
            for value in (0, -1, math.inf, math.nan, True):
                with self.assertRaises(ValueError):
                    ProjectionPolicy(**{field: value})
        for kwargs in ({'cluster_id': ''}, {'relation': 'uncertain'}, {'active': 1},
                       {'exclusion_reason': ''}, {'evidence_id': ' '}):
            with self.assertRaises(ValueError):
                dataclasses.replace(record(1), **kwargs)
        with self.assertRaises(ValueError):
            self.project([record(1), record(1)])
        with self.assertRaises(ValueError):
            self.project([dataclasses.replace(record(1), proposition_id='other')])
        with self.assertRaises(ValueError):
            self.project([object()])

    def test_numeric_range_safety(self):
        with self.assertRaises(ValueError):
            self.project([record(1, mass=1e308), record(2, mass=1e308)])
        with self.assertRaises(ValueError):
            self.project([], ProjectionPolicy(alpha0=1e308, beta0=1e308))
        with self.assertRaises(ValueError):
            self.project([record(1, mass=1e308)], ProjectionPolicy(alpha0=1e308, cluster_cap=1e308))
        state = self.project([record(1, mass=1e300)], ProjectionPolicy(cluster_cap=1e300))
        for field in ('mean', 'variance', 'posterior_concentration', 'conflict_balance'):
            self.assertTrue(math.isfinite(getattr(state, field)))
