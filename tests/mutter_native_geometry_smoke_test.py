"""Fault injection for native DPI orchestration; no real bus/display access."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from gi.repository import GLib
import mutter_native_geometry_smoke as runner
from mutter_scaling_probe_test import state, Settings


class NativeRestoration(unittest.TestCase):
    def execute(self, failure, settings=None):
        settings = settings or Settings()
        before = state()
        second = copy.deepcopy(before['monitors'][0])
        second['connector'] = 'second-fixture'
        before['monitors'].append(second)
        before['logicalMonitors'].append(dict(x=1920, y=0, scale=1., transform=0,
            primary=False, connectors=['second-fixture']))
        during = copy.deepcopy(before)
        during['properties'].update({'layout-mode': 3, 'supports-changing-layout-mode': True})
        current = copy.deepcopy(before)
        calls = []

        def apply(display, desired, method):
            nonlocal current
            calls.append((method, copy.deepcopy(desired)))
            if method == 0 and len(calls) == 2 and failure == 'verify':
                raise RuntimeError('fixture VERIFY rejected')
            if method == 1:
                if failure == 'restore' and len(calls) > 3:
                    raise RuntimeError('fixture restore rejected')
                current = copy.deepcopy(desired)

        def worker(command, **kwargs):
            if failure == 'interrupt':
                runner.m.interrupted(15, None)
            if failure == 'timeout':
                raise runner.subprocess.TimeoutExpired(command, 40)
            root = Path(command[3])
            (root / 'result.json').write_text(json.dumps(dict(passed=False, error='fixture worker failed')))
            return SimpleNamespace(returncode=1)

        with tempfile.TemporaryDirectory() as folder, \
                patch.object(runner.tempfile, 'mkdtemp', return_value=folder), \
                patch.object(runner.m, 'proxy', return_value=object()), \
                patch.object(runner.Gio.Settings, 'new', return_value=settings), \
                patch.object(runner.Gio.Settings, 'sync'), \
                patch.object(runner.m, 'snapshot', side_effect=lambda _: copy.deepcopy(current)), \
                patch.object(runner.m, 'settled', side_effect=lambda *_: copy.deepcopy(current)), \
                patch.object(runner.m, 'apply', side_effect=apply), \
                patch.object(runner, 'wait', return_value=during), \
                patch.object(runner.time, 'sleep'), \
                patch.object(runner.subprocess, 'check_output', return_value='(true,)' if failure == 'locked' else '(false,)'), \
                patch.object(runner.subprocess, 'run', side_effect=worker):
            result = runner.run()
            self.assertEqual(json.loads((Path(folder) / 'result.json').read_text()), result)
        return result, calls

    def test_worker_error_timeout_and_interrupt_restore_modes_and_features(self):
        for failure in ('worker', 'timeout', 'interrupt'):
            for original in (None, GLib.Variant('as', [])):
                with self.subTest(failure=failure, original=original):
                    result, calls = self.execute(failure, Settings(original))
                    self.assertFalse(result['passed'])
                    self.assertTrue(result['topologyRestored'])
                    self.assertTrue(result['userValueRestored'])
                    self.assertTrue(result['capabilitiesRestored'])
                    self.assertEqual([method for method, _ in calls], [0, 0, 1, 1])
                    requested = calls[1][1]
                    self.assertEqual([monitor['x'] for monitor in requested['logicalMonitors']], [0, 3072])
                    self.assertEqual([monitor['scale'] for monitor in requested['logicalMonitors']], [1.25, 1.25])
                    self.assertEqual(requested['monitors'], calls[0][1]['monitors'], 'Scaling must retain saved mode and refresh')

    def test_locked_desktop_never_mutates_features_or_topology(self):
        result, calls = self.execute('locked')
        self.assertFalse(result['passed'])
        self.assertFalse(result['featureMutationAttempted'])
        self.assertFalse(result['topologyMutationAttempted'])
        self.assertEqual(calls, [])

    def test_verify_rejection_never_applies_requested_layout(self):
        result, calls = self.execute('verify')
        self.assertFalse(result['passed'])
        self.assertTrue(result['userValueRestored'])
        self.assertEqual([method for method, _ in calls], [0, 0])

    def test_setting_restore_failure_still_attempts_topology_restore(self):
        result, calls = self.execute('worker', Settings(reset_error=True))
        self.assertFalse(result['passed'])
        self.assertTrue(result['topologyRestored'])
        self.assertFalse(result['userValueRestored'])
        self.assertIn('Settings:', result['restoreErrors'][0])
        self.assertEqual([method for method, _ in calls], [0, 0, 1, 1])

    def test_display_restore_failure_preserves_feature_restore_and_report(self):
        result, calls = self.execute('restore')
        self.assertFalse(result['passed'])
        self.assertTrue(result['userValueRestored'])
        self.assertFalse(result['topologyRestored'])
        self.assertIn('Display:', result['restoreErrors'][0])


if __name__ == '__main__': unittest.main()
