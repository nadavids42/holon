#!/usr/bin/env python3
"""Deterministic acceptance scenarios, with traceable JSON results; no model calls."""
import argparse
from dataclasses import asdict, replace
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import sqlite3
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from holon.domain.projection import (  # noqa: E402
    DYNAMICS_VERSION, ProjectionEvidence, ProjectionPolicy, project_binary,
)
from holon.workspace.metadata import SEMANTICS, policy_payload  # noqa: E402
from holon.workspace.service import Workspace  # noqa: E402

TOLERANCE = 1e-12


def json_value(value):
    return json.loads(json.dumps(value, allow_nan=False))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def expand(case):
    records = []
    for group in case['groups']:
        for i in range(group.get('count', 1)):
            identifier = f"{group['id']}-{i:03d}"
            cluster = group['cluster']
            if group.get('independent', False):
                cluster += f'-{i:03d}'
            records.append(ProjectionEvidence(
                identifier, 'p', cluster, group['relation'], group['mass'],
                group.get('active', True), group.get('exclusion_reason'),
            ))
    return records


def rational_readout(records, policy):
    """Independent exact arithmetic reference, used only for bounded fixtures."""
    active = [r for r in records if r.active]
    eligible = [r for r in active if r.exclusion_reason is None]
    clusters = []
    for cluster in sorted({r.cluster_id for r in eligible}):
        members = sorted((r for r in eligible if r.cluster_id == cluster),
                         key=lambda r: r.evidence_id)
        raw = [sum((Fraction(str(r.mass)) for r in members if r.relation == sign), Fraction())
               for sign in ('supports', 'contradicts')]
        effective = [min(m, Fraction(str(policy.cluster_cap))) for m in raw]
        clusters.append(dict(
            cluster_id=cluster, evidence_ids=[r.evidence_id for r in members],
            raw_support=raw[0], raw_contradiction=raw[1],
            effective_support=effective[0], effective_contradiction=effective[1],
            support_multiplier=effective[0] / raw[0] if raw[0] else Fraction(),
            contradiction_multiplier=effective[1] / raw[1] if raw[1] else Fraction(),
        ))
    positive = sum((c['effective_support'] for c in clusters), Fraction())
    negative = sum((c['effective_contradiction'] for c in clusters), Fraction())
    alpha = Fraction(str(policy.alpha0)) + positive
    beta = Fraction(str(policy.beta0)) + negative
    strength, concentration = positive + negative, alpha + beta
    result = dict(
        proposition_id=records[0].proposition_id if records else 'p',
        dynamics_version=DYNAMICS_VERSION, policy=asdict(policy),
        alpha=alpha, beta=beta, mean=alpha / concentration,
        variance=alpha * beta / (concentration**2 * (concentration + 1)),
        evidence_strength=strength, posterior_concentration=concentration,
        raw_support=sum((c['raw_support'] for c in clusters), Fraction()),
        raw_contradiction=sum((c['raw_contradiction'] for c in clusters), Fraction()),
        effective_support=positive, effective_contradiction=negative,
        conflict_balance=2 * min(positive, negative) / strength if strength else Fraction(),
        opposing_mass=min(positive, negative), active_count=len(active),
        withdrawn_count=len(records) - len(active),
        excluded_count=sum(r.exclusion_reason is not None for r in active),
        evidence_ids=sorted(r.evidence_id for r in eligible),
        withdrawn_ids=sorted(r.evidence_id for r in records if not r.active),
        exclusions=sorted([r.evidence_id, r.exclusion_reason] for r in active
                          if r.exclusion_reason is not None), clusters=clusters,
    )

    def convert(value):
        if isinstance(value, Fraction):
            return float(value)
        if isinstance(value, dict):
            return {k: convert(v) for k, v in value.items()}
        if isinstance(value, list):
            return [convert(v) for v in value]
        return value

    return convert(result)


class AdversarialChecks(unittest.TestCase):
    fixtures = None  # Set by build_suite; no work occurs on import.

    def setUp(self):
        self.checkpoints = {}
        self.temp = tempfile.TemporaryDirectory(prefix='holon-beta-')
        self.addCleanup(self.temp.cleanup)
        self.policy = ProjectionPolicy(**self.fixtures['policy'])

    def workspace(self, name='state'):
        w = Workspace(Path(self.temp.name) / f'{name}.sqlite3')
        self.addCleanup(w.close)
        return w

    def equal_value(self, actual, expected, path='readout'):
        if isinstance(expected, dict):
            self.assertEqual(set(actual), set(expected), path)
            for key in expected:
                self.equal_value(actual[key], expected[key], f'{path}.{key}')
        elif isinstance(expected, list):
            self.assertEqual(len(actual), len(expected), path)
            for i, (a, e) in enumerate(zip(actual, expected)):
                self.equal_value(a, e, f'{path}[{i}]')
        elif isinstance(expected, float):
            self.assertTrue(math.isfinite(actual) and math.isclose(
                actual, expected, rel_tol=TOLERANCE, abs_tol=TOLERANCE),
                f'{path}: {actual!r} != {expected!r}')
        else:
            self.assertEqual(actual, expected, path)

    def project(self, label, records, policy=None):
        policy = policy or self.policy
        value = json_value(asdict(project_binary('p', records, policy)))
        self.checkpoints[label] = dict(inputs=json_value([asdict(r) for r in records]),
                                       readout=value)
        self.equal_value(value, rational_readout(records, policy))
        return value

    def snapshot(self, w, pid, label):
        value = json_value(w.inspect(pid, projection_policy='binary-beta-v1'))
        self.checkpoints[label] = value
        projection = value['projection']
        self.assertEqual(projection['policy_id'], 'binary-beta-v1')
        self.assertEqual(projection['dynamics_version'], 'binary-beta-v1')
        self.assertEqual(projection['policy_digest'], sha256(policy_payload().encode()))
        if projection['readout'] is not None:
            records = [ProjectionEvidence(
                r['id'], pid, r['cluster_id'], r['relation'], r['mass'],
                r['withdrawn_at'] is None,
            ) for r in projection['evidence_metadata']]
            expected = rational_readout(records, self.policy)
            expected['proposition_id'] = pid
            self.equal_value(projection['readout'], expected)
        return value

    @staticmethod
    def dump(w):
        return '\n'.join(w.db.iterdump())

    def rejected_write(self, w, operation, exception=ValueError):
        before = self.dump(w)
        with self.assertRaises(exception):
            operation()
        self.assertEqual(self.dump(w), before, 'Rejected operation changed database')

    def test_fixed_fixtures_and_explanations(self):
        self.assertEqual(self.fixtures['fixture_version'], 'binary-beta-adversarial-v1')
        self.assertEqual(asdict(self.policy), asdict(ProjectionPolicy()))
        self.assertEqual(DYNAMICS_VERSION, 'binary-beta-v1')
        names = [case['name'] for case in self.fixtures['cases']]
        self.assertEqual(set(names), {'prior', 'balanced', 'one', 'independent',
                                     'copies', 'both_signs', 'explanation'})
        self.assertEqual(len(names), len(set(names)))
        for case in self.fixtures['cases']:
            with self.subTest(case=case['name']):
                result = self.project(case['name'], expand(case))
                for field, expected in case['expected'].items():
                    self.equal_value(result[field], expected, f"{case['name']}.{field}")

    def test_ignorance_conflict_and_repetition(self):
        cases = {c['name']: c for c in self.fixtures['cases']}
        results = {name: self.project(name, expand(case)) for name, case in cases.items()}
        self.assertEqual(results['prior']['mean'], results['balanced']['mean'])
        self.assertLess(results['balanced']['variance'], results['prior']['variance'])
        self.assertEqual(results['copies']['effective_support'], results['one']['effective_support'])
        self.assertEqual(results['copies']['clusters'][0]['support_multiplier'], 1 / 500)
        self.assertGreater(results['independent']['evidence_strength'], results['one']['evidence_strength'])

    def test_permutations_partitions_and_directionality(self):
        rng = random.Random(self.fixtures['seed'])
        records = [ProjectionEvidence(str(i), 'p', f'cluster-{i % 9}',
                   rng.choice(['supports', 'contradicts']), rng.randrange(0, 17) / 8)
                   for i in range(100)]
        expected = self.project('original', records)
        for _ in range(25):
            rng.shuffle(records)
            self.equal_value(json_value(asdict(project_binary('p', records))), expected)
        for count in (1, 2, 3, 7, 17):
            partitions = [records[i::count] for i in range(count)]
            combined = [record for partition in partitions for record in partition]
            self.equal_value(json_value(asdict(project_binary('p', combined))), expected)
        pair = [ProjectionEvidence(str(i), 'p', 'shared', 'supports', .75) for i in range(2)]
        joined = self.project('joined_raw_partitions', pair)
        wrong = sum(project_binary('p', [r]).effective_support for r in pair)
        self.assertEqual(joined['effective_support'], 1)
        self.assertEqual(wrong, 1.5)
        self.checkpoints['incorrect_sum_of_capped_partitions'] = wrong
        running = []
        for record in records:
            before = project_binary('p', running).mean
            running.append(record)
            after = project_binary('p', running).mean
            if record.relation == 'supports':
                self.assertGreaterEqual(after + TOLERANCE, before)
            else:
                self.assertLessEqual(after - TOLERANCE, before)

    def test_keyed_retry_and_changed_request(self):
        w = self.workspace()
        pid = w.create_proposition('Door closed', 'T0')
        args = dict(mass=.75, event_key='reading-001')
        first = w.add_report(pid, 'A', 'Closed', 'supports', **args)
        before = self.dump(w)
        for _ in range(20):
            self.assertEqual(w.add_report(pid, 'A', 'Closed', 'supports', **args), first)
        self.assertEqual(self.dump(w), before)
        self.rejected_write(w, lambda: w.add_report(pid, 'A', 'Changed', 'supports', **args))
        state = self.snapshot(w, pid, 'after_retries')
        self.assertEqual(len(state['evidence']), 1)
        self.assertEqual(len(state['history']), 1)
        self.assertEqual(state['projection']['readout']['raw_support'], .75)

    def test_shared_lineage_correction_and_reinterpretation(self):
        w = self.workspace()
        pid = w.create_proposition('Door closed', 'T0')
        shared = dict(cluster_id='original', cluster_actor='fixture', cluster_reason='Declared copy')
        first = w.add_report(pid, 'A', 'Closed', 'supports', **shared)
        second = w.add_report(pid, 'B', 'Closed copy', 'supports', **shared)
        initial = self.snapshot(w, pid, 'initial')
        self.assertEqual(initial['projection']['readout']['effective_support'], 1)
        corrected = w.withdraw_evidence(first['evidence_id'], 'fixture', 'Wrong transcription',
                                       report='Open', source='C', relation='contradicts', mass=.5,
                                       event_key='correction')
        correction = self.snapshot(w, pid, 'corrected')
        self.assertEqual(correction['status'], 'contested')
        self.assertEqual(correction['history'][0], initial['history'][0])
        self.assertEqual(len(correction['projection']['readout']['clusters']), 1)
        self.assertEqual(correction['projection']['readout']['effective_contradiction'], .5)
        self.assertNotEqual(corrected['observation_id'], first['observation_id'])
        before = self.dump(w)
        self.assertEqual(w.withdraw_evidence(first['evidence_id'], 'fixture', 'Wrong transcription',
                         report='Open', source='C', relation='contradicts', mass=.5,
                         event_key='correction'), corrected)
        self.assertEqual(self.dump(w), before)
        other = w.create_proposition('Door locked', 'T0')
        w.link_observation(second['observation_id'], other, 'supports')
        other_before = w.inspect(other, projection_policy='binary-beta-v1')
        replacement = w.reinterpret_evidence(second['evidence_id'], 'contradicts', 'fixture',
                                            'Wrong relation', event_key='reinterpretation')
        self.assertEqual(replacement['observation_id'], second['observation_id'])
        self.assertEqual(w.inspect(other, projection_policy='binary-beta-v1'), other_before)
        state = self.snapshot(w, pid, 'reinterpreted')
        self.assertEqual(state['status'], 'opposed')
        self.assertEqual(len(state['projection']['readout']['clusters']), 1)
        self.assertEqual(state['projection']['readout']['effective_contradiction'], 1)
        self.assertEqual(state['projection']['readout']['raw_contradiction'], 1.5)
        self.assertEqual([h['status'] for h in state['history']],
                         ['supported', 'supported', 'contested', 'opposed'])
        links = {e['id']: e for e in state['evidence']}
        self.assertEqual(links[first['evidence_id']]['report'], 'Closed')
        self.assertEqual(links[first['evidence_id']]['replacement_evidence_id'],
                         corrected['replacement_evidence_id'])
        self.assertEqual(links[second['evidence_id']]['replacement_evidence_id'],
                         replacement['replacement_evidence_id'])

    def test_all_withdrawn_returns_prior(self):
        w = self.workspace()
        pid = w.create_proposition('Door closed', 'T0')
        prior = w.project(pid)['readout']
        for source, sign in [('A', 'supports'), ('B', 'contradicts')]:
            w.add_report(pid, source, sign, sign)
        for evidence in w.inspect(pid)['evidence']:
            w.withdraw_evidence(evidence['id'], 'fixture', 'Withdraw all')
        state = self.snapshot(w, pid, 'all_withdrawn')
        result = state['projection']['readout']
        for field in ('alpha', 'beta', 'mean', 'variance', 'evidence_strength',
                      'posterior_concentration', 'opposing_mass', 'conflict_balance'):
            self.assertEqual(result[field], prior[field], field)
        self.assertEqual(state['status'], 'insufficient_evidence')
        self.assertEqual(result['withdrawn_count'], 2)
        self.assertEqual(len(state['evidence']), 2)
        self.assertEqual(len(state['history']), 4)
        # Also verify a non-default configured prior in the pure projector.
        policy = ProjectionPolicy('custom-prior', 2, 3, 1)
        records = [ProjectionEvidence('withdrawn', 'p', 'A', 'supports', 7, active=False)]
        self.assertEqual(self.project('custom_prior', records, policy)['mean'], .4)

    def test_qualitative_and_quantitative_divergence(self):
        w = self.workspace()
        pid = w.create_proposition('Door closed', 'T0')
        w.add_report(pid, 'A', 'Closed', 'supports', mass=0)
        zero = self.snapshot(w, pid, 'zero_mass')
        self.assertEqual(zero['status'], 'supported')
        self.assertEqual(zero['projection']['readout']['mean'], .5)
        self.assertEqual(zero['projection']['readout']['evidence_strength'], 0)
        w.add_report(pid, 'B', 'Closed', 'supports')
        w.add_report(pid, 'C', 'Open', 'contradicts', mass=.25)
        contested = self.snapshot(w, pid, 'favored_but_contested')
        self.assertEqual(contested['status'], 'contested')
        self.assertGreater(contested['projection']['readout']['mean'], .5)

    def test_restart_cli_and_read_only_inspection(self):
        w = self.workspace()
        path = Path(self.temp.name) / 'state.sqlite3'
        pid = w.create_proposition('Door closed', 'T0')
        w.add_report(pid, 'A', 'Closed', 'supports', mass=.75)
        expected = self.snapshot(w, pid, 'before_restart')
        changes, before, raw = w.db.total_changes, self.dump(w), path.read_bytes()
        for _ in range(5):
            self.assertEqual(json_value(w.project(pid)), expected['projection'])
            self.assertEqual(json_value(w.inspect(pid, projection_policy='binary-beta-v1')), expected)
        self.assertEqual(w.db.total_changes, changes)
        self.assertEqual(self.dump(w), before)
        self.assertEqual(path.read_bytes(), raw)
        w.close()
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), PYTHONDONTWRITEBYTECODE='1')
        for command in (['project', pid], ['inspect', pid, '--projection']):
            result = subprocess.run([sys.executable, '-m', 'holon.cli', '--db', str(path), *command],
                                    env=env, cwd=ROOT, check=True, capture_output=True, text=True,
                                    timeout=30)
            self.assertEqual(json.loads(result.stdout),
                             expected['projection'] if command[0] == 'project' else expected)
        reopened = self.workspace()
        self.assertEqual(self.snapshot(reopened, pid, 'after_restart'), expected)
        self.assertEqual(self.dump(reopened), before)
        self.assertEqual(path.read_bytes(), raw)

    def test_legacy_copy_and_explicit_assumptions(self):
        original = Path(self.temp.name) / 'legacy.sqlite3'
        copy = Path(self.temp.name) / 'copy.sqlite3'
        with sqlite3.connect(original) as db:
            db.executescript((HERE / 'legacy-v0.sql').read_text())
        original_bytes = original.read_bytes()
        with sqlite3.connect(original) as src, sqlite3.connect(copy) as dst:
            src.backup(dst)
        w = self.workspace('copy')
        before = self.snapshot(w, 'legacy-p', 'missing_metadata')
        self.assertEqual(before['projection']['replay_coverage'], 'replay_incomplete')
        self.assertIsNone(before['projection']['readout'])
        self.assertEqual(before['projection']['missing_metadata_ids'], ['legacy-e'])
        self.assertEqual(before['history'][0]['sequence'], 7)
        self.assertIsNone(before['evidence'][0]['observed_at'])
        self.assertEqual(w.migrate_impacts('legacy-p', 'fixture', 'Stipulated units')['annotated_count'], 1)
        annotated = self.snapshot(w, 'legacy-p', 'annotated')
        self.assertEqual(annotated['projection']['replay_coverage'], 'replay_approximate')
        self.assertEqual(annotated['history'], before['history'])
        self.assertEqual(annotated['evidence'], before['evidence'])
        self.assertEqual(annotated['projection']['readout']['effective_support'], 1)
        dump = self.dump(w)
        self.assertEqual(w.migrate_impacts('legacy-p', 'fixture', 'Retry')['annotated_count'], 0)
        self.assertEqual(self.dump(w), dump)
        self.assertEqual(w.db.execute('PRAGMA user_version').fetchone()[0], 3)
        self.assertEqual(w.db.execute('PRAGMA foreign_key_check').fetchall(), [])
        self.assertEqual(original.read_bytes(), original_bytes)

    def test_invalid_inputs_and_numeric_range(self):
        for mass in (-1, math.nan, math.inf, -math.inf, True, '1', 10**1000):
            with self.assertRaises(ValueError):
                ProjectionEvidence('e', 'p', 'c', 'supports', mass)
        for field in ('alpha0', 'beta0', 'cluster_cap'):
            for value in (0, -1, math.nan, math.inf, True, '1', 10**1000):
                with self.assertRaises(ValueError):
                    ProjectionPolicy(**{field: value})
        good = ProjectionEvidence('e', 'p', 'c', 'supports')
        for kwargs in ({'evidence_id': ''}, {'cluster_id': ' '}, {'relation': 'uncertain'},
                       {'active': 1}, {'exclusion_reason': ''}):
            with self.assertRaises(ValueError):
                replace(good, **kwargs)
        for records in ([good, good], [replace(good, proposition_id='other')], [object()]):
            with self.assertRaises(ValueError):
                project_binary('p', records)
        with self.assertRaises(ValueError):
            ProjectionPolicy(alpha0=1e308, beta0=1e308)
        for records, policy in [
            ([replace(good, mass=1e308), replace(good, evidence_id='f', mass=1e308)], self.policy),
            ([replace(good, mass=1e308)], ProjectionPolicy(alpha0=1e308, cluster_cap=1e308)),
        ]:
            with self.assertRaises(ValueError):
                project_binary('p', records, policy)
        self.project('large_finite', [replace(good, mass=1e300)],
                     ProjectionPolicy(cluster_cap=1e300))

    def test_atomic_write_failures_and_overflow_reads(self):
        w = self.workspace()
        pid = w.create_proposition('Door closed', 'T0')
        old = w.add_report(pid, 'A', 'Closed', 'supports')['evidence_id']
        for mass in (-1, math.nan, math.inf, True, '1', 10**1000):
            self.rejected_write(w, lambda m=mass: w.add_report(pid, 'B', 'Open', 'contradicts', mass=m))
            self.rejected_write(w, lambda m=mass: w.withdraw_evidence(
                old, 'fixture', 'Bad mass', report='Open', source='B', relation='contradicts', mass=m))
        # A late revision failure occurs after observations/links/impacts were inserted.
        w.db.execute("CREATE TRIGGER fail_revision BEFORE INSERT ON revisions BEGIN SELECT RAISE(ABORT,'injected failure'); END")
        for operation in (
            lambda: w.add_report(pid, 'B', 'Open', 'contradicts'),
            lambda: w.withdraw_evidence(old, 'fixture', 'Correction', report='Open', source='B', relation='contradicts'),
            lambda: w.reinterpret_evidence(old, 'contradicts', 'fixture', 'Reinterpretation'),
        ):
            self.rejected_write(w, operation, sqlite3.IntegrityError)
        w.db.execute('DROP TRIGGER fail_revision')
        self.snapshot(w, pid, 'after_rejected_writes')
        w.add_report(pid, 'large', 'Large 1', 'supports', mass=1e308)
        last = w.add_report(pid, 'large', 'Large 2', 'supports', mass=1e308)
        before = self.dump(w)
        for operation in (lambda: w.project(pid), lambda: w.inspect(pid, projection_policy='binary-beta-v1')):
            with self.assertRaises(ValueError):
                operation()
            self.assertEqual(self.dump(w), before)
        w.withdraw_evidence(last['evidence_id'], 'fixture', 'Restore representable aggregate')
        self.snapshot(w, pid, 'recovered_after_overflow')

    def test_atomic_migration_failure(self):
        path = Path(self.temp.name) / 'broken.sqlite3'
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE impact_migrations (unexpected TEXT)')
            before = '\n'.join(db.iterdump())
        with self.assertRaises(sqlite3.OperationalError):
            Workspace(path)
        with sqlite3.connect(path) as db:
            self.assertEqual('\n'.join(db.iterdump()), before)
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 0)
        self.checkpoints['migration_failure'] = {'original_schema_preserved': True, 'schema_version': 0}


class RecordingResult(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.scenarios = []

    def startTest(self, test):
        super().startTest(test)
        self.offsets = (len(self.failures), len(self.errors))

    def stopTest(self, test):
        failures = self.failures[self.offsets[0]:] + self.errors[self.offsets[1]:]
        self.scenarios.append(dict(
            name=test._testMethodName.removeprefix('test_'),
            passed=not failures,
            errors=[detail for _, detail in failures],
            checkpoints=getattr(test, 'checkpoints', {}),
        ))
        super().stopTest(test)


def build_suite(fixtures):
    class ConfiguredChecks(AdversarialChecks):
        pass
    ConfiguredChecks.fixtures = fixtures
    return unittest.defaultTestLoader.loadTestsFromTestCase(ConfiguredChecks)


def manifest(fixture_path):
    paths = [Path(__file__).resolve(), fixture_path, HERE / 'protocol.md', HERE / 'legacy-v0.sql']
    paths += sorted((ROOT / 'src' / 'holon').rglob('*.py'))
    hashes = {}
    for path in paths:
        name = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        hashes[name] = sha256(path.read_bytes())
    git = {}
    for label, args in [('commit', ['rev-parse', 'HEAD']), ('status', ['status', '--porcelain'])]:
        try:
            result = subprocess.run(['git', *args], cwd=ROOT, text=True, capture_output=True,
                                    check=True, timeout=10)
            git[label] = result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            git[label] = None
    return dict(python=platform.python_version(), sqlite=sqlite3.sqlite_version, git=git,
                hashes=hashes, policy=json.loads(policy_payload()), dynamics_version=DYNAMICS_VERSION,
                mass_semantics=SEMANTICS, tolerance=TOLERANCE)


def explanation(report):
    scenario = next((s for s in report['scenarios'] if s['name'] == 'fixed_fixtures_and_explanations'), None)
    example = scenario['checkpoints'].get('explanation') if scenario else None
    if not example:
        return '# Explanation unavailable\n\nSee results.json for failed scenario details.\n'
    value = example['readout']
    alpha, beta = Fraction(str(value['alpha'])), Fraction(str(value['beta']))
    concentration = alpha + beta
    exact_mean = alpha / concentration
    exact_variance = alpha * beta / (concentration**2 * (concentration + 1))
    strength = value['evidence_strength']
    lines = ['# Binary Beta explanation', '',
             'This is stipulated evidence impact, not calibrated truth probability.', '',
             f"Validation passed: {report['passed']}. Policy: `{value['policy']['version']}`.", '',
             '## Supplied evidence', '', '| ID | Cluster | Relation | Mass | Disposition |',
             '| --- | --- | --- | --- | --- |']
    for r in example['inputs']:
        disposition = 'withdrawn' if not r['active'] else (r['exclusion_reason'] or 'contributing')
        lines.append(f"| {r['evidence_id']} | {r['cluster_id']} | {r['relation']} | {r['mass']} | {disposition} |")
    lines += ['', '## Cluster contributions', '',
              '| Cluster | Evidence IDs | Raw + / − | Effective + / − | Multipliers + / − |',
              '| --- | --- | --- | --- | --- |']
    for c in value['clusters']:
        lines.append(f"| {c['cluster_id']} | {', '.join(c['evidence_ids'])} | {c['raw_support']} / {c['raw_contradiction']} | {c['effective_support']} / {c['effective_contradiction']} | {c['support_multiplier']} / {c['contradiction_multiplier']} |")
    lines += ['', '## Readout', '',
              f"Each sign is capped separately at {value['policy']['cluster_cap']} per cluster.",
              'Raw masses are the sums of eligible input masses for that cluster and sign.',
              'Effective masses are capped raw masses; multipliers are effective/raw',
              '(zero when raw mass is zero). Zero-mass records retain provenance.',
              'Withdrawn and excluded records add no mass; withdrawal takes precedence.', '',
              f"`alpha = {value['policy']['alpha0']} + {value['effective_support']} = {value['alpha']}`; "
              f"`beta = {value['policy']['beta0']} + {value['effective_contradiction']} = {value['beta']}`.",
              f'`mean = alpha / (alpha + beta) = {exact_mean}`; '
              f'`variance = alpha × beta / ((alpha + beta)² × (alpha + beta + 1)) = {exact_variance}`.',
              f"`strength = {value['effective_support']} + {value['effective_contradiction']} = {strength}`; "
              f"concentration includes the prior: `{value['posterior_concentration']}`.",
              f"`opposing_mass = min(effective_support, effective_contradiction) = {value['opposing_mass']}`; "
              f"`conflict_balance = 2 × opposing_mass / strength = {value['conflict_balance']}` "
              '(zero when strength is zero).',
              f"{value['active_count']} active links include {value['excluded_count']} excluded; "
              f"{value['withdrawn_count']} withdrawn links are disjoint from both.",
              f"{len(value['evidence_ids'])} IDs contribute, including any zero-mass records.", '',
              'Exact recorded readout (also checked against rational arithmetic):', '',
              '```json', json.dumps(value, indent=2, allow_nan=False), '```', '',
              'Explicit exclusion is a pure-projector input; current workspace APIs do not',
              'persist this exclusion mechanism. This example does not add that capability.', '']
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, default=HERE / 'fixtures.json')
    parser.add_argument('--output', type=Path, help='New output directory for results.json and explanation.md')
    args = parser.parse_args(argv)
    try:
        # Refuse overwriting any existing run, including accidentally selected source directories.
        if args.output is not None and args.output.exists():
            raise ValueError(f'Output directory already exists: {args.output}')
        fixture_path = args.fixtures.resolve()
        fixtures = json.loads(fixture_path.read_text())
        metadata = manifest(fixture_path)
        result = RecordingResult()
        build_suite(fixtures).run(result)
        report = dict(report_version='binary-beta-adversarial-v1', passed=result.wasSuccessful(),
                      fixture_version=fixtures.get('fixture_version'), seed=fixtures.get('seed'),
                      manifest=metadata, scenario_count=result.testsRun, scenarios=result.scenarios)
        encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n'
        if args.output is None:
            print(encoded, end='')
        else:
            args.output.mkdir(parents=True, exist_ok=False)
            (args.output / 'results.json').write_text(encoded)
            (args.output / 'explanation.md').write_text(explanation(report))
            passed = sum(s['passed'] for s in result.scenarios)
            print(f"{passed}/{result.testsRun} scenarios passed; results: {args.output / 'results.json'}")
        return 0 if result.wasSuccessful() else 1
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
