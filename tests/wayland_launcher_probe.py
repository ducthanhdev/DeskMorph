#!/usr/bin/python3
"""Actual WebKit/Tauri launcher on a private Wayland compositor and AT-SPI bus."""
import json
import os
from pathlib import Path
import subprocess
import time
import gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi, Gio, GLib


def run():
    root = Path(os.environ['DESKMORPH_COMPOSITOR_LAB'])
    assert str(root).startswith('/tmp/deskmorph-wayland-lab-')
    assert os.environ['XDG_RUNTIME_DIR'] == str(root / 'runtime') and not os.environ.get('DISPLAY')
    metadata = json.loads((root / 'session.json').read_text())
    binary = Path(__file__).resolve().parents[1] / 'src-tauri/target/agent/debug/deskmorph'
    env = dict(os.environ, DESKMORPH_CONFIG_HOME=str(root / 'deskmorph-config'), WEBKIT_DISABLE_DMABUF_RENDERER='1')
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    def dispatch(**command):
        result = bus.call_sync('org.gnome.Shell', '/org/deskmorph/Lab', 'org.deskmorph.Lab', 'Dispatch', GLib.Variant('(ss)', (metadata['DESKMORPH_PROTOTYPE_TOKEN'], json.dumps(command))), None, Gio.DBusCallFlags.NONE, 3000, None)
        return json.loads(result.unpack()[0])
    def wait(predicate, message):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            try:
                value = predicate()
                if value: return value
            except GLib.Error: pass
            time.sleep(.1)
        raise AssertionError(message)
    def descendants(node):
        if node is None: return
        yield node
        for i in range(node.get_child_count()): yield from descendants(node.get_child_at_index(i))
    def accessible(pid):
        return next((a for a in descendants(Atspi.get_desktop(0)) if a.get_role_name() == 'application' and a.get_process_id() == pid), None)
    def search(app):
        return next((n for n in descendants(app) if n.get_role_name() == 'entry' and n.get_name() in ('Tìm ứng dụng', 'Search applications')), None)
    process = None
    try:
        wait(lambda: dispatch(op='prepare'), 'Lab Shell did not initialize')
        time.sleep(.5)
        with (root / 'deskmorph-launcher.log').open('w') as log:
            process = subprocess.Popen([str(binary), '--launcher'], env=env, stdout=log, stderr=log)
        assert wait(lambda: dispatch(op='target', pid=process.pid), 'Lab extension unavailable')
        app = wait(lambda: accessible(process.pid), 'DeskMorph did not register on private AT-SPI bus')
        entry = wait(lambda: search(app), 'Cold launcher search did not load')
        state = wait(lambda: dispatch(op='state') if any(w['title'] == 'DeskMorph Launcher' for w in dispatch(op='state')['windows']) else None, 'Cold launcher did not map')
        automatic_cold_focus = any(w['focused'] and w['title'] == 'DeskMorph Launcher' for w in state['windows'])
        popup = next(w for w in state['windows'] if w['title'] == 'DeskMorph Launcher')
        dispatch(op='activate', id=popup['id'], pid=process.pid)
        wait(lambda: any(w['focused'] and w['title'] == 'DeskMorph Launcher' for w in dispatch(op='state')['windows']), 'Lab explicit activation did not focus launcher')
        assert all(w['clientType'] == 0 for w in state['windows']), state
        assert not any(w['title'] == 'DeskMorph Studio' for w in state['windows']), 'Cold launcher also mapped Studio'
        # Query the real renderer; no launch of an arbitrary installed app.
        for _ in range(16): dispatch(op='key', code=44)
        def has_empty():
            for n in descendants(app):
                text = n.get_text_iface()
                if text and Atspi.Text.get_text(text, 0, -1) in ('Không tìm thấy ứng dụng phù hợp.', 'No matching applications found.'): return True
            return False
        wait(has_empty, 'Search did not update to empty state')
        dispatch(op='key', code=1)
        wait(lambda: not any(w['title'] == 'DeskMorph Launcher' for w in dispatch(op='state')['windows']), 'Native Escape did not hide launcher')
        forwarded = subprocess.run([str(binary), '--launcher'], env=env, capture_output=True, text=True, timeout=8)
        assert forwarded.returncode == 0, forwarded.stderr
        state = wait(lambda: dispatch(op='state') if any(w['title'] == 'DeskMorph Launcher' for w in dispatch(op='state')['windows']) else None, 'Warm launcher did not map')
        automatic_warm_focus = any(w['focused'] and w['title'] == 'DeskMorph Launcher' for w in state['windows'])
        popup = next(w for w in state['windows'] if w['title'] == 'DeskMorph Launcher')
        dispatch(op='activate', id=popup['id'], pid=process.pid)
        wait(lambda: any(w['focused'] and w['title'] == 'DeskMorph Launcher' for w in dispatch(op='state')['windows']), 'Warm explicit activation failed')
        assert process.poll() is None
        dispatch(op='key', code=1)
        wait(lambda: not any(w['title'] == 'DeskMorph Launcher' for w in dispatch(op='state')['windows']), 'Warm Escape did not hide launcher')
        first_pid = process.pid
        process.terminate(); process.wait(timeout=8)
        config_path = root / 'deskmorph-config/com.ducthanhdev.deskmorph/config.json'
        config = json.loads(config_path.read_text()); config['config']['enabled'] = False
        config_path.write_text(json.dumps(config))
        original_config = config_path.read_bytes()
        with (root / 'deskmorph-launcher.log').open('a') as log:
            process = subprocess.Popen([str(binary), '--launcher'], env=env, stdout=log, stderr=log)
        dispatch(op='target', pid=process.pid)
        app = wait(lambda: accessible(process.pid), 'Disabled-Dock app unavailable')
        wait(lambda: search(app), 'Launcher requires the Dock to be enabled')
        state = wait(lambda: dispatch(op='state') if any(w['title'] == 'DeskMorph Launcher' for w in dispatch(op='state')['windows']) else None, 'Disabled-Dock launcher did not map')
        assert not any(w['title'] in ('DeskMorph Taskbar', 'DeskMorph Studio') for w in state['windows'])
        popup = next(w for w in state['windows'] if w['title'] == 'DeskMorph Launcher')
        dispatch(op='close', id=popup['id'], pid=process.pid)
        wait(lambda: not any(w['title'] == 'DeskMorph Launcher' for w in dispatch(op='state')['windows']), 'Window-manager close did not hide launcher')
        assert process.poll() is None and config_path.read_bytes() == original_config
        forwarded_studio = subprocess.run([str(binary)], env=env, capture_output=True, text=True, timeout=8)
        assert forwarded_studio.returncode == 0
        wait(lambda: any(w['title'] == 'DeskMorph Studio' for w in dispatch(op='state')['windows']), 'Default command no longer opens Studio')
        report = dict(appPid=first_pid, disabledDockAppPid=process.pid, disabledDockColdStart=True, disabledConfigUnchanged=True, windowManagerCloseHides=True, defaultCommandOpensStudio=True, coldStartLauncher=True, studioHidden=True, nativeWayland=True, searchEmptyState=True, nativeEscape=True, warmForwardAck=True, automaticColdFocus=automatic_cold_focus, automaticWarmFocus=automatic_warm_focus, explicitLabActivationForInput=True, scope='Direct CLI on private GNOME46 Wayland. Native input tested after explicit lab activation. No real custom keybinding or desktop activation token yet; automatic focus is not asserted.')
        (root / 'launcher-result.json').write_text(json.dumps(report, indent=2) + '\n')
    except Exception:
        try:
            print('NATIVE STATE', json.dumps(dispatch(op='state')), flush=True)
            for node in descendants(accessible(process.pid)):
                print(node.get_role_name(), repr(node.get_name()), flush=True)
        except Exception as error: print('DIAGNOSTIC', repr(error), flush=True)
        raise
    finally:
        if process and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=8)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)

if __name__ == '__main__': run()
