"""Browser adapter logic tested in Node; no live DOM or model required."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which('node'), 'Node is required for browser logic checks')
class StructureUITests(unittest.TestCase):
    def check_js(self, assertions):
        script = Path(__file__).resolve().parents[2] / 'src/holon/web/static/structure.js'
        result = subprocess.run(
            ['node', '-e', "const assert = require('node:assert/strict');\n" + script.read_text() + '\n' + assertions],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_signed_premises_and_conclusion_keep_distinct_roles(self):
        self.check_js("""
const row = (id, sign) => ({claim: {value: id}, sign: {value: sign}});
const result = derivationArguments({relation: 'contradicts', rule: 'rule', justification_id: 'stable'}, 'c',
  [row('a', 'supports'), row('b', 'contradicts')]);
assert.deepEqual(result, {rule: 'rule', justification_id: 'stable',
  conclusion: {proposition_id: 'c', relation: 'contradicts'},
  premises: [{proposition_id: 'a', relation: 'supports'}, {proposition_id: 'b', relation: 'contradicts'}]});
""")

    def test_invalid_premise_sets_are_rejected_before_submission(self):
        self.check_js("""
const row = id => ({claim: {value: id}, sign: {value: 'supports'}});
for (const rows of [[], [row('')], [row('c')], [row('a'), row('a')]]) {
  assert.throws(() => derivationArguments({relation: 'supports'}, 'c', rows));
}
""")

    def test_merge_preview_includes_target_members_and_excludes_unknown(self):
        self.check_js("""
const ledger = {assignments: {a: 'first', b: 'second', c: 'first', d: null, e: 'other'}};
assert.deepEqual(originGroups(ledger), [['first', ['a', 'c']], ['other', ['e']], ['second', ['b']]]);
assert.deepEqual(mergeChanges(ledger, ['first', 'second'], 'first'), [
  {observation_id: 'a', before: 'first', after: 'first'},
  {observation_id: 'b', before: 'second', after: 'first'},
  {observation_id: 'c', before: 'first', after: 'first'}]);
assert.equal(ledger.assignments.b, 'second');
assert.equal(ledger.assignments.d, null);
""")

    def test_reversal_controls_follow_heads_and_prior_reversals(self):
        self.check_js("""
const event = {id: 'merge', kind: 'merge', changes: [{observation_id: 'a'}, {observation_id: 'b'}]};
const ledger = {events: [event], heads: {a: 'merge', b: 'merge'}};
assert.equal(lineageEventState(event, ledger).reversible, true);
ledger.heads.a = 'later';
assert.equal(lineageEventState(event, ledger).reversible, false);
ledger.heads.a = 'merge';
const reverse = {kind: 'reverse', target_event_id: 'merge'};
ledger.events.push(reverse);
assert.equal(lineageEventState(event, ledger).label, 'Reversed');
assert.equal(lineageEventState(reverse, ledger).reversible, false);
""")

    def test_labels_show_scope_sign_and_unknown_observation_time(self):
        self.check_js("""
assert.equal(signedLabel({proposition_id: 'a', relation: 'contradicts'},
  [{id: 'a', claim: 'Closed', scope: 'Lab at T0'}]), 'Opposition to: Closed · Lab at T0');
assert.equal(observationLabel('o', {observations: [{id: 'o', source: 'A', report: 'Closed', observed_at: null}]}),
  'A · Closed · observed unknown');
""")
