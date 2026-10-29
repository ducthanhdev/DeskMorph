"""Owned native keyboard entry to an auto-hidden Dock, and popup continuity."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from gi.repository import Atspi
from dock_layout_smoke import descendants


def run(app, config_home, focus_studio, native_keys, native_click_node, test_app, start_app, set_app):
    path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = path.read_bytes()
    (Path('/tmp/deskmorph-desktop-test') / 'dock-keyboard-original.json').write_bytes(original)
    pids = []
    reports = []
    def stop():
        pid = app.get_process_id()
        assert f'DESKMORPH_CONFIG_HOME={config_home}'.encode() in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 7
        while Path(f'/proc/{pid}/stat').exists():
            try:
                if Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z': break
            except FileNotFoundError: break
            assert time.monotonic() < deadline
            time.sleep(.1)
    def start():
        nonlocal app
        app = start_app(); set_app(app); pids.append(app.get_process_id())
    def wait(predicate, message):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            result = predicate()
            if result: return result
            time.sleep(.1)
        print('FAIL', message, subprocess.check_output(['xprop','-root','_NET_ACTIVE_WINDOW'],text=True), flush=True)
        print([(n.get_role_name(), n.get_name(), n.get_state_set().contains(Atspi.StateType.FOCUSED)) for n in descendants(app) if n.get_role_name() in ('button','frame')], flush=True)
        raise AssertionError(message)
    def frame(title):
        return next(n for n in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == title)
    def focused(root):
        return next((n for n in descendants(root) if n.get_role_name() in ('button', 'toggle button', 'entry', 'slider') and n.get_state_set().contains(Atspi.StateType.FOCUSED)), None)
    def height():
        return frame('DeskMorph Taskbar').get_component_iface().get_extents(Atspi.CoordType.SCREEN).height
    try:
        for language in ('vi', 'en'):
            stop()
            fixture = json.loads(original)
            fixture['config'].update(language=language, autoHide=True, enabled=True, showApps=True, showAudio=True, showSystem=True, showClock=True, showShuffle=False)
            path.write_text(json.dumps(fixture)); start()
            focus_studio()
            studio = frame('DeskMorph Studio')
            nav = next(n for n in descendants(studio) if n.get_role_name() == 'button' and n.get_name() == 'Taskbar Studio')
            native_click_node(nav)  # Setup: also puts pointer away from the Dock edge.
            label = 'Điều khiển Dock bằng bàn phím' if language == 'vi' else 'Control Dock with keyboard'
            entry = wait(lambda: next((n for n in descendants(studio) if n.get_name() == label and n.get_role_name() == 'button'), None), 'Missing entry button')
            wait(lambda: height() <= 8, 'Dock never auto-hid before keyboard entry')
            assert entry.get_component_iface().grab_focus()
            time.sleep(.3)
            native_keys(chord=[0xff0d])
            dock = frame('DeskMorph Taskbar')
            first = 'Tìm ứng dụng' if language == 'vi' else 'Search applications'
            wait(lambda: focused(dock) and focused(dock).get_name() == first, 'Entry did not focus first Dock button')
            wait(lambda: height() > 30, 'Keyboard focus did not reveal Dock')
            time.sleep(8)
            assert height() > 30, 'Focused Dock hid after preview timeout'
            sequence = []
            sources = {'Tìm ứng dụng', 'Search applications', 'Âm thanh', 'Audio', 'Tiện ích hệ thống', 'System utilities', 'Mở lịch', 'Open calendar'}
            opened = []
            for _ in range(45):
                current = focused(dock)
                if current is None and len(opened) == 4: break
                assert current is not None, ('Dock lost DOM focus', sequence, opened)
                name = current.get_name(); assert name.strip(), 'Unnamed Dock control'
                if name in sequence: break
                sequence.append(name)
                if name in sources:
                    native_keys(chord=[0xff0d])
                    popup_title = 'DeskMorph Calendar' if name in ('Mở lịch', 'Open calendar') else 'DeskMorph Context Menu'
                    wait(lambda: any(n.get_role_name() == 'frame' and n.get_name() == popup_title for n in descendants(app)), 'Popup did not open: ' + name)
                    native_keys(chord=[0xff1b])
                    wait(lambda: focused(dock) and focused(dock).get_name() == name, 'Escape lost source focus: ' + name)
                    native_keys(chord=[0xff0d])
                    wait(lambda: any(n.get_role_name() == 'frame' and n.get_name() == popup_title for n in descendants(app)), 'Enter did not reopen: ' + name)
                    native_keys(chord=[0xff1b]); opened.append(name)
                    wait(lambda: focused(dock) and focused(dock).get_name() == name, 'Second Escape lost source focus')
                native_keys(chord=[0xff09])
            assert len(opened) == 4, (opened, sequence)
            # WebKit exposes one boundary stop after the final button.
            for name in reversed(sequence):
                native_keys(chord=[0xffe1, 0xff09])
                wait(lambda: focused(dock) and focused(dock).get_name() == name, 'Wrong reverse Tab target: ' + name)
            focus_studio()
            wait(lambda: height() <= 8, 'Dock stayed visible after native focus left')
            reports.append(dict(language=language, pid=app.get_process_id(), sequence=sequence, popupSources=opened, hiddenEntry=True, heldAfterPreview=True, escapeRestores=True, enterReopens=True, hidesAfterBlur=True, reverseMatches=True))
            print(json.dumps(reports[-1], ensure_ascii=False), flush=True)
    finally:
        stop(); path.write_bytes(original); start()
    result = dict(runs=reports, configRestored=path.read_bytes() == original, fixturePids=pids[:-1], normalPid=pids[-1], scope='Native X11 vi/en hidden Dock entry via Studio button, forward Tab names, four popup Enter/Escape/reopen paths; setup focus via AT-SPI. No screen reader or full popup control traversal claim.')
    Path('/tmp/deskmorph-desktop-test/dock-keyboard-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return app
