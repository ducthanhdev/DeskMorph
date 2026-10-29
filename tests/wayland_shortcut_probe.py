#!/usr/bin/python3
"""GNOME custom shortcut through the real gsd-media-keys, on the lab bus only."""
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import time
import gi
import hashlib
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi, Gio, GLib


def run():
    root = Path(os.environ['DESKMORPH_COMPOSITOR_LAB'])
    assert str(root).startswith('/tmp/deskmorph-wayland-lab-')
    assert os.environ['XDG_RUNTIME_DIR'] == str(root / 'runtime') and not os.environ.get('DISPLAY')
    metadata = json.loads((root / 'session.json').read_text())
    env = dict(os.environ, DESKMORPH_CONFIG_HOME=str(root / 'shortcut-config'), WEBKIT_DISABLE_DMABUF_RENDERER='1')
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    def dispatch(**command):
        reply = bus.call_sync('org.gnome.Shell', '/org/deskmorph/Lab', 'org.deskmorph.Lab', 'Dispatch', GLib.Variant('(ss)', (metadata['DESKMORPH_PROTOTYPE_TOKEN'], json.dumps(command))), None, Gio.DBusCallFlags.NONE, 3000, None)
        return json.loads(reply.unpack()[0])
    def wait(predicate, message):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            try:
                value = predicate()
                if value: return value
            except GLib.Error: pass
            time.sleep(.1)
        raise AssertionError(message)
    def settings(schema, key, value):
        subprocess.run(['gsettings', 'set', schema, key, value], env=env, check=True)
    def invocations():
        path = root / 'shortcut-invocations.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    def nodes(node):
        if node is None: return
        yield node
        for i in range(node.get_child_count()): yield from nodes(node.get_child_at_index(i))
    def app(pid):
        return next((n for n in nodes(Atspi.get_desktop(0)) if n.get_role_name() == 'application' and n.get_process_id() == pid), None)
    processes = []; app_pid = None; report = dict(cycles=[])
    schema = 'org.gnome.settings-daemon.plugins.media-keys'
    path = '/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/deskmorph-lab/'
    custom = schema + '.custom-keybinding:' + path
    try:
        wait(lambda: dispatch(op='prepare'), 'Lab extension not ready')
        settings(custom, 'name', 'DeskMorph Lab Launcher')
        command = shlex.join(['/usr/bin/python3', str(Path(__file__).with_name('wayland_shortcut_command.py'))])
        settings(custom, 'command', command)
        settings(custom, 'binding', '<Control><Super>k')
        settings(schema, 'custom-keybindings', "['" + path + "']")
        with (root / 'media-keys.log').open('w') as log:
            daemon = subprocess.Popen(['/usr/libexec/gsd-media-keys', '--verbose'], env=env, stdout=log, stderr=log)
        processes.append(daemon)
        wait(lambda: bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'NameHasOwner', GLib.Variant('(s)', ('org.gnome.SettingsDaemon.MediaKeys',)), None, Gio.DBusCallFlags.NONE, 3000, None).unpack()[0], 'Media keys daemon not ready')
        with (root / 'shortcut-background.log').open('w') as log:
            background = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('wayland_prototype') / 'fixture.py')], env=env, stdout=log, stderr=log)
        processes.append(background)
        dispatch(op='target', pid=background.pid)
        state = wait(lambda: dispatch(op='state') if len(dispatch(op='state')['windows']) == 2 else None, 'Background native fixture missing')
        target = state['windows'][0]
        wait(lambda: not dispatch(op='bindingAvailable')['available'], 'Custom accelerator was not registered')
        report['duplicateGrabRejected'] = True
        for cycle in range(2):
            dispatch(op='target', pid=background.pid)
            dispatch(op='activate', id=target['id'], pid=background.pid)
            wait(lambda: any(w['focused'] for w in dispatch(op='state')['windows']), 'Background did not focus')
            time.sleep(1)
            dispatch(op='shortcut')
            calls = wait(lambda: invocations() if len(invocations()) == cycle + 1 else None, 'Custom shortcut did not execute launcher command')
            if app_pid is None: app_pid = calls[0]['pid']
            dispatch(op='target', pid=app_pid)
            state = wait(lambda: dispatch(op='state') if any(w['focused'] and w['title'] == 'DeskMorph Launcher' for w in dispatch(op='state')['windows']) else None, 'Desktop shortcut did not activate the actual launcher')
            ui = wait(lambda: app(app_pid), 'Launcher inaccessible')
            wait(lambda: any(n.get_role_name() == 'entry' and n.get_name() == 'Tìm ứng dụng' for n in nodes(ui)), 'Launcher search missing')
            for _ in range(16): dispatch(op='key', code=44)
            def empty():
                return any(n.get_text_iface() and Atspi.Text.get_text(n.get_text_iface(), 0, -1) == 'Không tìm thấy ứng dụng phù hợp.' for n in nodes(ui))
            wait(empty, 'Shortcut did not focus renderer search input')
            dispatch(op='key', code=1)
            wait(lambda: not any(w['title'] == 'DeskMorph Launcher' for w in dispatch(op='state')['windows']), 'Escape did not hide shortcut launcher')
            report['cycles'].append(dict(kind='cold' if cycle == 0 else 'warm', commandPid=calls[-1]['pid'], appPid=app_pid, desktopToken=calls[-1], automaticNativeFocus=True, nativeSearch=True, escape=True, noExplicitLauncherActivation=True))
        settings(schema, 'custom-keybindings', '[]')
        wait(lambda: dispatch(op='bindingAvailable')['available'], 'Removing custom shortcut did not release accelerator registration')
        dispatch(op='target', pid=background.pid)
        dispatch(op='activate', id=target['id'], pid=background.pid)
        dispatch(op='shortcut'); time.sleep(2)
        assert len(invocations()) == 2, 'Removing custom shortcut did not release its key'
        report.update(shortcutRemoved=True, mediaKeysPid=daemon.pid, backgroundPid=background.pid, scope='Real GNOME46 gsd-media-keys custom shortcut on private compositor/settings/bus. Virtual Ctrl+Super+K input only in lab. No host shortcuts changed.')
        report['sourceSha256'] = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ('wayland_shortcut_probe.py', 'wayland_shortcut_command.py', 'wayland_lab.py')}
        report['binarySha256'] = hashlib.sha256((Path(__file__).resolve().parents[1] / 'src-tauri/target/agent/debug/deskmorph').read_bytes()).hexdigest()
        (root / 'launcher-result.json').write_text(json.dumps(report, indent=2) + '\n')
    except Exception:
        print('INVOCATIONS', json.dumps(invocations()), flush=True)
        try: print('STATE', json.dumps(dispatch(op='state')), flush=True)
        except Exception: pass
        raise
    finally:
        settings(schema, 'custom-keybindings', '[]')
        if app_pid:
            proc = Path(f'/proc/{app_pid}')
            if proc.exists():
                assert f'DESKMORPH_COMPOSITOR_LAB={root}'.encode() in (proc / 'environ').read_bytes().split(b'\0')
                os.kill(app_pid, signal.SIGTERM)
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)

if __name__ == '__main__': run()
