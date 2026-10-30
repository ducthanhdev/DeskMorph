"""Reuse system receiver fixtures with real Enter on the private GNOME desktop."""
import json
import os
from pathlib import Path
import re
import subprocess
import time
import traceback
from gi.repository import Atspi
from dock_layout_smoke import descendants
from private_keyboard import PrivateKeyboard
from system_locations_smoke import run


def audit(*, app, root, language, pid, **_):
    root = Path(root)
    keyboard = PrivateKeyboard(root)
    binary = Path(__file__).resolve().parents[1] / 'src-tauri/target/agent/debug/deskmorph'
    config_home = root / 'config'
    reports = root / 'system-keyboard'
    current = [app]
    processes = []
    activations = []

    def wait(predicate, message):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(.1)
        raise AssertionError(message)

    def owned(process_id):
        desktop = Atspi.get_desktop(0)
        return next((n for n in descendants(desktop) if n.get_role_name() == 'application' and n.get_process_id() == process_id), None)

    def start_app(env_overrides=None):
        env = dict(os.environ, DESKMORPH_CONFIG_HOME=str(config_home),
            DESKMORPH_SYSTEM_KEYS_LAB=str(root), WEBKIT_DISABLE_DMABUF_RENDERER='1')
        env.update(env_overrides or {})
        with (root / ('system-app-' + str(len(processes)) + '.log')).open('w') as log:
            process = subprocess.Popen([str(binary)], env=env, stdout=log, stderr=log)
        processes.append(process)
        return wait(lambda: owned(process.pid), 'Private system app accessibility absent')

    def test_app():
        process_id = current[0].get_process_id()
        if not Path(f'/proc/{process_id}').exists():
            raise RuntimeError('Owned app has stopped')
        return current[0]

    def native(title):
        process_id = current[0].get_process_id()
        tree = subprocess.check_output(['xwininfo', '-root', '-tree'], text=True, timeout=5)
        for xid in re.findall(r'(0x[0-9a-f]+) "' + re.escape(title) + '"', tree):
            props = subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID'], text=True, timeout=5)
            if not re.search(r'= ' + str(process_id) + r'\b', props):
                continue
            info = subprocess.check_output(['xwininfo', '-id', xid], text=True, timeout=5)
            if 'Map State: IsViewable' in info:
                return xid

    def focus_studio(title='DeskMorph Studio'):
        xid = wait(lambda: native(title), 'Private window absent: ' + title)
        keyboard.activate(xid, current[0].get_process_id())
        return xid

    def keys(value=None, chord=None):
        assert value is None, 'System fixtures only require key chords'
        keyboard.keys(keyboard.active(), current[0].get_process_id(), chord or [])
        time.sleep(.2)

    def click(name, role=None):
        def target():
            nodes = [n for n in descendants(current[0]) if n.get_name() == name and n.get_role_name() == (role or 'button')]
            assert len(nodes) <= 1, 'Ambiguous private key target: ' + name
            if nodes and nodes[0].get_state_set().contains(Atspi.StateType.ENABLED):
                return nodes[0]
        node = wait(target, 'Enabled system key target absent: ' + name)
        frame = node
        while frame.get_role_name() != 'frame':
            frame = frame.get_parent()
            assert frame
        xid = focus_studio(frame.get_name())
        assert node.get_component_iface().grab_focus()
        wait(lambda: node.get_state_set().contains(Atspi.StateType.FOCUSED), 'System action did not focus')
        keyboard.keys(xid, current[0].get_process_id(), [0xff0d])
        activations.append(dict(name=name, role=node.get_role_name(), frame=frame.get_name(), key='Enter'))
        time.sleep(.7)

    try:
        run(app, config_home, click, focus_studio, keys, test_app, start_app,
            lambda value: current.__setitem__(0, value), language=language, report_root=reports)
        report = json.loads((reports / 'system-locations-result.json').read_text())
        report.update(activationMethod='AT-SPI focus seeds followed by XTest Enter, owned private GNOME only',
                      activations=activations)
        return report
    except Exception as error:
        (root / 'system-keyboard-driver-result.json').write_text(json.dumps(dict(passed=False, error=repr(error), traceback=traceback.format_exc(), activations=activations), ensure_ascii=False, indent=2)+'\n')
        raise
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
