from dataclasses import FrozenInstanceError
import unittest

from holon.domain.derivation import DerivationGraph, Justification, SignedClaim
from holon.domain.records import Relation


def claim(pid, relation='supports'):
    return SignedClaim(pid, relation)


def justification(identifier, conclusion, *premises):
    return Justification(identifier, claim(conclusion), tuple(claim(p) for p in premises),
                         'Explicit test rule for this scope', 'reviewer', 'Supplied dependency')


class DerivationTests(unittest.TestCase):
    def setUp(self):
        self.joint = justification('joint', 'secured', 'closed', 'locked')
        self.audit = justification('audit', 'secured', 'inspection')
        self.graph = DerivationGraph({'closed', 'locked', 'inspection', 'secured'}, (self.joint, self.audit))

    def test_joint_premises_require_all_and_alternatives_require_any(self):
        conclusion = claim('secured')
        self.assertEqual(self.graph.matching_justifications(conclusion, []), ())
        for one in ('closed', 'locked'):
            self.assertEqual(self.graph.matching_justifications(conclusion, [claim(one)]), ())
        self.assertEqual(self.graph.matching_justifications(conclusion, [claim('closed'), claim('locked')]), (self.joint,))
        self.assertEqual(self.graph.matching_justifications(conclusion, [claim('inspection')]), (self.audit,))
        self.assertEqual(self.graph.matching_justifications(conclusion, [claim('closed'), claim('locked'), claim('inspection')]),
                         (self.audit, self.joint))

    def test_explicit_polarity_is_not_absence_or_positive_support(self):
        negative = Justification('negative', claim('secured', 'contradicts'), (claim('locked', 'contradicts'),),
                                 'An explicitly unlocked door is not secured here', 'reviewer', 'Negative premise')
        graph = self.graph.with_justification(negative)
        self.assertEqual(graph.alternatives(claim('secured', 'contradicts')), (negative,))
        self.assertEqual(graph.matching_justifications(claim('secured', 'contradicts'), []), ())
        self.assertEqual(graph.matching_justifications(claim('secured', 'contradicts'), [claim('locked')]), ())
        self.assertEqual(graph.matching_justifications(claim('secured', 'contradicts'), [claim('locked', 'contradicts')]), (negative,))
        self.assertEqual(graph.matching_justifications(claim('secured'), [claim('closed'), claim('locked', 'contradicts')]), ())

    def test_matching_does_not_perform_transitive_inference_or_change_graph(self):
        graph = DerivationGraph({'a', 'b', 'c'}, (justification('ab', 'b', 'a'), justification('bc', 'c', 'b')))
        self.assertTrue(graph.matching_justifications(claim('b'), [claim('a')]))
        self.assertFalse(graph.matching_justifications(claim('c'), [claim('a')]))
        self.assertTrue(graph.matching_justifications(claim('c'), [claim('b')]))
        self.assertEqual(len(graph.justifications), 2)

    def test_direct_and_indirect_cycles_are_rejected_even_with_alternative_grounding(self):
        for sign in Relation:
            with self.subTest(sign=sign), self.assertRaisesRegex(ValueError, 'Circular'):
                Justification('self', claim('a'), (claim('a', sign),), 'rule', 'actor', 'reason')
        graph = DerivationGraph({'a', 'b', 'c', 'ground'},
                                (justification('ab', 'b', 'a'), justification('bc', 'c', 'b'),
                                 justification('grounded', 'a', 'ground')))
        with self.assertRaisesRegex(ValueError, 'Circular'):
            graph.with_justification(justification('ca', 'a', 'c'))
        with self.assertRaisesRegex(ValueError, 'Circular'):
            graph.with_justification(Justification('negative-cycle', claim('a', 'contradicts'),
                (claim('c', 'contradicts'),), 'rule', 'actor', 'reason'))
        self.assertEqual(len(graph.justifications), 3)
        self.assertEqual(graph.topological_order(), ('ground', 'a', 'b', 'c'))

    def test_snapshot_order_is_deterministic_and_diamond_is_valid(self):
        ids = ['a', 'b', 'c', 'd', 'isolated']
        js = [justification('ab', 'b', 'a'), justification('ac', 'c', 'a'), justification('bd', 'd', 'b'), justification('cd', 'd', 'c')]
        one = DerivationGraph(ids, js)
        two = DerivationGraph(list(reversed(ids)), list(reversed(js)))
        self.assertEqual(one, two)
        self.assertEqual(one.topological_order(), two.topological_order())
        self.assertEqual(justification('same', 'd', 'a', 'b'), justification('same', 'd', 'b', 'a'))

    def test_deep_graph_avoids_recursion_limit(self):
        ids = [str(i) for i in range(1500)]
        graph = DerivationGraph(ids, [justification('j' + str(i), ids[i], ids[i-1]) for i in range(1, len(ids))])
        self.assertEqual(graph.topological_order(), tuple(ids))
        with self.assertRaisesRegex(ValueError, 'Circular'):
            graph.with_justification(justification('cycle', ids[0], ids[-1]))

    def test_unknown_references_and_duplicate_identities_fail(self):
        for j in (justification('unknown-premise', 'secured', 'missing'), justification('unknown-conclusion', 'missing', 'closed')):
            with self.assertRaisesRegex(ValueError, 'Unknown'):
                self.graph.with_justification(j)
        with self.assertRaisesRegex(ValueError, 'Duplicate justification'):
            self.graph.with_justification(justification('joint', 'locked', 'closed'))
        with self.assertRaisesRegex(ValueError, 'Duplicate proposition'):
            DerivationGraph(['a', 'a'])
        for conclusion, available in ((claim('missing'), []), (claim('secured'), [claim('missing')]),
                                     (claim('secured'), ['closed']), (claim('secured'), None)):
            with self.assertRaises(ValueError):
                self.graph.matching_justifications(conclusion, available)

    def test_immutable_snapshots_do_not_retain_mutable_input_collections(self):
        premises = [claim('a')]
        j = Justification('j', claim('b'), premises, 'rule', 'actor', 'reason')
        ids, js = ['a', 'b'], [j]
        graph = DerivationGraph(ids, js)
        premises.clear(); ids.clear(); js.clear()
        self.assertEqual(j.premises, (claim('a'),))
        self.assertEqual(graph.proposition_ids, frozenset(('a', 'b')))
        self.assertEqual(graph.justifications, (j,))
        with self.assertRaises(FrozenInstanceError):
            j.rule = 'rewritten'
        with self.assertRaises(FrozenInstanceError):
            graph.justifications = ()

    def test_malformed_records_fail_at_boundary(self):
        for pid in ('', ' ', ' a', 'a ', None, 1):
            with self.subTest(pid=pid), self.assertRaises(ValueError):
                claim(pid)
        for sign in ('uncertain', 'unrelated', None, [], True):
            with self.subTest(sign=sign), self.assertRaises(ValueError):
                claim('a', sign)
        good = dict(id='j', conclusion=claim('b'), premises=(claim('a'),), rule='rule', actor='actor', reason='reason')
        for change in ({'id': ''}, {'conclusion': 'b'}, {'premises': ()}, {'premises': 'a'},
                       {'premises': [claim('a'), claim('a')]}, {'premises': [None]},
                       {'rule': ' '}, {'actor': None}, {'reason': ''}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                Justification(**(good | change))
        for args in [('abc', ()), ({'a'}, 'bad'), ({'a'}, [None]), ([None], ())]:
            with self.assertRaises(ValueError):
                DerivationGraph(*args)

    def test_conflicting_available_stances_remain_explicit_without_explosion(self):
        conflict = Justification('conflict', claim('review'), (claim('a'), claim('a', 'contradicts')),
                                 'Explicitly flag disagreement for review', 'reviewer', 'Conflict rule')
        graph = DerivationGraph({'a', 'review', 'unrelated'}, [conflict])
        supplied = [claim('a'), claim('a', 'contradicts')]
        self.assertEqual(graph.matching_justifications(claim('review'), supplied), (conflict,))
        self.assertEqual(graph.matching_justifications(claim('unrelated'), supplied), ())

    def test_distinct_justifications_are_not_collapsed_or_treated_as_mass(self):
        other = justification('other-review', 'secured', 'closed', 'locked')
        graph = self.graph.with_justification(other)
        matches = graph.matching_justifications(claim('secured'), [claim('closed'), claim('locked'), claim('closed')])
        self.assertEqual(matches, (self.joint, other))
        self.assertEqual(self.graph.justifications, (self.audit, self.joint))
        self.assertEqual(DerivationGraph(set()).topological_order(), ())
