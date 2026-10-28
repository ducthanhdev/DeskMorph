"""Unknown WM_CLASS ownership changes through the real Studio mapping editor."""
import json
import os
from pathlib import Path
import re
import select
import subprocess
import time
from gi.repository import Atspi
from dock_layout_smoke import descendants


def run(app, config_home, click, focus_studio, native_keys, native_click_node, owned_input_pids, restart):
    root = Path('/tmp/deskmorph-desktop-test')
    path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    snapshot = lambda: json.loads(path.read_text())
    original = snapshot()['config']
    fixtures = []
    passed = []
    pin_name = 'Mapping Test'
    test_id = 'deskmorph-mapping-test'
    assert not any(p['id'] == test_id for p in original['pinnedApps'])

    def wait(predicate, message):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(.1)
        raise AssertionError(message)

    def node(name, role=None):
        return next((n for n in descendants(app) if n.get_name() == name and (role is None or n.get_role_name() == role)), None)

    def pin(count): return node(f'{pin_name} • {count} cửa sổ', 'button')
    def unknown(count): return node(f'DecodeTool • {count} cửa sổ', 'button')
    def current_pin(): return next(p for p in snapshot()['config']['pinnedApps'] if p['id'] == test_id)

    def import_config(value, label):
        file = root / f'mapping-{label}.json'
        file.write_text(json.dumps({'schemaVersion': 1, 'config': value}))
        focus_studio(); click('Hệ thống'); click('Nhập cấu hình'); focus_studio('Select File')
        native_keys(chord=[0xffe3, ord('l')]); native_keys(value=str(file)); native_keys(chord=[0xff0d])
        time.sleep(.8); click('Áp dụng cấu hình đã nhập')
        wait(lambda: snapshot()['config'] == value, 'Mapping import did not persist')

    def edit(value):
        focus_studio(); click('Ứng dụng')
        summary = node('Ghép lớp cửa sổ ' + pin_name)
        assert summary, 'Mapping disclosure missing'
        entry = node('Ghép lớp cửa sổ ' + pin_name, 'entry')
        if entry is None:
            assert summary.get_action_iface().do_action(0)
            time.sleep(.3)
            entry = node('Ghép lớp cửa sổ ' + pin_name, 'entry')
        assert entry, [(n.get_role_name(), n.get_name()) for n in descendants(app) if 'Ghép' in n.get_name()]
        assert entry.get_component_iface().grab_focus()
        native_keys(value=value)
        click('Lưu')

    def reply(fixture):
        assert select.select([fixture.stdout], [], [], 5)[0], 'Mapping fixture did not reply'
        line = fixture.stdout.readline()
        assert line, 'Mapping fixture exited early'
        return json.loads(line)

    def command(fixture, index):
        fixture.stdin.write(json.dumps(dict(action='close', index=index)) + '\n'); fixture.stdin.flush()
        return reply(fixture)

    try:
        # No desktop ID exists for this test pin or WM_CLASS. Its command is never guessed.
        test_pin = dict(id=test_id, name=pin_name, command='/bin/true', matchClasses=['code'], iconType='custom', enabled=True)
        initial = dict(original, enabled=True, autoHide=False, showApps=True,
                       pinnedApps=[test_pin] + [p for p in original['pinnedApps'] if 'code' not in [c.lower() for c in p['matchClasses']]])
        import_config(initial, 'initial')
        states = []
        for _ in range(2):
            fixture = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('desktop_smoke.py').resolve()), '--mapping-fixture'],
                env=dict(os.environ, DESKMORPH_CONFIG_HOME=config_home), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            fixtures.append(fixture)
            state = reply(fixture); states.append(state)
            assert fixture.poll() is None
            assert b'DESKMORPH_CONFIG_HOME=' + config_home.encode() in Path(f'/proc/{fixture.pid}/environ').read_bytes().split(b'\0')
            for window in state.values():
                props = subprocess.check_output(['xprop', '-id', window['xid'], '_NET_WM_PID', 'WM_CLASS'], text=True)
                assert re.search(r'_NET_WM_PID.*= ' + str(fixture.pid) + r'\b', props) and 'DecodeTool' in props
            owned_input_pids.add(fixture.pid)
        assert fixtures[0].pid != fixtures[1].pid
        wait(lambda: pin(0) is not None and unknown(6) is not None, 'Substring code rule stole DecodeTool or multi-process count differs')
        passed.append('two owned GTK processes / six windows with unknown DecodeTool class stay separate from code pin')
        edit('DecodeTool')
        wait(lambda: current_pin()['matchClasses'] == ['decodetool'] and pin(6) is not None and unknown(6) is None, 'Explicit mapping failed to transfer all windows exactly once')
        assert current_pin()['command'] == '/bin/true' and 'desktopId' not in current_pin()
        passed.append('real mapping editor normalizes and saves class, transfers six windows, preserves command without inventing desktop ID')
        # A conflicting mapping must neither write config nor disturb running ownership.
        before = snapshot()
        other_class = next(p['matchClasses'][0] for p in initial['pinnedApps'][1:] if p['matchClasses'])
        edit(other_class)
        wait(lambda: any('WM_CLASS đã thuộc' in (n.get_name() + (Atspi.Text.get_text(n.get_text_iface(), 0, -1) if n.get_text_iface() else '')) for n in descendants(app)), 'Conflict was not shown')
        assert snapshot() == before and pin(6) is not None
        passed.append('conflicting class is rejected with visible error and no config/revision mutation')
        edit('DecodeTool')
        click('Ghim ' + pin_name)
        wait(lambda: unknown(6) is not None and pin(6) is None, 'Disabling pin lost or duplicated its windows')
        click('Ghim ' + pin_name)
        wait(lambda: pin(6) is not None and unknown(6) is None, 'Enabling pin failed to reclaim windows')
        passed.append('disable and enable transfer full count between unpinned and pinned groups')
        saved_pin = current_pin()
        app = restart()
        wait(lambda: current_pin() == saved_pin and pin(6) is not None and unknown(6) is None, 'Restart lost mapping or duplicated groups')
        passed.append('normal isolated app restart preserves explicit mapping and six-window ownership')
        # Validate selecting the active window by exact XID after grouping multiple PIDs.
        focus_studio('DeskMorph Window Test 2', target_pid=fixtures[1].pid)
        expected_xid = states[1]['2']['xid']
        assert expected_xid in subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)
        time.sleep(1.8)  # Dock snapshots active XID on its 1.5 s window poll.
        native_click_node(pin(6))
        wait(lambda: any(n.get_role_name() == 'button' and n.get_name().startswith('DeskMorph Window Test 2') for n in descendants(app)), 'Mapped pin did not open window list')
        rows = [n for n in descendants(app) if n.get_role_name() == 'button' and n.get_name().startswith('DeskMorph Window Test')]
        assert len(rows) == 6, 'Mapped list does not contain six window rows'
        def expected_focus():
            focused = [n for n in descendants(app) if n.get_role_name() == 'button' and n.get_name().startswith('DeskMorph Window Test') and n.get_state_set().contains(Atspi.StateType.FOCUSED)]
            return len(focused) == 1 and focused[0].get_name().startswith('DeskMorph Window Test 2')
        wait(expected_focus, 'Mapped list did not focus the active fixture row')
        native_keys(chord=[0xff0d])
        wait(lambda: expected_xid in subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True), 'Mapped active selection targeted wrong PID/XID')
        passed.append('active row and Enter preserve exact XID across duplicate titles from two processes')
        focus_studio(); edit('')
        wait(lambda: current_pin()['matchClasses'] == [] and pin(0) is not None and unknown(6) is not None, 'Clearing mapping did not return windows')
        edit('DecodeTool')
        for fixture in fixtures:
            for index in (1, 2, 3): command(fixture, index)
        wait(lambda: pin(0) is not None and unknown(6) is None, 'External close did not reconcile pinned count to zero')
        passed.append('clear and restore mapping, then external close 6 to 0 retains idle pin')
    finally:
        for fixture in fixtures:
            owned_input_pids.discard(fixture.pid)
            if fixture.poll() is None: fixture.terminate()
            fixture.wait(timeout=5)
        import_config(original, 'restore')
    report = dict(passed=passed, pid=app.get_process_id(), fixturePids=[f.pid for f in fixtures], configRestored=True)
    (root / 'mapping-result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
