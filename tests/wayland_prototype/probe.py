"""Drive only the capability-protected extension inside the private compositor."""
import json
import os
from pathlib import Path
import subprocess
import time
import hashlib
from gi.repository import GLib


def run(root, metadata, bus, call):
    token = metadata['DESKMORPH_PROTOTYPE_TOKEN']
    def dispatch(**command):
        return json.loads(call(bus, 'org.gnome.Shell', '/org/deskmorph/Lab', 'org.deskmorph.Lab', 'Dispatch',
            GLib.Variant('(ss)', (token, json.dumps(command)))).unpack()[0])
    def wait(predicate, message):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                value = predicate()
                if value: return value
            except GLib.Error:
                pass
            time.sleep(.1)
        raise AssertionError(message)
    wait(lambda: dispatch(op='state'), 'Lab extension did not enable')
    rejected = False
    try:
        call(bus, 'org.gnome.Shell', '/org/deskmorph/Lab', 'org.deskmorph.Lab', 'Dispatch', GLib.Variant('(ss)', ('invalid-token', '{"op":"state"}')))
    except GLib.Error:
        rejected = True
    assert rejected, 'Unauthenticated prototype request accepted'
    env = dict(os.environ, **{k: v for k, v in metadata.items() if k.isupper()}, DBUS_SESSION_BUS_ADDRESS=metadata['busAddress'])
    env.pop('DISPLAY', None)
    process = None
    result = dict(extension='deskmorph-lab@deskmorph.local', unauthorizedRequestRejected=rejected, placement=[], autoHideCycles=[])
    def snapshot(): return dispatch(op='state')
    try:
        with (root / 'fixture.log').open('w') as log:
            process = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('fixture.py'))], env=env, stdout=log, stderr=log)
        def fixtures():
            state = snapshot()
            return state if len(state['windows']) == 2 else None
        state = wait(fixtures, 'Two native fixture windows did not map')
        assert all(w['pid'] == process.pid and w['clientType'] == 0 for w in state['windows']), state
        result['fixturePid'] = process.pid
        result['nativeWindows'] = state['windows']
        for edge in ('bottom', 'top'):
            dispatch(op='edge', edge=edge)
            m = snapshot()['monitor']; x = m['x'] + m['width'] // 2
            outside_y = m['y'] + m['height'] // 2
            inside_y = m['y'] + m['height'] - 1 if edge == 'bottom' else m['y']
            for cycle in range(3):
                dispatch(op='pointer', x=x, y=outside_y)
                wait(lambda: snapshot()['dock']['height'] == 4, 'Dock did not auto-hide away from edge')
                dispatch(op='pointer', x=x, y=inside_y)
                visible = wait(lambda: snapshot() if snapshot()['dock']['height'] == 54 else None, 'Dock did not reveal from actual pointer motion')
                dock = visible['dock']
                assert visible['actorMapped'] and visible['pointer'] == [x, inside_y]
                assert dock['x'] == m['x'] + round((m['width'] - 500) / 2)
                assert dock['y'] == (m['y'] + m['height'] - 54 if edge == 'bottom' else m['y'])
                result['autoHideCycles'].append(dict(edge=edge, cycle=cycle + 1, hiddenHeight=4, shownHeight=54))
            result['placement'].append(dict(monitor=m, dock=dock))
        activations = []
        for window in state['windows'] + list(reversed(state['windows'])):
            dispatch(op='activate', id=window['id'], pid=window['pid'])
            wait(lambda: any(w['id'] == window['id'] and w['focused'] for w in snapshot()['windows']), 'Exact native window activation failed')
            activations.append(window['id'])
        result['activatedWindowIds'] = activations
        # PID mismatch must reject without closing either window.
        try:
            dispatch(op='close', id=state['windows'][0]['id'], pid=process.pid + 1)
            raise AssertionError('Mismatched PID accepted')
        except GLib.Error:
            pass
        assert len(snapshot()['windows']) == 2
        result['mismatchedPidRejected'] = True
        target, survivor = state['windows']
        dispatch(op='close', id=target['id'], pid=target['pid'])
        remaining = wait(lambda: snapshot() if len(snapshot()['windows']) == 1 else None, 'Exact target did not close')
        assert remaining['windows'][0]['id'] == survivor['id'] and process.poll() is None
        result['closedWindowId'] = target['id']; result['survivingWindowId'] = survivor['id']
        dispatch(op='close', id=survivor['id'], pid=survivor['pid'])
        process.wait(timeout=5)
        assert process.returncode == 0
        wait(lambda: not snapshot()['windows'], 'Fixture window remained after normal exit')
        subprocess.run(['gsettings', 'set', 'org.gnome.shell', 'enabled-extensions', '[]'], env=env, check=True)
        def disabled():
            try:
                snapshot()
                return False
            except GLib.Error as error:
                return 'UnknownMethod' in str(error) or 'UnknownObject' in str(error)
        wait(disabled, 'Disabling the lab extension retained its exported control endpoint')
        result['extensionDisabledEndpointRemoved'] = True
        result['sourceSha256'] = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ('extension.js', 'metadata.json', 'fixture.py', 'probe.py')}
        result.update(fixtureExited=True, rendering='GNOME Shell St actor; not the Tauri Dock', scope='Private GNOME 46 headless compositor only, lab extension with explicit enable and capability token; two GTK native Wayland windows. No production adapter or host extension installation.')
        return result
    finally:
        if process and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
