"""Fault injection for host-display restoration; never accesses the real bus."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from gi.repository import GLib
import mutter_scaling_probe as probe


def state():
    return dict(configSerial=7,
        monitors=[dict(connector='owned-fixture', configProperties={}, currentModes=[dict(
            id='fixture-mode', width=1920, height=1080, refresh=60.0,
            preferredScale=1.0, supportedScales=[1.0, 1.25, 1.5, 2.0])])],
        logicalMonitors=[dict(x=0, y=0, scale=1.0, transform=0, primary=True, connectors=['owned-fixture'])],
        properties={'renderer': 'xrandr', 'layout-mode': 2})


class Settings:
    def __init__(self, user=None, reset_error=False):
        self.user = user
        self.reset_error = reset_error
    def get_strv(self, key): return self.user.unpack() if self.user is not None else []
    def get_user_value(self, key): return self.user
    def is_writable(self, key): return True
    def set_strv(self, key, value): self.user = GLib.Variant('as', value); return True
    def set_value(self, key, value): self.user = value; return True
    def reset(self, key):
        if self.reset_error: raise RuntimeError('fixture reset failure')
        self.user = None


class Restoration(unittest.TestCase):
    def execute(self, settings, trial=True, drift=False, apply_error=False):
        before = state()
        after = copy.deepcopy(before)
        if drift: after['logicalMonitors'][0]['x'] = 100
        calls = []
        def apply(display, baseline, method):
            calls.append(method)
            if method == 1 and apply_error: raise RuntimeError('fixture display restore failure')
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(probe, 'snapshot', return_value=before), \
                patch.object(probe, 'settled', return_value=after), \
                patch.object(probe, 'apply', side_effect=apply), \
                patch.object(probe.Gio.Settings, 'sync'):
            output = Path(folder) / 'result.json'
            result = probe.execute(output, trial, False, object(), settings)
            self.assertEqual(json.loads(output.read_text()), result)
        return result, calls

    def test_unset_and_explicit_user_values_are_restored_distinctly(self):
        for original in (None, GLib.Variant('as', []), GLib.Variant('as', ['fixture-feature'])):
            with self.subTest(original=original):
                settings = Settings(original)
                report, calls = self.execute(settings)
                self.assertTrue(report['passed'])
                self.assertTrue(probe.same_user_value(settings, original))
                self.assertEqual(calls, [0])

    def test_settings_restore_failure_preserves_report_and_failure(self):
        report, calls = self.execute(Settings(reset_error=True))
        self.assertFalse(report['passed'])
        self.assertFalse(report['userValueRestored'])
        self.assertIn('fixture reset failure', report['restoreErrors'][0])
        self.assertEqual(calls, [0])

    def test_display_restore_failure_preserves_report_and_settings_restore(self):
        report, calls = self.execute(Settings(), drift=True, apply_error=True)
        self.assertFalse(report['passed'])
        self.assertTrue(report['userValueRestored'])
        self.assertIn('fixture display restore failure', report['restoreErrors'][0])
        self.assertEqual(calls, [0, 1])

    def test_read_only_does_not_restore_an_external_topology_change(self):
        report, calls = self.execute(Settings(), trial=False, drift=True)
        self.assertFalse(report['passed'])
        self.assertFalse(report['featureMutationAttempted'])
        self.assertEqual(calls, [])

    def test_payload_omits_layout_mode_unless_compositor_supports_setting_it(self):
        baseline = state()
        payload = probe.configuration(baseline, 9, 0).unpack()
        self.assertEqual(payload[:2], (9, 0))
        self.assertEqual(payload[3], {})
        self.assertEqual(payload[2][0][5][0][:2], ('owned-fixture', 'fixture-mode'))
        baseline['properties']['supports-changing-layout-mode'] = True
        self.assertEqual(probe.configuration(baseline, 9, 0).unpack()[3], {'layout-mode': 2})
        with self.assertRaises(AssertionError): probe.configuration(baseline, 9, 2)

    def test_fractional_guard_rejects_empty_active_set_and_ignores_disabled_output(self):
        baseline = state()
        baseline['logicalMonitors'] = []
        with self.assertRaises(AssertionError): probe.fractional_advertised(baseline)
        baseline = state()
        baseline['monitors'].append(dict(connector='disabled-fixture', configProperties={}, currentModes=[]))
        self.assertTrue(probe.fractional_advertised(baseline))
        baseline['monitors'][0]['currentModes'][0]['supportedScales'] = [1.0, 2.0]
        self.assertFalse(probe.fractional_advertised(baseline))


if __name__ == '__main__': unittest.main()
