"""Focus ownership and keyboard continuity of native popup dismissal."""
import json
import os
import select
from pathlib import Path
import re
import subprocess
import time
from gi.repository import Atspi, GLib
from dock_layout_smoke import descendants


def run(app, config_home, click, focus_studio, native_keys, native_click_node, owned_input_pids):
    def node(name, role=None):
        try:
            return next((n for n in descendants(app) if n.get_name() == name and (role is None or n.get_role_name() == role)), None)
        except GLib.GError:
            return None  # AT-SPI nodes can disappear during an import review update; wait() retries.

    def frames():
        found = {}
        clients = subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True)
        for xid in re.findall(r'0x[0-9a-fA-F]+', clients):
            props = subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID', '_NET_WM_NAME'], text=True)
            if not re.search(r'_NET_WM_PID.*= ' + str(app.get_process_id()) + r'\b', props): continue
            title = re.search(r'_NET_WM_NAME\([^)]*\) = "(.*)"', props)
            if title: found[title.group(1)] = xid
        return found

    def active():
        raw = subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)
        value = re.search(r'0x[0-9a-fA-F]+', raw)
        return value.group(0) if value else None

    def wait(predicate, message):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(.1)
        raise AssertionError(message + f'; active={active()}, frames={frames()}')

    root = Path('/tmp/deskmorph-desktop-test')
    runtime_start = (root / 'runtime.log').stat().st_size
    config_path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    config = lambda: json.loads(config_path.read_text())['config']
    original = config()
    fixture = None
    popup_titles = {'DeskMorph Context Menu', 'DeskMorph Calendar'}
    passed = []

    def import_config(value, label):
        file = root / f'focus-{label}.json'
        file.write_text(json.dumps({'schemaVersion': 1, 'config': value}))
        # Clear only native file dialogs owned by this isolated app after an interrupted attempt.
        if node('Error', 'alert') is not None: click('OK', 'button')
        if node('Select File', 'file chooser') is not None: click('Cancel', 'button')
        focus_studio(); click('Hệ thống'); click('Nhập cấu hình'); focus_studio('Select File')
        native_keys(chord=[0xffe3, ord('l')]); native_keys(value=str(file)); native_keys(chord=[0xff0d])
        wait(lambda: node('Áp dụng cấu hình đã nhập', 'button') is not None, 'Import review not ready')
        click('Áp dụng cấu hình đã nhập')
        wait(lambda: config() == value, 'Focus fixture import did not persist')

    def has_text(value):
        return any(n.get_text_iface() and value in Atspi.Text.get_text(n.get_text_iface(), 0, -1) for n in descendants(app))

    def open_from_dock(button):
        focus_studio('DeskMorph Taskbar')
        assert node(button, 'button').get_component_iface().grab_focus()
        native_keys(chord=[0xff0d])
        wait(lambda: bool(popup_titles & frames().keys()), 'Dock popup not mapped')

    def stable_focus(xid, message):
        wait(lambda: active() == xid, message)
        deadline = time.monotonic() + .7
        while time.monotonic() < deadline:
            assert active() == xid, message + ': delayed callback stole focus'
            time.sleep(.1)

    def fixture_reply():
        assert select.select([fixture.stdout], [], [], 5)[0], 'Owned focus fixture did not reply'
        line = fixture.stdout.readline()
        assert line, 'Owned focus fixture exited early'
        return json.loads(line)

    try:
        initial = dict(original, language='vi', enabled=True, autoHide=False, showAudio=True, showSystem=True, showClock=True, showApps=True, launcherShortcut='Ctrl+Alt+Shift+J')
        import_config(initial, 'setup')
        focus_studio(); click('Hệ thống')
        wait(lambda: has_text('Phím tắt đang hoạt động: Ctrl+Alt+Shift+J'), 'Focus test chord unavailable')
        native_keys(chord=[0xffe3, 0xffe9, 0xffe1, ord('j')])
        wait(lambda: 'DeskMorph Context Menu' in frames(), 'Initial shortcut launcher did not open')
        native_keys(chord=[0xff1b])
        wait(lambda: not popup_titles & frames().keys(), 'Initial shortcut launcher did not dismiss')
        for button, popup in [('Tìm ứng dụng', 'DeskMorph Context Menu'), ('Âm thanh', 'DeskMorph Context Menu'), ('Tiện ích hệ thống', 'DeskMorph Context Menu'), ('Mở lịch', 'DeskMorph Calendar')]:
            focus_studio('DeskMorph Taskbar')
            assert node(button, 'button').get_component_iface().grab_focus()
            dock_xid = frames()['DeskMorph Taskbar']
            native_keys(chord=[0xff0d])
            wait(lambda: popup in frames() and active() == frames()[popup], button + ': Enter did not open/focus popup')
            native_keys(chord=[0xff1b])
            wait(lambda: not popup_titles & frames().keys(), button + ': Escape did not hide popup')
            wait(lambda: active() == dock_xid, button + ': Escape did not return native focus to Dock')
            time.sleep(.6)
            assert active() == dock_xid, 'Dismissal lost source focus after delayed callback'
            # No helper refocus: Enter must still reach the same source DOM button.
            native_keys(chord=[0xff0d])
            wait(lambda: popup in frames() and active() == frames()[popup], button + ': source DOM button did not retain keyboard focus')
            native_keys(chord=[0xff1b])
            wait(lambda: not popup_titles & frames().keys(), 'Second Escape failed')
            passed.append(button + ': keyboard Enter / Escape returns exact Dock XID and Enter reopens same source without helper refocus')
            print(passed[-1], flush=True)
        # Real outside click into the owned Studio header, for both native popup windows.
        for button in ['Tìm ứng dụng', 'Mở lịch', 'Âm thanh', 'Tiện ích hệ thống']:
            open_from_dock(button)
            studio = node('DeskMorph Studio', 'frame')
            studio_bounds = studio.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
            heading = node('DeskMorph', 'heading').get_component_iface().get_extents(Atspi.CoordType.SCREEN)
            point = (studio_bounds.x + studio_bounds.width - 30, heading.y + heading.height // 2)
            for title in popup_titles:
                popup = node(title, 'frame')
                if popup and popup.get_state_set().contains(Atspi.StateType.SHOWING):
                    rect = popup.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
                    assert not (rect.x <= point[0] < rect.x + rect.width and rect.y <= point[1] < rect.y + rect.height)
            native_click_node(studio, point=point)
            wait(lambda: not popup_titles & frames().keys(), 'Outside click did not hide ' + button)
            stable_focus(frames()['DeskMorph Studio'], 'Outside click did not retain Studio')
        passed.append('four popup modes: real outside click retains selected Studio XID across delayed callbacks')

        for button in ['Âm thanh', 'Tiện ích hệ thống']:
            open_from_dock(button); click('Đóng', 'button')
            wait(lambda: not popup_titles & frames().keys(), 'Close button did not hide popup')
            stable_focus(frames()['DeskMorph Taskbar'], 'Close button did not return Dock focus')
            native_keys(chord=[0xff0d])
            wait(lambda: 'DeskMorph Context Menu' in frames(), 'Close lost source button keyboard continuity')
            native_keys(chord=[0xff1b])
            wait(lambda: not popup_titles & frames().keys(), 'Escape failed after Close retry')
        passed.append('audio/system scoped Close buttons return Dock keyboard focus and Enter reopens original source')

        fixture = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('desktop_smoke.py').resolve()), '--window-fixture'],
            env=dict(os.environ, DESKMORPH_CONFIG_HOME=config_home), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        state = fixture_reply()
        assert fixture.poll() is None
        assert b'DESKMORPH_CONFIG_HOME=' + config_home.encode() in Path(f'/proc/{fixture.pid}/environ').read_bytes().split(b'\0')
        for window in state.values():
            props = subprocess.check_output(['xprop', '-id', window['xid'], '_NET_WM_PID', 'WM_CLASS'], text=True)
            assert re.search(r'_NET_WM_PID.*= ' + str(fixture.pid) + r'\b', props) and 'DeskMorphWindowFixture' in props
        owned_input_pids.add(fixture.pid)

        for button in ['Tìm ứng dụng', 'Mở lịch', 'Âm thanh', 'Tiện ích hệ thống']:
            open_from_dock(button)
            focus_studio(state['2']['title'], fixture.pid)
            wait(lambda: not popup_titles & frames().keys(), 'External focus did not hide popup: ' + button)
            stable_focus(state['2']['xid'], 'Popup stole selected external fixture focus')
        passed.append('four popup modes: selecting owned external GTK window dismisses and retains exact external XID')

        group = 'DeskMorphWindowFixture • 3 cửa sổ'
        wait(lambda: node(group, 'button') is not None, 'Owned window group missing')
        focus_studio('DeskMorph Taskbar')
        assert node(group, 'button').get_component_iface().grab_focus()
        native_keys(chord=[0xff0d])
        wait(lambda: 'DeskMorph Context Menu' in frames(), 'Window list did not open')
        native_keys(chord=[0xff1b])
        wait(lambda: not popup_titles & frames().keys(), 'Window list Escape did not hide')
        stable_focus(frames()['DeskMorph Taskbar'], 'Window list Escape did not return source Dock')
        native_keys(chord=[0xff0d])
        wait(lambda: node('DeskMorph Window Test 2', 'button') is not None or any(n.get_name().startswith('DeskMorph Window Test 2') and n.get_role_name() == 'button' for n in descendants(app)), 'Window list source button did not reopen')
        native_keys(chord=[0xff50]); native_keys(chord=[0xff54]); native_keys(chord=[0xff0d])
        wait(lambda: not popup_titles & frames().keys(), 'Selecting row did not hide list')
        stable_focus(state['2']['xid'], 'List activation stole selected external XID')
        passed.append('window list Escape returns source and Enter reopens; activating second row keeps exact external target focus')

        focus_studio('DeskMorph Taskbar')
        native_click_node(node(group, 'button'), button=3)
        wait(lambda: 'DeskMorph Context Menu' in frames(), 'Context menu did not open')
        native_keys(chord=[0xff1b])
        wait(lambda: not popup_titles & frames().keys(), 'Context menu Escape did not hide')
        stable_focus(frames()['DeskMorph Taskbar'], 'Context menu Escape lost source Dock')
        passed.append('right-click context menu Escape returns exact source Dock XID')

        focus_studio(); click('Hệ thống')
        wait(lambda: has_text('Phím tắt đang hoạt động: Ctrl+Alt+Shift+J'), 'Focus test chord unavailable; no shortcut input will be sent')
        focus_studio(state['1']['title'], fixture.pid)
        native_keys(chord=[0xffe3, 0xffe9, 0xffe1, ord('j')])
        wait(lambda: 'DeskMorph Context Menu' in frames() and active() == frames()['DeskMorph Context Menu'], 'Global shortcut launcher did not focus')
        native_keys(chord=[0xff1b])
        wait(lambda: not popup_titles & frames().keys(), 'Shortcut launcher Escape did not hide')
        stable_focus(state['1']['xid'], 'Shortcut Escape did not return original external source')
        passed.append('launcher global shortcut from external GTK window: Escape returns exact original external XID')

        focus_studio(state['1']['title'], fixture.pid)
        native_keys(chord=[0xffe3, 0xffe9, 0xffe1, ord('j')])
        wait(lambda: 'DeskMorph Context Menu' in frames(), 'Second shortcut launcher did not open')
        focus_studio(state['2']['title'], fixture.pid)
        wait(lambda: not popup_titles & frames().keys(), 'Shortcut popup focus loss did not dismiss')
        stable_focus(state['2']['xid'], 'Shortcut dismissal restored old source over newly selected window')
        passed.append('shortcut popup: external user selection wins over original source, without delayed restore')

        app_environment = Path(f'/proc/{app.get_process_id()}/environ').read_bytes().split(b'\0')
        delayed = b'DESKMORPH_TEST_POPUP_FOCUS_DELAY_MS=500' in app_environment
        trace = (root / 'runtime.log').read_bytes()[runtime_start:].decode(errors='replace')
        guarded = len(re.findall(r'deskmorph-popup-content-focus generation=\d+ active=true focused=false', trace))
        inactive = len(re.findall(r'deskmorph-popup-content-focus generation=\d+ active=false', trace))
        if delayed:
            assert guarded > 0, 'Delayed run did not exercise a live popup losing focus before its content callback'
        report = dict(pid=app.get_process_id(), fixturePid=fixture.pid, nativeContentFocusDelayMs=500 if delayed else 0, liveUnfocusedCallbacksSkipped=guarded, inactiveCallbacksSkipped=inactive, passed=passed)
        Path('/tmp/deskmorph-desktop-test/popup-focus-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(report, ensure_ascii=False), flush=True)
    finally:
        if fixture:
            owned_input_pids.discard(fixture.pid)
            if fixture.poll() is None: fixture.terminate()
            fixture.wait(timeout=5)
        if config() != original: import_config(original, 'restore')
        assert config() == original
