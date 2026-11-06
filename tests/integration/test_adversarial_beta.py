"""Exercise the experiment as a real command, including failure reporting."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = ROOT / 'experiments' / '002-binary-beta'


class AdversarialRunnerTests(unittest.TestCase):
    def invoke(self, *args, optimized=False):
        command = [sys.executable]
        if optimized:
            command.append('-O')
        command += [str(EXPERIMENT / 'run.py'), *map(str, args)]
        return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))

    def test_full_run_artifacts_and_reproducible_fixture_readouts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'run'
            completed = self.invoke('--output', output)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            report = json.loads((output / 'results.json').read_text())
            self.assertTrue(report['passed'])
            self.assertEqual(report['scenario_count'], 12)
            self.assertEqual(len(report['scenarios']), 12)
            self.assertTrue(all(s['passed'] and not s['errors'] for s in report['scenarios']))
            self.assertEqual(report['manifest']['dynamics_version'], 'binary-beta-v1')
            self.assertIn('experiments/002-binary-beta/fixtures.json', report['manifest']['hashes'])
            self.assertIn('src/holon/domain/projection.py', report['manifest']['hashes'])
            explanation = (output / 'explanation.md').read_text()
            for text in ('a-000', 'e-000', '4/7', '8/147', 'not calibrated'):
                self.assertIn(text, explanation)
            repeated = self.invoke()
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            second = json.loads(repeated.stdout)
            def fixtures(result):
                return next(s['checkpoints'] for s in result['scenarios']
                            if s['name'] == 'fixed_fixtures_and_explanations')
            self.assertEqual(fixtures(report), fixtures(second))
            # Existing results must not be silently replaced.
            original = (output / 'results.json').read_bytes()
            refused = self.invoke('--output', output)
            self.assertEqual(refused.returncode, 2)
            self.assertEqual((output / 'results.json').read_bytes(), original)

    def test_wrong_expectation_fails_even_under_optimization(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = json.loads((EXPERIMENT / 'fixtures.json').read_text())
            fixture['cases'][0]['expected']['mean'] = .9
            path = Path(directory) / 'wrong.json'
            path.write_text(json.dumps(fixture))
            output = Path(directory) / 'failed-run'
            completed = self.invoke('--fixtures', path, '--output', output, optimized=True)
            self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
            report = json.loads((output / 'results.json').read_text())
            self.assertFalse(report['passed'])
            self.assertEqual(report['scenario_count'], 12)
            failed = [s for s in report['scenarios'] if not s['passed']]
            self.assertEqual([s['name'] for s in failed], ['fixed_fixtures_and_explanations'])
            self.assertIn('prior.mean', '\n'.join(failed[0]['errors']))
            self.assertIn('Validation passed: False', (output / 'explanation.md').read_text())

    def test_missing_or_malformed_fixture_fails_without_success_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixtures.json'
            output = Path(directory) / 'output'
            missing = self.invoke('--fixtures', path, '--output', output)
            self.assertEqual(missing.returncode, 2)
            self.assertFalse(output.exists())
            path.write_text('{invalid JSON')
            malformed = self.invoke('--fixtures', path, '--output', output)
            self.assertEqual(malformed.returncode, 2)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
