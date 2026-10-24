import unittest
from holon.domain.records import BeliefStatus, Relation, belief_status


class PolicyTests(unittest.TestCase):
    def test_evidence_presence_policy(self):
        self.assertEqual(belief_status({Relation.SUPPORTS}), BeliefStatus.SUPPORTED)
        self.assertEqual(belief_status({Relation.CONTRADICTS}), BeliefStatus.OPPOSED)
        self.assertEqual(belief_status(set(Relation)), BeliefStatus.CONTESTED)
        with self.assertRaises(ValueError):
            belief_status(set())
