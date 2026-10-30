#!/usr/bin/python3
"""Mutter capability survey and opt-in reversible fractional-feature trial.

Read-only by default. --verify-restore asks Mutter to VERIFY (method 0) the
saved configuration without applying it. The opt-in feature trial restores the
GSettings user value and, only if needed, the saved topology using temporary
method 1. No input is injected. Capabilities are not application DPI acceptance.
"""
import argparse
import json
from pathlib import Path
import signal
import tempfile
import time
from gi.repository import Gio, GLib

FEATURE = 'x11-randr-fractional-scaling'
INTERFACE = 'org.gnome.Mutter.DisplayConfig'


def proxy():
    return Gio.DBusProxy.new_for_bus_sync(Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE,
        None, INTERFACE, '/org/gnome/Mutter/DisplayConfig', INTERFACE, None)


def snapshot(display):
    state = display.call_sync('GetCurrentState', None, Gio.DBusCallFlags.NONE, 5000, None).unpack()
    monitors = []
    for spec, modes, properties in state[1]:
        current = [mode for mode in modes if mode[6].get('is-current', False)]
        config = {}
        if 'is-underscanning' in properties:
            config['underscanning'] = bool(properties['is-underscanning'])
        monitors.append(dict(connector=spec[0], configProperties=config,
            currentModes=[dict(id=mode[0], width=mode[1], height=mode[2], refresh=mode[3],
                preferredScale=mode[4], supportedScales=mode[5]) for mode in current]))
    return dict(configSerial=state[0], monitors=monitors,
        logicalMonitors=[dict(x=m[0], y=m[1], scale=m[2], transform=m[3], primary=m[4],
            connectors=[spec[0] for spec in m[5]]) for m in state[2]],
        properties={key: state[3][key] for key in ('renderer', 'layout-mode',
            'global-scale-required', 'legacy-ui-scaling-factor', 'supports-changing-layout-mode') if key in state[3]})


def topology(state):
    return dict(logicalMonitors=state['logicalMonitors'], modes=[dict(connector=m['connector'],
        configProperties=m['configProperties'], modes=[{key: mode[key] for key in ('id', 'width', 'height', 'refresh')}
            for mode in m['currentModes']]) for m in state['monitors']])


def active_modes(state):
    active = [connector for logical in state['logicalMonitors'] for connector in logical['connectors']]
    assert active and len(active) == len(set(active)), 'No active monitors or duplicate connector'
    monitors = {m['connector']: m for m in state['monitors']}
    assert all(connector in monitors and len(monitors[connector]['currentModes']) == 1 for connector in active), 'Active monitor must have exactly one current mode'
    return [monitors[connector]['currentModes'][0] for connector in active]


def fractional_advertised(state):
    modes = active_modes(state)
    return all(all(any(abs(scale - wanted) < .001 for scale in mode['supportedScales'])
        for wanted in (1.25, 1.5)) for mode in modes)


def configuration(state, serial, method):
    assert method in (0, 1), 'Only VERIFY or TEMPORARY methods are permitted'
    active_modes(state)
    monitors = {m['connector']: m for m in state['monitors']}
    logical = []
    for m in state['logicalMonitors']:
        physical = [(connector, monitors[connector]['currentModes'][0]['id'],
            {key: GLib.Variant('b', value) for key, value in monitors[connector]['configProperties'].items()})
            for connector in m['connectors']]
        logical.append((m['x'], m['y'], m['scale'], m['transform'], m['primary'], physical))
    properties = {'layout-mode': GLib.Variant('u', state['properties']['layout-mode'])} if state['properties'].get('supports-changing-layout-mode', False) else {}
    return GLib.Variant('(uua(iiduba(ssa{sv}))a{sv})', (serial, method, logical, properties))


def apply(display, before, method):
    current = snapshot(display)
    assert {m['connector'] for m in current['monitors']} == {m['connector'] for m in before['monitors']}, 'Connected monitors changed; do not overwrite a different hardware setup'
    if not current['properties'].get('supports-changing-layout-mode', False):
        assert current['properties'].get('layout-mode') == before['properties'].get('layout-mode'), 'Fixed layout mode differs from baseline'
    display.call_sync('ApplyMonitorsConfig', configuration(before, current['configSerial'], method), Gio.DBusCallFlags.NONE, 5000, None)


def same_user_value(settings, original):
    current = settings.get_user_value('experimental-features')
    return (current is None and original is None) or (current is not None and original is not None and current.equal(original))


def settled(display, before):
    deadline = time.monotonic() + 8
    while True:
        after = snapshot(display)
        if (after['properties'] == before['properties'] and after['monitors'] == before['monitors'] and topology(after) == topology(before)) or time.monotonic() >= deadline:
            return after
        time.sleep(.2)


def execute(output, trial, verify, display, settings):
    # All report paths and restore payloads must be usable before any mutation.
    output.parent.mkdir(parents=True, exist_ok=True)
    original = list(settings.get_strv('experimental-features'))
    user_value = settings.get_user_value('experimental-features')
    before = snapshot(display)
    active_modes(before)
    configuration(before, before['configSerial'], 0)
    backup = Path(tempfile.mkdtemp(prefix='deskmorph-mutter-scaling-')) / 'backup.json'
    backup.write_text(json.dumps(dict(features=original, userValue=None if user_value is None else user_value.print_(True), state=before), indent=2) + '\n')
    report = dict(passed=False, trialRequested=trial, verifyRestoreRequested=verify, before=before,
        originalFeatures=original, originalUserValueUnset=user_value is None, backup=str(backup),
        settingsRestored=False, userValueRestored=False, topologyRestored=False, capabilitiesRestored=False,
        featureMutationAttempted=False, restoreConfigurationApplied=False, restoreErrors=[],
        scope='Mutter capability survey, optional VERIFY of saved restore payload and reversible fractional-feature trial; no application DPI acceptance', inputSent=False)
    try:
        if verify or trial:
            apply(display, before, 0)
            report['restorePayloadVerifiedByMutter'] = True
        if trial:
            assert before['properties'].get('renderer') == 'xrandr'
            assert settings.is_writable('experimental-features')
            requested = list(dict.fromkeys(original + [FEATURE]))
            if requested != original:
                report['featureMutationAttempted'] = True
                assert settings.set_strv('experimental-features', requested)
                Gio.Settings.sync()
            deadline = time.monotonic() + 8
            while True:
                during = snapshot(display)
                available = fractional_advertised(during)
                if available or time.monotonic() >= deadline:
                    break
                time.sleep(.2)
            report.update(requestedFeatures=requested, observedFeatures=list(settings.get_strv('experimental-features')),
                during=during, fractional125And150Advertised=available)
            assert topology(during) == topology(before), 'Feature changed topology unexpectedly; restoring baseline'
        else:
            report['during'] = before
    except Exception as error:
        report['error'] = repr(error)
    finally:
        if report['featureMutationAttempted']:
            try:
                if user_value is None:
                    settings.reset('experimental-features')
                else:
                    assert settings.set_value('experimental-features', user_value)
                Gio.Settings.sync()
            except Exception as error:
                report['restoreErrors'].append('GSettings: ' + repr(error))
        try:
            after = settled(display, before)
            # A read-only survey never overwrites a user/external layout change.
            if report['featureMutationAttempted'] and topology(after) != topology(before):
                apply(display, before, 1)
                report['restoreConfigurationApplied'] = True
                after = settled(display, before)
            report.update(after=after, topologyRestored=topology(after) == topology(before),
                capabilitiesRestored=after['properties'] == before['properties'] and after['monitors'] == before['monitors'])
        except Exception as error:
            report['restoreErrors'].append('DisplayConfig: ' + repr(error))
        try:
            report.update(settingsRestored=list(settings.get_strv('experimental-features')) == original,
                userValueRestored=same_user_value(settings, user_value))
        except Exception as error:
            report['restoreErrors'].append('GSettings verification: ' + repr(error))
        report['passed'] = not report.get('error') and not report['restoreErrors'] and all(report[key] for key in ('settingsRestored', 'userValueRestored', 'topologyRestored', 'capabilitiesRestored'))
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


def interrupted(signum, frame):
    raise InterruptedError('Signal ' + str(signum))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--verify-restore', action='store_true')
    parser.add_argument('--trial-fractional-feature', action='store_true')
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    result = execute(args.output, args.trial_fractional_feature, args.verify_restore,
        proxy(), Gio.Settings.new('org.gnome.mutter'))
    print(json.dumps({key: result.get(key) for key in ('passed', 'featureMutationAttempted', 'restorePayloadVerifiedByMutter', 'settingsRestored', 'userValueRestored', 'topologyRestored', 'capabilitiesRestored', 'fractional125And150Advertised')}), flush=True)
    assert result['passed'], 'Probe/restore failed; see report and backup'
