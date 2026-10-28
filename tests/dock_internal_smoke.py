"""Filter this process's native windows without hiding external lookalikes."""
import json
import os
from pathlib import Path
import re
import select
import subprocess
import time
from gi.repository import Atspi
from dock_layout_smoke import descendants


def run(app, config_home, click, focus_studio, native_keys, native_click_node, owned_input_pids):
    root = Path('/tmp/deskmorph-desktop-test')
    config_file = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    config = lambda: json.loads(config_file.read_text())['config']
    original = config()
    fixture = None
    passed = []

    def wait(predicate, message):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(.1)
        raise AssertionError(message)

    def import_config(value, label):
        if config() == value: return
        file = root / f'internal-{label}.json'
        file.write_text(json.dumps({'schemaVersion': 1, 'config': value}))
        focus_studio(); click('Hệ thống'); click('Nhập cấu hình'); focus_studio('Select File')
        native_keys(chord=[0xffe3, ord('l')]); native_keys(value=str(file)); native_keys(chord=[0xff0d])
        time.sleep(.8); click('Áp dụng cấu hình đã nhập')
        wait(lambda: config() == value, 'Internal-window config import failed')

    def native_windows():
        result = []
        for xid in re.findall(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True)):
            props = subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID', 'WM_CLASS', '_NET_WM_NAME', '_NET_WM_WINDOW_TYPE'], text=True)
            pid = re.search(r'_NET_WM_PID.*= (\d+)', props)
            if pid: result.append((xid, int(pid.group(1)), props))
        return result

    def group(count):
        return next((n for n in descendants(app) if n.get_role_name() == 'button' and n.get_name() == f'Deskmorph • {count} cửa sổ'), None)

    def assert_count(count):
        wait(lambda: group(count) is not None if count else not any(n.get_role_name() == 'button' and n.get_name().startswith('Deskmorph • ') for n in descendants(app)), 'Own native windows leaked into external same-class group')

    def reply():
        assert select.select([fixture.stdout], [], [], 5)[0]
        line = fixture.stdout.readline(); assert line
        return json.loads(line)

    try:
        initial = dict(original, enabled=True, autoHide=False, showApps=True, showClock=True, showAudio=True,
                       pinnedApps=[p for p in original['pinnedApps'] if 'deskmorph' not in [c.lower() for c in p['matchClasses']]])
        import_config(initial, 'initial')
        native = native_windows()
        own = [(xid, props) for xid, pid, props in native if pid == app.get_process_id()]
        assert any('DeskMorph Studio' in props for _, props in own) and any('DeskMorph Taskbar' in props for _, props in own)
        baseline = sum(pid != app.get_process_id() and '"Deskmorph"' in props and '_NET_WM_WINDOW_TYPE_DOCK' not in props and '_NET_WM_WINDOW_TYPE_DESKTOP' not in props for _, pid, props in native)
        assert_count(baseline)
        passed.append('visible own Studio and Dock are excluded by PID; unrelated same-class native windows retain their baseline count')
        fixture = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('desktop_smoke.py').resolve()), '--internal-fixture'],
            env=dict(os.environ, DESKMORPH_CONFIG_HOME=config_home), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        state = reply()
        assert fixture.poll() is None and b'DESKMORPH_CONFIG_HOME=' + config_home.encode() in Path(f'/proc/{fixture.pid}/environ').read_bytes().split(b'\0')
        for window in state.values():
            props = subprocess.check_output(['xprop', '-id', window['xid'], '_NET_WM_PID', 'WM_CLASS'], text=True)
            assert re.search(r'_NET_WM_PID.*= ' + str(fixture.pid) + r'\b', props) and '"Deskmorph"' in props
        owned_input_pids.add(fixture.pid)
        fixture.stdin.write(json.dumps(dict(action='title', index=1, title='DeskMorph Studio _NET_WM_WINDOW_TYPE_DOCK')) + '\n'); fixture.stdin.flush(); reply()
        assert_count(baseline + 3)
        passed.append('three owned external windows with identical WM_CLASS and a Studio lookalike title remain visible')
        for button, title in [('Tìm ứng dụng', 'DeskMorph Context Menu'), ('Âm thanh', 'DeskMorph Context Menu'), ('Mở lịch', 'DeskMorph Calendar')]:
            focus_studio(); click(button, role='button'); focus_studio(title)
            assert any(pid == app.get_process_id() and title in props for _, pid, props in native_windows())
            time.sleep(1.8); assert_count(baseline + 3)
            native_keys(chord=[0xff1b])
        passed.append('own launcher/audio/calendar native popups do not increment app count')
        focus_studio('DeskMorph Window Test 2', target_pid=fixture.pid)
        expected = state['2']['xid']
        assert expected in subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)
        time.sleep(1.8); native_click_node(group(baseline + 3))
        def active_row():
            return next((n for n in descendants(app) if n.get_role_name() == 'button' and n.get_name().startswith('DeskMorph Window Test 2') and n.get_state_set().contains(Atspi.StateType.FOCUSED)), None)
        wait(lambda: active_row() is not None, 'External lookalike active row did not receive focus')
        focus_studio('DeskMorph Context Menu'); native_keys(chord=[0xff0d])
        wait(lambda: expected in subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True), 'Lookalike selection activated wrong XID')
        passed.append('external lookalike active row and Enter activate the exact owned XID, with no title/class exclusion')
    finally:
        if fixture:
            owned_input_pids.discard(fixture.pid)
            if fixture.poll() is None: fixture.terminate()
            fixture.wait(timeout=5)
        import_config(original, 'restore')
    assert_count(baseline)
    report = dict(passed=passed, pid=app.get_process_id(), fixturePid=fixture.pid, externalBaseline=baseline, configRestored=True)
    (root / 'internal-result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
