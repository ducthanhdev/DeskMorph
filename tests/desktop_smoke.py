#!/usr/bin/python3
"""Opt-in native UI checks via AT-SPI, restricted to the isolated test instance.
Run outside a sandbox with an existing X11 session. Never targets normal user instances.
"""
import argparse
import json
import os
import time
import subprocess
import re
import signal
import ctypes
from pathlib import Path
import gi

gi.require_version('Atspi', '2.0')
from gi.repository import Atspi

TEST_CONFIG = '/tmp/deskmorph-desktop-test/config'

def test_app():
    desktop = Atspi.get_desktop(0)
    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if app is None:
            continue
        if app.get_name() != 'deskmorph':
            continue
        try:
            env = Path(f'/proc/{app.get_process_id()}/environ').read_bytes().split(b'\0')
            if any(f'{key}={TEST_CONFIG}'.encode() in env for key in ('DESKMORPH_CONFIG_HOME', 'XDG_CONFIG_HOME')):
                return app
        except (OSError, TypeError):
            continue
    raise RuntimeError('Isolated DeskMorph test instance is not running')

def descendants(node, depth=0):
    if node is None or depth > 35:
        return
    yield node, depth
    for i in range(node.get_child_count()):
        yield from descendants(node.get_child_at_index(i), depth + 1)

def inspect(app):
    print('Test process:', app.get_process_id())
    x11 = ctypes.CDLL('libX11.so.6')
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XGetInputFocus.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int)]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    display = x11.XOpenDisplay(None)
    if display:
        focus, revert = ctypes.c_ulong(), ctypes.c_int()
        x11.XGetInputFocus(display, ctypes.byref(focus), ctypes.byref(revert))
        print('Native input focus:', hex(focus.value))
        x11.XCloseDisplay(display)
    for node, depth in descendants(app):
        role, name = node.get_role_name(), node.get_name()
        if name or role in ('push button', 'check box', 'slider', 'frame', 'text', 'entry'):
            print('  ' * depth + role + ': ' + str(name)[:140])

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--inspect', action='store_true')
    parser.add_argument('--action', action='append', default=[])
    parser.add_argument('--screenshot')
    parser.add_argument('--restart', action='store_true')
    parser.add_argument('--basic', action='store_true')
    parser.add_argument('--launcher-smoke', action='store_true')
    parser.add_argument('--exports-smoke', action='store_true')
    parser.add_argument('--pin-identity-smoke', action='store_true')
    parser.add_argument('--pinning-smoke', action='store_true')
    parser.add_argument('--missing-app-smoke', action='store_true')
    parser.add_argument('--launcher-keyboard-smoke', action='store_true')
    parser.add_argument('--icon-render-smoke', action='store_true')
    parser.add_argument('--preview-smoke', action='store_true')
    parser.add_argument('--capabilities-smoke', action='store_true')
    parser.add_argument('--localization-smoke', action='store_true')
    parser.add_argument('--removal-focus-smoke', action='store_true')
    parser.add_argument('--calendar-keyboard-smoke', action='store_true')
    parser.add_argument('--clock-smoke', action='store_true')
    parser.add_argument('--catalogue-refresh-smoke', action='store_true')
    parser.add_argument('--force-close-smoke', action='store_true')
    parser.add_argument('--popup-smoke', action='store_true')
    parser.add_argument('--focus-smoke', action='store_true')
    parser.add_argument('--focus-delay', action='store_true', help='Delay native popup content callback by 500 ms in debug build')
    parser.add_argument('--geometry-smoke', action='store_true')
    parser.add_argument('--autohide-smoke', action='store_true')
    parser.add_argument('--shortcut-smoke', action='store_true')
    parser.add_argument('--lifecycle-smoke', action='store_true')
    parser.add_argument('--registration-smoke', action='store_true')
    parser.add_argument('--studio-smoke', action='store_true')
    parser.add_argument('--config-smoke', action='store_true')
    parser.add_argument('--command-errors-smoke', action='store_true')
    parser.add_argument('--wallpaper-smoke', action='store_true')
    parser.add_argument('--scheduler-smoke', action='store_true')
    parser.add_argument('--scheduler-recovery-smoke', action='store_true')
    parser.add_argument('--system-open-smoke', action='store_true')
    parser.add_argument('--system-locations-smoke', action='store_true')
    parser.add_argument('--system-unavailable', action='store_true')
    parser.add_argument('--system-smoke', action='store_true')
    parser.add_argument('--audio-exit', action='store_true')
    parser.add_argument('--audio-tool-missing', action='store_true')
    parser.add_argument('--audio-unavailable', action='store_true')
    parser.add_argument('--media-smoke', action='store_true')
    parser.add_argument('--audio-smoke', action='store_true')
    parser.add_argument('--library-stress', action='store_true')
    parser.add_argument('--fixture', action='store_true')
    parser.add_argument('--window-fixture', action='store_true')
    parser.add_argument('--indicator-fixture', action='store_true')
    parser.add_argument('--mapping-fixture', action='store_true')
    parser.add_argument('--internal-fixture', action='store_true')
    parser.add_argument('--internal-smoke', action='store_true')
    parser.add_argument('--performance-matrix', action='store_true')
    parser.add_argument('--performance-smoke', action='store_true')
    parser.add_argument('--polling-smoke', action='store_true')
    parser.add_argument('--performance-trace', action='store_true')
    parser.add_argument('--mapping-smoke', action='store_true')
    parser.add_argument('--window-list-smoke', action='store_true')
    parser.add_argument('--reorder-smoke', action='store_true')
    parser.add_argument('--tooltip-smoke', action='store_true')
    parser.add_argument('--launch-smoke', action='store_true')
    parser.add_argument('--overflow-smoke', action='store_true')
    parser.add_argument('--layout-smoke', action='store_true')
    parser.add_argument('--indicator-smoke', action='store_true')
    parser.add_argument('--environment', action='store_true')
    parser.add_argument('--platform-tool-missing', action='store_true', help='Read-only startup check with an empty PATH in the isolated app')
    args = parser.parse_args()
    if args.performance_trace: args.performance_smoke = True
    if args.focus_delay: args.focus_smoke = True
    if args.audio_tool_missing: args.audio_unavailable = True
    if args.force_close_smoke: args.launcher_smoke = True
    if args.popup_smoke or args.focus_smoke: args.restart = True
    if args.geometry_smoke: args.restart = True
    if args.window_list_smoke or args.reorder_smoke or args.tooltip_smoke or args.launch_smoke or args.overflow_smoke or args.layout_smoke or args.indicator_smoke or args.mapping_smoke or args.internal_smoke or args.performance_smoke or args.polling_smoke: args.restart = True
    if args.platform_tool_missing: args.restart = True
    if args.scheduler_recovery_smoke: args.scheduler_smoke = True
    if args.scheduler_smoke: args.wallpaper_smoke = True
    if args.environment:
        for command in (['xprop', '-root', '_NET_ACTIVE_WINDOW'], ['gdbus', 'call', '--session', '--dest', 'org.gnome.ScreenSaver', '--object-path', '/org/gnome/ScreenSaver', '--method', 'org.gnome.ScreenSaver.GetActive']):
            result = subprocess.run(command, capture_output=True, text=True, timeout=5)
            print(result.stdout.strip() or result.stderr.strip())
        raise SystemExit(0)
    def require_unlocked_desktop():
        result = subprocess.run(['gdbus', 'call', '--session', '--dest', 'org.gnome.ScreenSaver', '--object-path', '/org/gnome/ScreenSaver', '--method', 'org.gnome.ScreenSaver.GetActive'], capture_output=True, text=True, timeout=4)
        if result.returncode != 0:
            raise RuntimeError('Cannot verify GNOME lock state; no native input will be sent')
        if re.search(r'\btrue\b', result.stdout):
            raise RuntimeError('GNOME desktop is locked; unlock it before native UI tests. No input was sent.')
    input_tests = any((args.removal_focus_smoke, args.calendar_keyboard_smoke, args.localization_smoke, args.performance_matrix, args.preview_smoke, args.capabilities_smoke, args.clock_smoke, args.icon_render_smoke, args.launcher_keyboard_smoke, args.missing_app_smoke, args.pinning_smoke, args.pin_identity_smoke, args.catalogue_refresh_smoke, args.exports_smoke, args.action, args.screenshot, args.basic, args.popup_smoke, args.focus_smoke, args.autohide_smoke, args.shortcut_smoke, args.lifecycle_smoke, args.registration_smoke, args.window_list_smoke, args.reorder_smoke, args.tooltip_smoke, args.launch_smoke, args.overflow_smoke, args.layout_smoke, args.indicator_smoke, args.mapping_smoke, args.internal_smoke, args.polling_smoke, args.launcher_smoke, args.studio_smoke, args.config_smoke, args.command_errors_smoke,
                       args.wallpaper_smoke, args.scheduler_smoke, args.library_stress, args.audio_smoke, args.media_smoke,
                       args.audio_exit, args.audio_unavailable, args.system_smoke, args.system_unavailable, args.system_open_smoke, args.system_locations_smoke))
    if input_tests or args.geometry_smoke: require_unlocked_desktop()
    if args.window_fixture or args.indicator_fixture or args.mapping_fixture or args.internal_fixture:
        if args.indicator_fixture or args.mapping_fixture or args.internal_fixture: assert os.environ.get('DESKMORPH_CONFIG_HOME') == TEST_CONFIG
        gi.require_version('Gtk', '3.0')
        gi.require_version('GdkX11', '3.0')
        from gi.repository import Gtk, GLib, GdkX11
        import sys
        fixture_windows = {}
        window_fixture_class = os.environ.get('DESKMORPH_WINDOW_FIXTURE_CLASS', 'DeskMorphWindowFixture') if args.window_fixture else 'DeskMorphWindowFixture'
        if window_fixture_class != 'DeskMorphWindowFixture':
            assert os.environ.get('DESKMORPH_CONFIG_HOME') == TEST_CONFIG
            assert re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,63}', window_fixture_class)
        def new_fixture_window(index):
            assert 1 <= index <= (12 if args.indicator_fixture else 8) and index not in fixture_windows
            window = Gtk.Window(title=f'DeskMorph {"Indicator" if args.indicator_fixture else "Window"} Test {index}')
            window.set_wmclass('deskmorph' if args.internal_fixture else 'deskmorph-mapping' if args.mapping_fixture else 'deskmorph-layout' if args.indicator_fixture else 'deskmorph-window-fixture', 'Deskmorph' if args.internal_fixture else 'DecodeTool' if args.mapping_fixture else 'DeskMorphLayout' if args.indicator_fixture else window_fixture_class)
            window.set_default_size(320, 180)
            window.set_focus_on_map(False)
            window.add(Gtk.Label(label=f'Cửa sổ kiểm thử {index}'))
            if index == 1:
                def confirm(window, event):
                    dialog = Gtk.MessageDialog(transient_for=window, modal=True, buttons=Gtk.ButtonsType.OK_CANCEL, text='Xác nhận đóng cửa sổ fixture')
                    dialog.set_title('DeskMorph Window Confirm')
                    dialog.connect('response', lambda d, response: (d.destroy(), window.destroy() if response == Gtk.ResponseType.OK else None))
                    dialog.show_all()
                    return True
                window.connect('delete-event', confirm)
            window.connect('destroy', lambda current: fixture_windows.pop(index, None))
            fixture_windows[index] = window
            window.show_all()
        def fixture_reply():
            print(json.dumps({str(index): {'xid': hex(GdkX11.X11Window.get_xid(window.get_window())), 'title': window.get_title()} for index, window in fixture_windows.items()}), flush=True)
        for index in ((1, 2) if args.indicator_fixture else (1, 2, 3)): new_fixture_window(index)
        fixture_reply()
        os.set_blocking(sys.stdin.fileno(), False)
        fixture_buffer = bytearray()
        def fixture_commands():
            try: chunk = os.read(sys.stdin.fileno(), 4096)
            except BlockingIOError: return True
            if not chunk: Gtk.main_quit(); return False
            fixture_buffer.extend(chunk)
            assert len(fixture_buffer) <= 8192
            while b'\n' in fixture_buffer:
                line, _, remainder = fixture_buffer.partition(b'\n'); fixture_buffer[:] = remainder
                request = json.loads(line)
                index = request['index']
                if request['action'] == 'add': new_fixture_window(index)
                elif request['action'] == 'close': fixture_windows[index].destroy()
                elif request['action'] == 'title': fixture_windows[index].set_title(request['title'])
                else: raise AssertionError('Unknown fixture action')
                fixture_reply()
            return True
        GLib.timeout_add(50, fixture_commands)
        Gtk.main()
        raise SystemExit(0)
    if args.fixture:
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        windows = []
        def confirm_close(window, event):
            dialog = Gtk.MessageDialog(transient_for=window, modal=True, message_type=Gtk.MessageType.QUESTION,
                                       buttons=Gtk.ButtonsType.NONE, text='Giữ cửa sổ khi chưa xác nhận đóng?')
            dialog.set_title('DeskMorph Smoke Confirm')
            dialog.add_button('Hủy', Gtk.ResponseType.CANCEL)
            dialog.add_button('Đóng', Gtk.ResponseType.OK)
            dialog.connect('response', lambda d, response: (d.destroy(), window.destroy() if response == Gtk.ResponseType.OK else None))
            dialog.show_all()
            return True
        for index in (1, 2):
            window = Gtk.Window(title=f'DeskMorph Smoke {index}')
            window.set_wmclass('deskmorph-smoke-fixture', 'DeskMorphSmokeFixture')
            window.set_default_size(320, 180)
            if index == 1:
                window.connect('delete-event', confirm_close)
            window.add(Gtk.Label(label=f'Cửa sổ mẫu {index} dành riêng cho kiểm thử DeskMorph'))
            window.show_all()
            windows.append(window)
        Gtk.main()
        raise SystemExit(0)
    if args.launcher_smoke:
        desktop_dir = Path('/tmp/deskmorph-desktop-test/data/applications')
        desktop_dir.mkdir(parents=True, exist_ok=True)
        script = Path(__file__).resolve()
        (desktop_dir / 'deskmorph-smoke-fixture.desktop').write_text(
            '[Desktop Entry]\nType=Application\nName=DeskMorph Smoke Fixture\n'
            f'Exec=/usr/bin/python3 "{script}" --fixture\n'
            'Icon=utilities-terminal\nStartupWMClass=DeskMorphSmokeFixture\nCategories=Utility;\n')
    if args.window_list_smoke:
        desktop_dir = Path('/tmp/deskmorph-desktop-test/data/applications')
        desktop_dir.mkdir(parents=True, exist_ok=True)
        (desktop_dir / 'deskmorph-window-fixture.desktop').write_text(
            '[Desktop Entry]\nType=Application\nName=DeskMorph Window Fixture\n'
            f'Exec=/usr/bin/python3 "{Path(__file__).resolve()}" --window-fixture\n'
            'Icon=utilities-terminal\nStartupWMClass=DeskMorphWindowFixture\nCategories=Utility;\n')
    if args.reorder_smoke:
        desktop_dir = Path('/tmp/deskmorph-desktop-test/data/applications')
        desktop_dir.mkdir(parents=True, exist_ok=True)
        for letter in 'ABC':
            (desktop_dir / f'deskmorph-reorder-{letter.lower()}.desktop').write_text(
                f'[Desktop Entry]\nType=Application\nName=DeskMorph Reorder {letter}\n'
                f'Exec=/usr/bin/touch /tmp/deskmorph-desktop-test/reorder-launched-{letter}\n'
                f'Icon=utilities-terminal\nStartupWMClass=DeskMorphReorder{letter}\nCategories=Utility;\n')
    if args.tooltip_smoke:
        tooltip_fixture_name = 'DeskMorph Tooltip — tên ứng dụng rất dài để kiểm tra hiển thị trong khung native và điều hướng bàn phím'
        desktop_dir = Path('/tmp/deskmorph-desktop-test/data/applications')
        desktop_dir.mkdir(parents=True, exist_ok=True)
        (desktop_dir / 'deskmorph-tooltip-fixture.desktop').write_text(
            f'[Desktop Entry]\nType=Application\nName={tooltip_fixture_name}\n'
            'Exec=/usr/bin/touch /tmp/deskmorph-desktop-test/tooltip-launched\n'
            'Icon=utilities-terminal\nStartupWMClass=DeskMorphTooltipFixture\nCategories=Utility;\n')
    if args.launch_smoke:
        launch_fixture_script = Path(__file__).resolve().with_name('launch_fixture.py')
        desktop_dir = Path('/tmp/deskmorph-desktop-test/data/applications')
        desktop_dir.mkdir(parents=True, exist_ok=True)
        for mode in ('multi', 'single'):
            actions = ('Actions=Compose;Private;\n'
                       '[Desktop Action Compose]\nName=Soạn tài liệu fixture\n'
                       f'Exec=/usr/bin/python3 "{launch_fixture_script}" action compose "two words"\n'
                       '[Desktop Action Private]\nName=Phiên riêng fixture\n'
                       f'Exec=/usr/bin/python3 "{launch_fixture_script}" action private\n') if mode == 'multi' else ''
            (desktop_dir / f'deskmorph-launch-{mode}.desktop').write_text(
                f'[Desktop Entry]\nType=Application\nName=DeskMorph Launch {mode}\n'
                f'Exec=/usr/bin/python3 "{launch_fixture_script}" {mode}\n'
                f'Icon=utilities-terminal\nStartupWMClass=DeskMorphLaunch{mode.title()}\nCategories=Utility;\n' + actions)
    if args.overflow_smoke:
        desktop_dir = Path('/tmp/deskmorph-desktop-test/data/applications')
        desktop_dir.mkdir(parents=True, exist_ok=True)
        for index in range(1, 41):
            (desktop_dir / f'deskmorph-overflow-{index:02}.desktop').write_text(
                f'[Desktop Entry]\nType=Application\nName=DeskMorph Overflow {index:02}\n'
                f'Exec=/usr/bin/touch /tmp/deskmorph-desktop-test/overflow-launched-{index:02}\n'
                f'Icon=utilities-terminal\nStartupWMClass=DeskMorphOverflow{index:02}\nCategories=Utility;\n')
    if args.layout_smoke or args.indicator_smoke:
        root = Path('/tmp/deskmorph-desktop-test')
        root.mkdir(parents=True, exist_ok=True)
        (root / 'layout-icon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><path fill="#ff00ff" d="M0 0h64v64H0z"/></svg>')
        desktop_dir = root / 'data/applications'
        desktop_dir.mkdir(parents=True, exist_ok=True)
        (desktop_dir / 'deskmorph-layout.desktop').write_text(
            '[Desktop Entry]\nType=Application\nName=DeskMorph Layout Fixture\n'
            'Exec=/usr/bin/touch /tmp/deskmorph-desktop-test/layout-launched\n'
            f'Icon={root / "layout-icon.svg"}\nStartupWMClass=DeskMorphLayout\nCategories=Utility;\n')
    if args.restart:
        try:
            previous = test_app()
            os.kill(previous.get_process_id(), signal.SIGTERM)
            time.sleep(0.7)
        except RuntimeError:
            pass
        test_root = Path('/tmp/deskmorph-desktop-test')
        test_root.mkdir(exist_ok=True)
        env = dict(os.environ, DESKMORPH_CONFIG_HOME=TEST_CONFIG,
                   XDG_DATA_HOME=str(test_root / 'data'), XDG_CACHE_HOME=str(test_root / 'cache'),
                   WEBKIT_DISABLE_DMABUF_RENDERER='1')
        if args.popup_smoke:
            # Hide system launchers through XDG user overrides, preserving the
            # system MIME, icon and GSettings directories needed by WebKit/GIO.
            from gi.repository import Gio
            safe_data = test_root / 'safe-data'
            safe_apps = safe_data / 'applications'
            safe_apps.mkdir(parents=True, exist_ok=True)
            for old in safe_apps.glob('*.desktop'): old.unlink()
            for installed in Gio.AppInfo.get_all():
                desktop_id = installed.get_id()
                if desktop_id and Path(desktop_id).name == desktop_id:
                    (safe_apps / desktop_id).write_text('[Desktop Entry]\nType=Application\nName=DeskMorph Hidden Fixture\nExec=/bin/false\nHidden=true\n')
            fixture_entry = test_root / 'data/applications/deskmorph-smoke-fixture.desktop'
            if fixture_entry.exists():
                (safe_apps / fixture_entry.name).write_bytes(fixture_entry.read_bytes())
            (safe_apps / 'deskmorph-stress-noop.desktop').write_text('[Desktop Entry]\nType=Application\nName=DeskMorph Stress Noop\nExec=/bin/true\n')
            env['XDG_DATA_HOME'] = str(safe_data)
        if args.polling_smoke: env['DESKMORPH_TRACE_COMMANDS'] = '1'
        if args.focus_smoke: env['DESKMORPH_TEST_POPUP_FOCUS_DELAY_MS'] = '500' if args.focus_delay else '0'
        if args.audio_unavailable: env['PULSE_SERVER'] = 'unix:/tmp/deskmorph-nonexistent-audio-service'
        if args.audio_tool_missing or args.platform_tool_missing:
            empty_path = test_root / 'empty-tool-path'
            empty_path.mkdir(exist_ok=True)
            assert not any(empty_path.iterdir()), 'The missing-tool test PATH must stay empty'
            env['PATH'] = str(empty_path)
        if args.system_unavailable: env['DBUS_SYSTEM_BUS_ADDRESS'] = 'unix:path=/tmp/deskmorph-nonexistent-system-bus'
        binary = Path(__file__).resolve().parents[1] / 'src-tauri/target/agent/debug/deskmorph'
        command = [str(binary)]
        if args.performance_trace:
            command = ['strace', '-f', '-qq', '-ttt', '-e', 'trace=execve', '-o', str(test_root / 'performance-execve.log'), str(binary)]
        startup_started = time.monotonic()
        with (test_root / 'runtime.log').open('a') as log:
            process = subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True)
        for _ in range(50):
            time.sleep(0.2)
            if process.poll() is not None:
                raise RuntimeError('Test app exited: ' + (test_root / 'runtime.log').read_text()[-1500:])
            try:
                app = test_app()
                if any(n.get_role_name() == 'button' for n, _ in descendants(app)):
                    break
            except RuntimeError:
                continue
        else:
            raise RuntimeError('Timed out waiting for test app UI')
    app = test_app()
    startup_ready_seconds = time.monotonic() - startup_started if args.restart else None
    if args.platform_tool_missing:
        observed = ''
        for _ in range(50):
            texts = []
            for node, _ in descendants(app):
                texts.append(node.get_name() or '')
                interface = node.get_text_iface()
                if interface: texts.append(Atspi.Text.get_text(interface, 0, -1))
            observed = '\n'.join(texts)
            if 'xprop_unavailable' in observed: break
            time.sleep(0.1)
        assert 'xprop_unavailable' in observed, 'Missing xprop capability error did not reach Studio'
        assert any(node.get_name() in ('Tìm ứng dụng', 'Search applications') for node, _ in descendants(app)), 'Dock launcher disappeared when window management was unavailable'
        report = {'passed': ['missing xprop reaches Studio capability status', 'Dock and launcher remain available'], 'pid': app.get_process_id(), 'inputSent': False}
        Path('/tmp/deskmorph-desktop-test/platform-tool-missing-result.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
    owned_input_pids = set()
    def click(name, role=None):
        require_unlocked_desktop()
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            candidates = [node for node, _ in descendants(app) if node.get_name() == name and (role is None or node.get_role_name() == role) and node.get_role_name() in ('button', 'check box', 'toggle button', 'menu item', 'radio button')]
            if len(candidates) != 1:
                raise RuntimeError(f'Expected one actionable {name!r}, found {len(candidates)}')
            states = candidates[0].get_state_set()
            if states.contains(Atspi.StateType.ENABLED) and states.contains(Atspi.StateType.SENSITIVE): break
            time.sleep(0.1)
        else: raise RuntimeError(f'Action stayed disabled: {name}')
        action = candidates[0].get_action_iface()
        require_unlocked_desktop()
        if not action or not action.do_action(0):
            raise RuntimeError(f'Action failed: {name}')
        time.sleep(0.7)
    def focus_studio(title="DeskMorph Studio", target_pid=None):
        require_unlocked_desktop()
        target_pid = app.get_process_id() if target_pid is None else target_pid
        assert target_pid == app.get_process_id() or target_pid in owned_input_pids, 'Focus target is not an owned test process'
        gi.require_version('Gdk', '3.0')
        gi.require_version('GdkX11', '3.0')
        from gi.repository import Gdk, GdkX11
        clients = subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True)
        for xid in re.findall(r'0x[0-9a-fA-F]+', clients):
            properties = subprocess.run(['xprop', '-id', xid, '_NET_WM_PID', '_NET_WM_NAME'], capture_output=True, text=True).stdout
            pid = re.search(r'_NET_WM_PID.*= (\d+)', properties)
            if pid and int(pid.group(1)) == target_pid and title in properties:
                active = subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)
                if re.search(r'0x[0-9a-fA-F]+', active).group(0) == xid:
                    return
                # Ask the window manager to activate this client. Direct GDK focus can
                # leave _NET_ACTIVE_WINDOW at 0 and race GNOME's focus notifications.
                class Message(ctypes.Structure):
                    _fields_ = [('type', ctypes.c_int), ('serial', ctypes.c_ulong), ('send_event', ctypes.c_int), ('display', ctypes.c_void_p), ('window', ctypes.c_ulong), ('message_type', ctypes.c_ulong), ('format', ctypes.c_int), ('data', ctypes.c_long * 5)]
                class Event(ctypes.Union): _fields_ = [('client', Message), ('pad', ctypes.c_long * 24)]
                x11 = ctypes.CDLL('libX11.so.6'); x11.XOpenDisplay.restype = ctypes.c_void_p; x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
                x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]; x11.XDefaultRootWindow.restype = ctypes.c_ulong
                x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]; x11.XInternAtom.restype = ctypes.c_ulong
                x11.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long, ctypes.POINTER(Event)]
                x11.XFlush.argtypes = [ctypes.c_void_p]; x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
                display = x11.XOpenDisplay(None); assert display
                try:
                    event = Event(); event.client.type = 33; event.client.send_event = 1; event.client.display = display; event.client.window = int(xid, 16)
                    event.client.message_type = x11.XInternAtom(display, b'_NET_ACTIVE_WINDOW', 0); event.client.format = 32
                    event.client.data[0] = 2
                    assert x11.XSendEvent(display, x11.XDefaultRootWindow(display), 0, (1 << 19) | (1 << 20), ctypes.byref(event)); x11.XFlush(display)
                finally: x11.XCloseDisplay(display)
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    active = subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)
                    if re.search(r'0x[0-9a-fA-F]+', active).group(0) == xid:
                        time.sleep(0.15)
                        return
                    time.sleep(0.05)
                raise AssertionError('Window manager did not activate isolated target window')
        raise AssertionError('Cannot focus isolated Studio window')
    def reopen_studio():
        require_unlocked_desktop()
        test_root = Path('/tmp/deskmorph-desktop-test')
        env = dict(os.environ, DESKMORPH_CONFIG_HOME=TEST_CONFIG, XDG_DATA_HOME=str(test_root / 'data'),
                   XDG_CACHE_HOME=str(test_root / 'cache'), WEBKIT_DISABLE_DMABUF_RENDERER='1')
        binary = Path(__file__).resolve().parents[1] / 'src-tauri/target/agent/debug/deskmorph'
        subprocess.run([str(binary)], env=env, timeout=5, check=True, capture_output=True)
        time.sleep(0.7)
    def start_isolated_app(binary_override=None, env_overrides=None):
        require_unlocked_desktop()
        test_root = Path('/tmp/deskmorph-desktop-test')
        env = dict(os.environ, DESKMORPH_CONFIG_HOME=TEST_CONFIG, XDG_DATA_HOME=str(test_root / 'data'),
                   XDG_CACHE_HOME=str(test_root / 'cache'), WEBKIT_DISABLE_DMABUF_RENDERER='1')
        binary = Path(__file__).resolve().parents[1] / 'src-tauri/target/agent/debug/deskmorph'
        if env_overrides: env.update(env_overrides)
        if binary_override is not None: binary = binary_override
        with (test_root / 'runtime.log').open('a') as log:
            launched = subprocess.Popen([str(binary)], env=env, stdout=log, stderr=log, start_new_session=True)
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if launched.poll() is not None: raise AssertionError('Fresh isolated app exited during startup')
            time.sleep(0.2)
            try:
                candidate = test_app()
                if candidate.get_process_id() == launched.pid and any(n.get_role_name() == 'button' for n, _ in descendants(candidate)): return candidate
            except RuntimeError: pass
        # This Popen belongs to this helper even if AT-SPI never exposed it.
        # Do not leave an unrecognized fixture running after a readiness failure.
        if launched.poll() is None: launched.terminate()
        launched.wait(timeout=5)
        raise AssertionError('Fresh isolated app did not become accessible')
    def close_studio_native():
        require_unlocked_desktop()
        clients = subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True)
        for xid in re.findall(r'0x[0-9a-fA-F]+', clients):
            properties = subprocess.run(['xprop', '-id', xid, '_NET_WM_PID', '_NET_WM_NAME'], capture_output=True, text=True).stdout
            pid = re.search(r'_NET_WM_PID.*= (\d+)', properties)
            if pid and int(pid.group(1)) == app.get_process_id() and 'DeskMorph Studio' in properties:
                break
        else: raise AssertionError('Isolated Studio window not found')
        class Message(ctypes.Structure):
            _fields_ = [('type', ctypes.c_int), ('serial', ctypes.c_ulong), ('send_event', ctypes.c_int),
                        ('display', ctypes.c_void_p), ('window', ctypes.c_ulong), ('message_type', ctypes.c_ulong),
                        ('format', ctypes.c_int), ('data', ctypes.c_long * 5)]
        class Event(ctypes.Union):
            _fields_ = [('client', Message), ('pad', ctypes.c_long * 24)]
        x11 = ctypes.CDLL('libX11.so.6')
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        x11.XInternAtom.restype = ctypes.c_ulong
        x11.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long, ctypes.POINTER(Event)]
        x11.XFlush.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        display = x11.XOpenDisplay(None)
        assert display
        try:
            event = Event()
            event.client.type = 33; event.client.display = display; event.client.window = int(xid, 16)
            event.client.message_type = x11.XInternAtom(display, b'WM_PROTOCOLS', 0)
            event.client.format = 32; event.client.data[0] = x11.XInternAtom(display, b'WM_DELETE_WINDOW', 0)
            assert x11.XSendEvent(display, int(xid, 16), 0, 0, ctypes.byref(event))
            x11.XFlush(display)
        finally: x11.XCloseDisplay(display)
        time.sleep(0.7)
        assert xid not in re.findall(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True)), 'Studio was not hidden by close'
    def native_keys(value=None, chord=None):
        assert not (chord and 0xffe3 in chord and 0xffe9 in chord and any(0xffbe <= sym <= 0xffc9 for sym in chord)), 'Never send virtual-terminal switching chords'
        require_unlocked_desktop()
        active = subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)
        xid = re.search(r'0x[0-9a-fA-F]+', active).group(0)
        pid = subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID'], text=True)
        focused_pid = int(pid.split('=')[1].strip())
        assert focused_pid == app.get_process_id() or focused_pid in owned_input_pids, 'Keyboard focus left isolated app and explicitly owned fixture'
        x11 = ctypes.CDLL('libX11.so.6')
        xtst = ctypes.CDLL('libXtst.so.6')
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        x11.XKeysymToKeycode.restype = ctypes.c_uint
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]; x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XQueryPointer.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_uint)]
        x11.XkbLookupKeySym.argtypes = [ctypes.c_void_p, ctypes.c_ubyte, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_ulong)]
        x11.XkbLookupKeySym.restype = ctypes.c_int
        x11.XFlush.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        display = x11.XOpenDisplay(None)
        assert display
        def key(keysym, down):
            code = x11.XKeysymToKeycode(display, keysym)
            assert code
            xtst.XTestFakeKeyEvent(display, code, down, 0)
        try:
            if chord:
                for sym in chord: key(sym, 1)
                for sym in reversed(chord): key(sym, 0)
            if value is not None:
                # Preserve lock modifiers; do not toggle the user's Caps Lock.
                root, child = ctypes.c_ulong(), ctypes.c_ulong()
                rx, ry, wx, wy, mask = ctypes.c_int(), ctypes.c_int(), ctypes.c_int(), ctypes.c_int(), ctypes.c_uint()
                assert x11.XQueryPointer(display, x11.XDefaultRootWindow(display), ctypes.byref(root), ctypes.byref(child), ctypes.byref(rx), ctypes.byref(ry), ctypes.byref(wx), ctypes.byref(wy), ctypes.byref(mask))
                assert not mask.value & (1 | 4 | 8 | 64), 'A non-lock keyboard modifier is held; no text will be typed'
                def symbol(code, state):
                    consumed, result = ctypes.c_uint(), ctypes.c_ulong()
                    assert x11.XkbLookupKeySym(display, code, state, ctypes.byref(consumed), ctypes.byref(result))
                    return result.value
                key(0xffe3, 1)
                key(ord('a'), 1); key(ord('a'), 0); key(0xffe3, 0)
                if value == '': key(0xff08, 1); key(0xff08, 0)
                for char in value:
                    assert char in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -./+', 'Test helper accepts bounded ASCII only'
                    code = x11.XKeysymToKeycode(display, ord(char))
                    shifted = symbol(code, mask.value & ~1) != ord(char)
                    assert not shifted or symbol(code, mask.value | 1) == ord(char), 'Test character needs an unsupported keymap level'
                    if shifted: key(0xffe1, 1)
                    key(ord(char), 1); key(ord(char), 0)
                    if shifted: key(0xffe1, 0)
            x11.XFlush(display)
        finally:
            x11.XCloseDisplay(display)
        if chord or value is not None: time.sleep(0.4)
    def assert_pointer_over_test_app():
        require_unlocked_desktop()
        x11 = ctypes.CDLL('libX11.so.6')
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]; x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XQueryPointer.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_uint)]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        display = x11.XOpenDisplay(None); assert display
        try:
            current = x11.XDefaultRootWindow(display)
            observed_owners = []
            for _ in range(12):
                root, child = ctypes.c_ulong(), ctypes.c_ulong()
                rx, ry, wx, wy, mask = ctypes.c_int(), ctypes.c_int(), ctypes.c_int(), ctypes.c_int(), ctypes.c_uint()
                assert x11.XQueryPointer(display, current, ctypes.byref(root), ctypes.byref(child), ctypes.byref(rx), ctypes.byref(ry), ctypes.byref(wx), ctypes.byref(wy), ctypes.byref(mask))
                if not child.value: break
                current = child.value
                props = subprocess.run(['xprop', '-id', hex(current), '_NET_WM_PID'], capture_output=True, text=True).stdout
                owner = re.search(r'_NET_WM_PID.*= (\d+)', props)
                if owner:
                    if int(owner.group(1)) == app.get_process_id(): return
                    # A WM-owned decoration can wrap our client. Follow the
                    # actual child under the pointer before rejecting ownership.
                    observed_owners.append((hex(current), int(owner.group(1))))
            raise AssertionError('Cannot establish isolated ownership of window under pointer; no click will be sent; observed=' + str(observed_owners))
        finally: x11.XCloseDisplay(display)
    def native_click_node(node, button=1, point=None):
        assert button in (1, 2, 3)
        # Verify focus belongs to our isolated PID before moving the real pointer.
        native_keys()
        rect = node.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        assert rect.width > 0 and rect.height > 0 and node.get_state_set().contains(Atspi.StateType.SHOWING)
        x, y = point or (rect.x + rect.width // 2, rect.y + rect.height // 2)
        assert rect.x <= x < rect.x + rect.width and rect.y <= y < rect.y + rect.height
        x11 = ctypes.CDLL('libX11.so.6'); xtst = ctypes.CDLL('libXtst.so.6')
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XFlush.argtypes = [ctypes.c_void_p]; x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
        xtst.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        display = x11.XOpenDisplay(None)
        assert display
        try:
            assert xtst.XTestFakeMotionEvent(display, -1, x, y, 0)
            x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]; x11.XSync(display, 0)
            assert_pointer_over_test_app()
            assert xtst.XTestFakeButtonEvent(display, button, 1, 0)
            assert xtst.XTestFakeButtonEvent(display, button, 0, 0)
            x11.XFlush(display)
        finally: x11.XCloseDisplay(display)
        time.sleep(0.4)
    def type_entry(name, value):
        focus_studio()
        entry = next(n for n, _ in descendants(app) if n.get_name() == name and n.get_role_name() == 'entry')
        assert entry.get_component_iface().grab_focus(), 'Cannot focus isolated text field'
        time.sleep(0.3)
        native_keys(value=value)
        text = entry.get_text_iface()
        assert text and Atspi.Text.get_text(text, 0, -1) == value, 'Native typing did not update the intended field'
    for name in args.action:
        click(name)
    if args.autohide_smoke:
        path = Path(TEST_CONFIG) / 'com.ducthanhdev.deskmorph/config.json'
        config = lambda: json.loads(path.read_text())['config']
        original = config()
        focus_studio()
        click('Taskbar Studio')
        heading = next(n for n, _ in descendants(app) if n.get_role_name() == 'heading' and n.get_name() == 'DeskMorph')
        dock = next(n for n, _ in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Taskbar')
        def dock_rect(): return dock.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        def wait_hide(predicate, message):
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                if predicate(): return
                time.sleep(0.1)
            rect = dock_rect()
            active = subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True).strip()
            frames = [n.get_name() for n, _ in descendants(app) if n.get_role_name() == 'frame' and n.get_state_set().contains(Atspi.StateType.SHOWING)]
            raise AssertionError(message + f': Dock={rect.x},{rect.y},{rect.width},{rect.height}; {active}; showing={frames}')
        def move_to(node):
            require_unlocked_desktop()
            native_keys()  # Retain the isolated-app focus guard for real input.
            rect = node.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
            assert rect.width > 0 and rect.height > 0
            x11 = ctypes.CDLL('libX11.so.6'); xtst = ctypes.CDLL('libXtst.so.6')
            x11.XOpenDisplay.restype = ctypes.c_void_p
            x11.XFlush.argtypes = [ctypes.c_void_p]; x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
            xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
            display = x11.XOpenDisplay(None); assert display
            try:
                require_unlocked_desktop()
                assert xtst.XTestFakeMotionEvent(display, -1, rect.x + rect.width // 2, rect.y + rect.height // 2, 0)
                x11.XFlush(display)
            finally: x11.XCloseDisplay(display)
            return (rect.x + rect.width // 2, rect.y + rect.height // 2)
        def pointer_position():
            x11 = ctypes.CDLL('libX11.so.6')
            x11.XOpenDisplay.restype = ctypes.c_void_p
            x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]; x11.XDefaultRootWindow.restype = ctypes.c_ulong
            x11.XQueryPointer.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_uint)]
            x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
            display = x11.XOpenDisplay(None); assert display
            try:
                root, child = ctypes.c_ulong(), ctypes.c_ulong()
                x, y, win_x, win_y, mask = ctypes.c_int(), ctypes.c_int(), ctypes.c_int(), ctypes.c_int(), ctypes.c_uint()
                assert x11.XQueryPointer(display, x11.XDefaultRootWindow(display), ctypes.byref(root), ctypes.byref(child), ctypes.byref(x), ctypes.byref(y), ctypes.byref(win_x), ctypes.byref(win_y), ctypes.byref(mask))
                return (x.value, y.value)
            finally: x11.XCloseDisplay(display)
        def set_auto(value):
            if config()['autoHide'] != value:
                click('Tự động ẩn Dock Chạm cạnh màn hình để hiện lại; Dock giữ hiện khi bạn thao tác popup.')
        passed = []
        try:
            if not config()['enabled']: click('Bật Dock')
            for position in ('top', 'bottom'):
                focus_studio()
                set_auto(False)
                click('Trên đỉnh màn hình' if position == 'top' else 'Dưới đáy (Đề xuất)')
                move_to(heading)
                set_auto(True)
                wait_hide(lambda: dock_rect().height <= 4, f'{position}: Dock did not hide')
                move_to(dock)
                wait_hide(lambda: dock_rect().height > 4, f'{position}: edge did not reveal Dock')
                time.sleep(0.35)  # Native size settles before the CSS slide finishes.
                target = move_to(dock)
                time.sleep(0.8)
                assert pointer_position() == target, 'Pointer moved during hover test; cannot attribute result to DeskMorph'
                assert dock_rect().height > 4, f'{position}: Dock hid while pointer was over its surface'
                move_to(heading)
                wait_hide(lambda: dock_rect().height <= 4, f'{position}: pointer leaving surface did not hide Dock')
                move_to(dock)
                wait_hide(lambda: dock_rect().height > 4, f'{position}: edge did not reveal before calendar')
                click('Mở lịch')
                move_to(heading)
                time.sleep(0.8)
                assert dock_rect().height > 4, f'{position}: Dock hid while calendar was open'
                native_keys(chord=[0xff1b])
                wait_hide(lambda: dock_rect().height <= 4, f'{position}: Dock did not hide after Escape')
                move_to(dock)
                wait_hide(lambda: dock_rect().height > 4, f'{position}: edge did not reveal Dock again')
                click('Âm thanh', 'button')
                move_to(heading)
                time.sleep(0.8)
                assert dock_rect().height > 4, f'{position}: Dock hid while audio was open'
                focus_studio()
                click('Bật Dock')
                wait_hide(lambda: not any(n.get_role_name() in ('slider', 'check box') and n.get_name() in ('Âm lượng', 'Tắt tiếng') and n.get_state_set().contains(Atspi.StateType.SHOWING) for n, _ in descendants(app)), f'{position}: disabling Dock left audio visible')
                click('Bật Dock')
                passed.append(position + ': hide, edge reveal, calendar/audio keep visible, Escape and disable')
        finally:
            try: app = test_app()
            except RuntimeError:
                reopen_studio()
                app = test_app()
            focus_studio()
            if config()['enabled'] != original['enabled']: click('Bật Dock')
            set_auto(original['autoHide'])
            if config()['position'] != original['position']:
                click('Trên đỉnh màn hình' if original['position'] == 'top' else 'Dưới đáy (Đề xuất)')
        report = {'passed': passed, 'pid': app.get_process_id(), 'preferencesRestored': True}
        Path('/tmp/deskmorph-desktop-test/autohide-result.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
    if args.preview_smoke:
        from preview_smoke import run
        app = run(app, TEST_CONFIG, click, focus_studio, native_keys, test_app, start_isolated_app, lambda current: globals().__setitem__('app', current), require_unlocked_desktop, assert_pointer_over_test_app)
    if args.removal_focus_smoke:
        from removal_focus_smoke import run
        app = run(app, TEST_CONFIG, click, focus_studio, native_keys, test_app, start_isolated_app, lambda current: globals().__setitem__("app", current))
    if args.calendar_keyboard_smoke:
        from calendar_keyboard_smoke import run
        run(app, click, focus_studio, native_keys)
    if args.localization_smoke:
        from localization_smoke import run
        app = run(app, TEST_CONFIG, click, focus_studio, native_keys, test_app, start_isolated_app, lambda current: globals().__setitem__('app', current), native_click_node)
    if args.capabilities_smoke:
        from capabilities_smoke import run
        app = run(app, TEST_CONFIG, click, focus_studio, native_keys, test_app, start_isolated_app, lambda current: globals().__setitem__('app', current))
    if args.clock_smoke:
        from clock_smoke import run
        app = run(app, TEST_CONFIG, click, focus_studio, native_keys, test_app, start_isolated_app, lambda current: globals().__setitem__('app', current))
    if args.system_locations_smoke:
        from system_locations_smoke import run
        app = run(app, TEST_CONFIG, click, focus_studio, native_keys, test_app, start_isolated_app, lambda current: globals().__setitem__('app', current))
    if args.icon_render_smoke:
        from icon_render_smoke import run
        app = run(app, TEST_CONFIG, click, focus_studio, native_keys, test_app, start_isolated_app, lambda current: globals().__setitem__('app', current))
    if args.launcher_keyboard_smoke:
        from launcher_keyboard_smoke import run
        app = run(app, TEST_CONFIG, click, focus_studio, native_keys, test_app, start_isolated_app, lambda current: globals().__setitem__('app', current))
    if args.missing_app_smoke:
        from missing_app_smoke import run
        app = run(app, TEST_CONFIG, click, focus_studio, native_keys, native_click_node, test_app, start_isolated_app, lambda current: globals().__setitem__('app', current))
    if args.pinning_smoke:
        from pinning_smoke import run
        app = run(app, TEST_CONFIG, click, focus_studio, native_keys, test_app, start_isolated_app, lambda current: globals().__setitem__('app', current))
    if args.pin_identity_smoke:
        from pin_identity_smoke import run
        app = run(app, TEST_CONFIG, click, focus_studio, native_keys, native_click_node, test_app, start_isolated_app, lambda current: globals().__setitem__('app', current))
    if args.catalogue_refresh_smoke:
        from catalogue_refresh_smoke import run
        app = run(app, TEST_CONFIG, click, focus_studio, native_keys, test_app, start_isolated_app, lambda current: globals().__setitem__('app', current))
    if args.exports_smoke:
        from exports_smoke import run
        app = run(app, TEST_CONFIG, click, focus_studio, native_keys, test_app, start_isolated_app, lambda current: globals().__setitem__('app', current))
    # The dedicated case above exercises auto-hide. Other cases interact with
    # a fully shown Dock; AT-SPI actions on off-screen children are not a real
    # user interaction and can leave the popup unfocused during native resize.
    if any((args.popup_smoke, args.focus_smoke, args.shortcut_smoke, args.audio_smoke, args.media_smoke, args.launcher_smoke)):
        baseline_path = Path(TEST_CONFIG) / 'com.ducthanhdev.deskmorph/config.json'
        focus_studio()
        click('Taskbar Studio')
        if json.loads(baseline_path.read_text())['config']['autoHide']:
            click('Tự động ẩn Dock Chạm cạnh màn hình để hiện lại; Dock giữ hiện khi bạn thao tác popup.')
    if args.layout_smoke:
        from dock_layout_smoke import run
        run(app, TEST_CONFIG, click, focus_studio, native_keys, native_click_node, require_unlocked_desktop, assert_pointer_over_test_app)
    if args.geometry_smoke:
        from geometry_smoke import run
        run(app, TEST_CONFIG, click, focus_studio, native_keys)
    if args.polling_smoke:
        from polling_smoke import run
        try:
            run(app, TEST_CONFIG, click, focus_studio, native_keys, native_click_node, require_unlocked_desktop, assert_pointer_over_test_app, close_studio_native, reopen_studio)
        finally:
            assert test_app().get_process_id() == app.get_process_id()
            os.kill(app.get_process_id(), signal.SIGTERM)
            process.wait(timeout=5)
            app = start_isolated_app()
    if args.performance_matrix:
        from performance_matrix import run
        app = run(app, TEST_CONFIG, click, focus_studio, native_keys, test_app, start_isolated_app, lambda current: globals().__setitem__('app', current), close_studio_native, reopen_studio, require_unlocked_desktop, assert_pointer_over_test_app)
    if args.performance_smoke:
        from performance_smoke import run
        try:
            run(app, TEST_CONFIG, startup_ready_seconds, args.performance_trace)
        finally:
            if args.performance_trace:
                assert test_app().get_process_id() == app.get_process_id()
                os.kill(app.get_process_id(), signal.SIGTERM)
                process.wait(timeout=5)
                app = start_isolated_app()
    if args.internal_smoke:
        from dock_internal_smoke import run
        run(app, TEST_CONFIG, click, focus_studio, native_keys, native_click_node, owned_input_pids)
    if args.mapping_smoke:
        from dock_mapping_smoke import run
        def restart_mapping_app():
            global app
            require_unlocked_desktop()
            assert test_app().get_process_id() == app.get_process_id()
            os.kill(app.get_process_id(), signal.SIGTERM)
            time.sleep(.7)
            app = start_isolated_app()
            return app
        run(app, TEST_CONFIG, click, focus_studio, native_keys, native_click_node, owned_input_pids, restart_mapping_app)
    if args.indicator_smoke:
        from dock_indicator_smoke import run
        run(app, TEST_CONFIG, click, focus_studio, native_keys, owned_input_pids)
    if args.overflow_smoke:
        gi.require_version('Gdk', '3.0'); gi.require_version('GdkX11', '3.0')
        from gi.repository import Gdk, GdkX11
        overflow_path = Path(TEST_CONFIG) / 'com.ducthanhdev.deskmorph/config.json'
        overflow_config = lambda: json.loads(overflow_path.read_text())['config']
        overflow_original = overflow_config()
        overflow_root = Path('/tmp/deskmorph-desktop-test')
        markers = [overflow_root / f'overflow-launched-{index:02}' for index in range(1, 41)]
        assert not any(marker.exists() for marker in markers), 'Do not overwrite existing overflow markers'
        assert not any(pin.get('desktopId', '').startswith('deskmorph-overflow-') for pin in overflow_original['pinnedApps'])
        overflow_passed = []
        def wait_overflow(predicate, message):
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if predicate(): return
                time.sleep(0.1)
            raise AssertionError(message)
        def overflow_button(name): return next((n for n, _ in descendants(app) if n.get_role_name() == 'button' and n.get_name() == name), None)
        def fixture_pin(index): return overflow_button(f'DeskMorph Overflow {index:02} • 0 cửa sổ')
        def overflow_rect(node): return node.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        def dock_frame(): return next(n for n, _ in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Taskbar')
        def import_overflow(config, label):
            file = overflow_root / ('overflow-' + label + '.json')
            file.write_text(json.dumps({'schemaVersion': 1, 'config': config}))
            focus_studio(); click('Hệ thống'); click('Nhập cấu hình'); focus_studio('Select File')
            native_keys(chord=[0xffe3, ord('l')]); native_keys(value=str(file)); native_keys(chord=[0xff0d])
            time.sleep(0.8); click('Áp dụng cấu hình đã nhập')
            wait_overflow(lambda: overflow_config() == config, 'Reviewed overflow import did not persist')
        def scroll_overflow(direction):
            name = 'Cuộn ứng dụng sang phải' if direction == 1 else 'Cuộn ứng dụng sang trái'
            for _ in range(10):
                node = overflow_button(name)
                assert node is not None, 'Overflow arrow disappeared'
                if not node.get_state_set().contains(Atspi.StateType.ENABLED): return
                focus_studio(); native_click_node(node)
                time.sleep(0.4)
            raise AssertionError('Overflow arrow did not reach content boundary')
        fixture_pins = [dict(id=f'deskmorph-overflow-{index:02}.desktop', desktopId=f'deskmorph-overflow-{index:02}.desktop', name=f'DeskMorph Overflow {index:02}', command=f'desktop:deskmorph-overflow-{index:02}.desktop', matchClasses=[f'DeskMorphOverflow{index:02}'], iconType='custom', enabled=True) for index in range(1, 41)]
        try:
            small = dict(overflow_original, enabled=True, autoHide=False, showApps=True, position='top', height=52, iconSize=36, iconSpacing=8, showStats=True, showClock=True, showAudio=True, pinnedApps=overflow_original['pinnedApps'] + fixture_pins[:2])
            import_overflow(small, 'small')
            wait_overflow(lambda: fixture_pin(2) is not None, 'Small Dock did not render fixtures')
            time.sleep(1)
            small_width = overflow_rect(dock_frame()).width
            assert overflow_button('Cuộn ứng dụng sang phải') is None, 'Small Dock unexpectedly requires overflow on reference monitor'
            large = dict(small, pinnedApps=overflow_original['pinnedApps'] + fixture_pins)
            import_overflow(large, 'large')
            wait_overflow(lambda: overflow_button('Cuộn ứng dụng sang phải') is not None, 'Overflow has no mouse navigation affordance')
            dock = overflow_rect(dock_frame())
            monitor = Gdk.Display.get_default().get_monitor_at_point(dock.x + dock.width // 2, dock.y + dock.height // 2)
            assert monitor.get_scale_factor() == 1, 'Native overflow pixel test expects reference scale 1'
            area = monitor.get_workarea()
            assert dock.width > small_width and dock.width <= area.width - 32
            assert area.x <= dock.x and dock.x + dock.width <= area.x + area.width and area.y <= dock.y and dock.y + dock.height <= area.y + area.height
            scroll_overflow(1)
            last = overflow_rect(fixture_pin(40)); arrow = overflow_rect(overflow_button('Cuộn ứng dụng sang phải'))
            assert dock.x < last.x and last.x + last.width <= arrow.x and dock.y <= last.y and last.y + last.height <= dock.y + dock.height, 'Final pin is outside its scroll viewport'
            for name in ('Âm thanh', 'Mở lịch'):
                widget = overflow_rect(overflow_button(name))
                assert widget.x >= last.x + last.width and widget.x + widget.width <= dock.x + dock.width, 'Overflow pin overlaps a system widget'
            focus_studio(); native_click_node(fixture_pin(40))
            wait_overflow(markers[-1].exists, 'Mouse scroll did not expose the exact final application')
            assert [i for i, marker in enumerate(markers, 1) if marker.exists()] == [40], 'Overflow click launched the wrong application'
            overflow_passed.append('40 extra pins grow native Dock up to work area; mouse arrows expose and launch exact final pin without covering widgets')
            scroll_overflow(-1)
            focus_studio('DeskMorph Taskbar')
            assert fixture_pin(1).get_component_iface().grab_focus()
            time.sleep(0.2)
            for index in range(2, 41):
                native_keys(chord=[0xff09])
                assert fixture_pin(index).get_state_set().contains(Atspi.StateType.FOCUSED), f'Tab skipped overflow fixture {index}'
            time.sleep(0.7)
            last = overflow_rect(fixture_pin(40)); arrow = overflow_rect(overflow_button('Cuộn ứng dụng sang phải'))
            assert last.x + last.width <= arrow.x and last.x > dock.x, 'Keyboard focus did not scroll final pin into view'
            markers[-1].unlink()
            native_keys(chord=[0xff0d])
            wait_overflow(markers[-1].exists, 'Enter did not launch the focused final application')
            overflow_passed.append('Tab traverses all 40 fixture pins and scrolls final focused application into view; Enter remains usable')
            clients = re.findall(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True))
            xid = next(xid for xid in clients if re.search(r'_NET_WM_PID.*= ' + str(app.get_process_id()) + r'\b', subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID', '_NET_WM_NAME'], text=True)) and 'DeskMorph Taskbar' in subprocess.check_output(['xprop', '-id', xid, '_NET_WM_NAME'], text=True))
            native = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(), int(xid, 16))
            picture = Gdk.pixbuf_get_from_window(native, 0, 0, dock.width, dock.height)
            assert picture; picture.savev(str(overflow_root / 'overflow-dock.png'), 'png', [], [])
            import_overflow(dict(large, position='bottom'), 'bottom')
            wait_overflow(lambda: overflow_rect(dock_frame()).y > area.y + area.height // 2, 'Overflow Dock did not move to bottom')
            bottom = overflow_rect(dock_frame())
            assert bottom.width == dock.width and bottom.x >= area.x and bottom.x + bottom.width <= area.x + area.width and bottom.y + bottom.height <= area.y + area.height
            scroll_overflow(-1); scroll_overflow(1)
            last = overflow_rect(fixture_pin(40)); arrow = overflow_rect(overflow_button('Cuộn ứng dụng sang phải'))
            assert bottom.x < last.x and last.x + last.width <= arrow.x and bottom.y <= last.y and last.y + last.height <= bottom.y + bottom.height
            markers[-1].unlink(); focus_studio(); native_click_node(fixture_pin(40))
            wait_overflow(markers[-1].exists, 'Bottom overflow click did not launch exact final pin')
            picture = Gdk.pixbuf_get_from_window(native, 0, 0, bottom.width, bottom.height)
            assert picture; picture.savev(str(overflow_root / 'overflow-bottom.png'), 'png', [], [])
            overflow_passed.append('bottom placement keeps the same work-area width limit and mouse access to final pin')
            import_overflow(small, 'shrink')
            wait_overflow(lambda: overflow_button('Cuộn ứng dụng sang phải') is None and overflow_rect(dock_frame()).width < dock.width, 'Removing excess pins did not shrink Dock and remove arrows')
            overflow_passed.append('removing excess pins shrinks Dock and hides both overflow controls')
        finally:
            import_overflow(overflow_original, 'restore')
            assert overflow_config() == overflow_original, 'Overflow test did not restore original configuration'
            for marker in markers: marker.unlink(missing_ok=True)
        report = {'passed': overflow_passed, 'smallWidth': small_width, 'overflowWidth': dock.width, 'workAreaWidth': area.width, 'pid': app.get_process_id(), 'preferencesRestored': True}
        (overflow_root / 'overflow-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(report, ensure_ascii=False))
    if args.launch_smoke:
        launch_path = Path(TEST_CONFIG) / 'com.ducthanhdev.deskmorph/config.json'
        launch_config = lambda: json.loads(launch_path.read_text())['config']
        launch_original = launch_config()
        launch_log = Path('/tmp/deskmorph-desktop-test/launch-events.jsonl')
        assert not launch_log.exists(), 'Do not overwrite a previous fixture log; inspect and remove it before rerunning'
        assert not any(pin.get('desktopId') in ('deskmorph-launch-multi.desktop', 'deskmorph-launch-single.desktop') for pin in launch_original['pinnedApps'])
        launch_passed = []
        def launch_events():
            return [json.loads(line) for line in launch_log.read_text().splitlines()] if launch_log.exists() else []
        def activations(mode): return [row for row in launch_events() if row['mode'] == mode and row['event'] == 'activate']
        def wait_launch(predicate, message):
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if predicate(): return
                time.sleep(0.1)
            raise AssertionError(message + '; events=' + repr(launch_events()))
        def launch_pinned(mode):
            return any(pin.get('desktopId') == f'deskmorph-launch-{mode}.desktop' for pin in launch_config()['pinnedApps'])
        def launch_node(mode, count):
            name = ('DeskMorph Launch ' + mode) if launch_pinned(mode) else ('DeskMorphLaunch' + mode.title())
            return next((n for n, _ in descendants(app) if n.get_role_name() == 'button' and n.get_name() == f'{name} • {count} cửa sổ'), None)
        def ready_launch_node(mode, count):
            wait_launch(lambda: launch_node(mode, count) is not None, 'Missing fixture Dock group')
            return launch_node(mode, count)
        def context_launch(mode, count):
            focus_studio()
            native_click_node(ready_launch_node(mode, count), button=3)
            wait_launch(lambda: any(n.get_name() == ('Bỏ ghim' if launch_pinned(mode) else 'Ghim') for n, _ in descendants(app)), 'Fixture context menu not ready')
        def assert_fixture_windows(mode, count):
            rows = activations(mode)
            assert len({row['xid'] for row in rows}) == count
            managed = re.findall(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True))
            for row in rows:
                assert row['xid'] in managed, 'Fixture window disappeared'
                properties = subprocess.check_output(['xprop', '-id', row['xid'], '_NET_WM_PID'], text=True)
                assert re.search(r'= ' + str(row['pid']) + r'\b', properties), 'Fixture XID changed owner'
        try:
            focus_studio(); click('Taskbar Studio')
            if not launch_original['enabled']: click('Bật Dock')
            if launch_original['autoHide']: click('Tự động ẩn Dock Chạm cạnh màn hình để hiện lại; Dock giữ hiện khi bạn thao tác popup.')
            if launch_original['position'] != 'top': click('Trên đỉnh màn hình')
            for mode in ('multi', 'single'):
                focus_studio(); click('Tìm ứng dụng')
                entry = next(n for n, _ in descendants(app) if n.get_name() == 'Tìm ứng dụng' and n.get_role_name() == 'entry')
                assert entry.get_component_iface().grab_focus(); time.sleep(0.2)
                native_keys(value='deskmorph launch ' + mode)
                wait_launch(lambda: any(n.get_name() == 'Ghim DeskMorph Launch ' + mode for n, _ in descendants(app)), 'Fixture entry missing from launcher')
                click('Ghim DeskMorph Launch ' + mode); native_keys(chord=[0xff1b])
                focus_studio(); native_click_node(ready_launch_node(mode, 0))
                wait_launch(lambda: len(activations(mode)) == 1, 'Ordinary click did not launch fixture')
                context_launch(mode, 1); click('Bỏ ghim')
                focus_studio(); native_click_node(ready_launch_node(mode, 1), button=2)
                wait_launch(lambda: len(activations(mode)) == 2, 'Unpinned middle click did not activate desktop entry')
                count = 2 if mode == 'multi' else 1
                context_launch(mode, count); click('Ghim')
                focus_studio(); native_click_node(ready_launch_node(mode, count), button=2)
                wait_launch(lambda: len(activations(mode)) == 3, 'Pinned middle click did not activate desktop entry')
                count = 3 if mode == 'multi' else 1
                ready_launch_node(mode, count)
                assert_fixture_windows(mode, count)
                assert len({row['pid'] for row in activations(mode)}) == count
                launch_passed.append(mode + ': ordinary launch plus unpinned/pinned middle click preserve application instance semantics and Dock count')
            for name, arguments in (('Soạn tài liệu fixture', ['compose', 'two words']), ('Phiên riêng fixture', ['private'])):
                context_launch('multi', 3)
                wait_launch(lambda: any(n.get_name() == name for n, _ in descendants(app)), 'Declared Desktop Action missing')
                previous = len([row for row in launch_events() if row['event'] == 'action'])
                click(name)
                wait_launch(lambda: len([row for row in launch_events() if row['event'] == 'action']) == previous + 1, 'Desktop Action did not run')
                assert [row for row in launch_events() if row['event'] == 'action'][-1]['arguments'] == arguments
                assert len(activations('multi')) == 3, 'Desktop Action fell back to ordinary launch'
            context_launch('single', 1)
            assert not any(n.get_name() in ('Soạn tài liệu fixture', 'Phiên riêng fixture') for n, _ in descendants(app)), 'Menu retained actions from previous application'
            native_keys(chord=[0xff1b])
            launch_passed.append('declared Desktop Actions run exact arguments; application without actions has no stale action buttons')
        finally:
            events = launch_events()
            for pid in {row['pid'] for row in events if row['event'] == 'activate'}:
                try: handle = os.pidfd_open(pid)
                except ProcessLookupError: continue
                try:
                    assert b'DESKMORPH_CONFIG_HOME=' + TEST_CONFIG.encode() in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
                    assert str(launch_fixture_script).encode() in Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0'), 'Refuse to terminate an unowned process'
                    signal.pidfd_send_signal(handle, signal.SIGTERM)
                finally: os.close(handle)
            focus_studio()
            for mode in ('multi', 'single'):
                if launch_pinned(mode): context_launch(mode, 0); click('Bỏ ghim')
            assert launch_config()['pinnedApps'] == launch_original['pinnedApps'], 'Launch test changed original pins/order'
            click('Taskbar Studio')
            if launch_config()['position'] != launch_original['position']: click('Trên đỉnh màn hình' if launch_original['position'] == 'top' else 'Dưới đáy (Đề xuất)')
            if launch_config()['autoHide'] != launch_original['autoHide']: click('Tự động ẩn Dock Chạm cạnh màn hình để hiện lại; Dock giữ hiện khi bạn thao tác popup.')
            if launch_config()['enabled'] != launch_original['enabled']: click('Bật Dock')
            Path('/tmp/deskmorph-desktop-test/launch-last-events.json').write_text(json.dumps(events, indent=2))
            launch_log.unlink(missing_ok=True)
        report = {'passed': launch_passed, 'events': events, 'pid': app.get_process_id(), 'preferencesRestored': True}
        Path('/tmp/deskmorph-desktop-test/launch-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(report, ensure_ascii=False))
    if args.tooltip_smoke:
        gi.require_version('Gdk', '3.0')
        gi.require_version('GdkX11', '3.0')
        from gi.repository import Gdk, GdkX11
        tooltip_path = Path(TEST_CONFIG) / 'com.ducthanhdev.deskmorph/config.json'
        tooltip_config = lambda: json.loads(tooltip_path.read_text())['config']
        tooltip_original = tooltip_config()
        marker_path = Path('/tmp/deskmorph-desktop-test/tooltip-launched')
        assert not marker_path.exists(), 'Do not overwrite existing tooltip fixture marker'
        assert not any(pin.get('desktopId') == 'deskmorph-tooltip-fixture.desktop' for pin in tooltip_original['pinnedApps']), 'Tooltip fixture must start unpinned'
        passed = []
        timings = []
        tooltip_xid_cache = None
        widget_fields = [('showApps', 'Ứng dụng trên Dock'), ('showStats', 'CPU và RAM'), ('showAudio', 'Âm thanh'), ('showClock', 'Đồng hồ'), ('showSystem', 'Nút tiện ích hệ thống'), ('showShuffle', 'Nút đổi hình nền'), ('showBattery', 'Hiện pin trên Dock'), ('showNetwork', 'Hiện mạng trên Dock')]
        def wait_tooltip(predicate, message):
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                if predicate(): return
                time.sleep(0.05)
            raise AssertionError(message)
        def owned_native_windows():
            result = {}
            for xid in re.findall(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True)):
                props = subprocess.run(['xprop', '-id', xid, '_NET_WM_PID', '_NET_WM_NAME'], capture_output=True, text=True).stdout
                if re.search(r'_NET_WM_PID.*= ' + str(app.get_process_id()) + r'\b', props):
                    title = re.search(r'_NET_WM_NAME\([^)]*\) = "(.*)"', props)
                    if title: result[title.group(1)] = xid
            return result
        def tooltip_mapped():
            # Cache the known owned XID after first map; xwininfo queries the server.
            global tooltip_xid_cache
            if tooltip_xid_cache is None: tooltip_xid_cache = owned_native_windows().get('DeskMorph Tooltip')
            if tooltip_xid_cache is None: return False
            result = subprocess.run(['xwininfo', '-id', tooltip_xid_cache], capture_output=True, text=True)
            return result.returncode == 0 and 'Map State: IsViewable' in result.stdout
        def tooltip_text():
            frame = next((n for n, _ in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Tooltip'), None)
            parts = []
            if frame:
                for node, _ in descendants(frame):
                    parts.append(node.get_name() or '')
                    iface = node.get_text_iface()
                    if iface: parts.append(Atspi.Text.get_text(iface, 0, -1))
            return '\n'.join(parts)
        def tooltip_node(name, prefix=False):
            dock_frame = next(n for n, _ in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Taskbar')
            return next(n for n, _ in descendants(dock_frame) if (n.get_name().startswith(name) if prefix else n.get_name() == name) and n.get_role_name() in ('button', 'image'))
        def move_tooltip_pointer(node):
            native_keys()
            rect = node.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
            assert rect.width > 0 and rect.height > 0
            x11 = ctypes.CDLL('libX11.so.6'); xtst = ctypes.CDLL('libXtst.so.6')
            x11.XOpenDisplay.restype = ctypes.c_void_p
            x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]; x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
            xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
            display = x11.XOpenDisplay(None); assert display
            try:
                require_unlocked_desktop()
                started = time.monotonic()
                assert xtst.XTestFakeMotionEvent(display, -1, rect.x + rect.width // 2, rect.y + rect.height // 2, 0)
                x11.XSync(display, 0)
                assert_pointer_over_test_app()
                return started
            finally: x11.XCloseDisplay(display)
        def clear_tooltip():
            focus_studio()
            heading = next(n for n, _ in descendants(app) if n.get_role_name() == 'heading' and n.get_name() == 'DeskMorph')
            move_tooltip_pointer(heading)
            wait_tooltip(lambda: not tooltip_mapped(), 'Tooltip did not hide after leaving Dock')
        def assert_empty_input_region(xid):
            x11 = ctypes.CDLL('libX11.so.6'); shape = ctypes.CDLL('libXext.so.6')
            x11.XOpenDisplay.restype = ctypes.c_void_p; x11.XCloseDisplay.argtypes = [ctypes.c_void_p]; x11.XFree.argtypes = [ctypes.c_void_p]
            shape.XShapeGetRectangles.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
            shape.XShapeGetRectangles.restype = ctypes.c_void_p
            display = x11.XOpenDisplay(None); assert display
            try:
                count, ordering = ctypes.c_int(), ctypes.c_int()
                rectangles = shape.XShapeGetRectangles(display, int(xid, 16), 2, ctypes.byref(count), ctypes.byref(ordering))
                try: assert count.value == 0, 'Tooltip native input region must be empty'
                finally:
                    if rectangles: x11.XFree(rectangles)
            finally: x11.XCloseDisplay(display)
        def hover_tooltip(node, expected, position, pixels=False):
            clear_tooltip()
            active = subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True).strip()
            started = move_tooltip_pointer(node)
            time.sleep(0.12)
            early = time.monotonic() - started
            assert early < 0.45, 'Timing observation was delayed; cannot prove tooltip delay'
            assert not tooltip_mapped(), 'Tooltip appeared before the hover delay'
            wait_tooltip(tooltip_mapped, 'Unified native tooltip did not appear')
            latency = time.monotonic() - started
            assert latency >= 0.45, 'Tooltip appeared before its configured delay'
            try: wait_tooltip(lambda: expected in tooltip_text(), 'Tooltip did not show the expected accessible text: ' + expected)
            except AssertionError:
                native = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(), int(tooltip_xid_cache, 16))
                bounds = native.get_frame_extents()
                picture = Gdk.pixbuf_get_from_window(native, 0, 0, bounds.width, bounds.height)
                if picture: picture.savev('/tmp/deskmorph-desktop-test/tooltip-failure.png', 'png', [], [])
                print('Tooltip text diagnostic:', repr(tooltip_text()), [(n.get_role_name(), n.get_name()) for n, _ in descendants(app) if n.get_role_name() == 'frame'], flush=True)
                raise
            assert subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True).strip() == active, 'Tooltip stole native focus'
            native = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(), int(tooltip_xid_cache, 16))
            server_geometry = subprocess.check_output(['xwininfo', '-id', tooltip_xid_cache], text=True)
            rect = Gdk.Rectangle()
            for field, label in (('x', 'Absolute upper-left X'), ('y', 'Absolute upper-left Y'), ('width', 'Width'), ('height', 'Height')):
                setattr(rect, field, int(re.search(re.escape(label) + r':\s*(-?\d+)', server_geometry).group(1)))
            dock = next(n for n, _ in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Taskbar').get_component_iface().get_extents(Atspi.CoordType.SCREEN)
            monitor = Gdk.Display.get_default().get_monitor_at_point(dock.x + dock.width // 2, dock.y + dock.height // 2)
            assert monitor.get_scale_factor() == 1, 'This reference pixel test requires X11 scale 1; mixed DPI remains a separate gate'
            area = monitor.get_workarea()
            assert area.x <= rect.x and rect.x + rect.width <= area.x + area.width and area.y <= rect.y and rect.y + rect.height <= area.y + area.height, 'Tooltip escaped monitor work area'
            assert rect.height == 44 and rect.width == 250, f'Unexpected native tooltip size: {rect.width}x{rect.height}'
            assert (rect.y >= dock.y + dock.height) if position == 'top' else (rect.y + rect.height <= dock.y), 'Tooltip overlaps native Dock'
            assert_empty_input_region(tooltip_xid_cache)
            if pixels:
                picture = Gdk.pixbuf_get_from_window(native, 0, 0, rect.width, rect.height)
                assert picture, 'Could not capture owned tooltip pixels'
                picture.savev(f'/tmp/deskmorph-desktop-test/tooltip-{position}.png', 'png', [], [])
                data, stride, channels = picture.get_pixels(), picture.get_rowstride(), picture.get_n_channels()
                text_pixels = [(x, y) for y in range(rect.height) for x in range(rect.width) if all(data[y * stride + x * channels + offset] >= 150 for offset in (0, 1, 2))]
                assert len(text_pixels) > 20, 'Long tooltip text was not rendered'
                xs, ys = zip(*text_pixels)
                assert min(xs) >= 10 and max(xs) < rect.width - 10 and min(ys) >= 8 and max(ys) < rect.height - 8 and max(ys) - min(ys) < 20, 'Long tooltip text escaped padded single-line bounds'
            timings.append({'text': expected[:50], 'position': position, 'seconds': round(latency, 3), 'rect': [rect.x, rect.y, rect.width, rect.height]})
        try:
            focus_studio(); click('Taskbar Studio')
            if not tooltip_original['enabled']: click('Bật Dock')
            if tooltip_original['autoHide']: click('Tự động ẩn Dock Chạm cạnh màn hình để hiện lại; Dock giữ hiện khi bạn thao tác popup.')
            for field, label in widget_fields:
                if not tooltip_config()[field]: click(label)
            click('Tìm ứng dụng')
            entry = next(n for n, _ in descendants(app) if n.get_name() == 'Tìm ứng dụng' and n.get_role_name() == 'entry')
            assert entry.get_component_iface().grab_focus(); time.sleep(0.2); native_keys(value='deskmorph tooltip')
            wait_tooltip(lambda: any(n.get_name() == 'Ghim ' + tooltip_fixture_name for n, _ in descendants(app)), 'Long tooltip fixture missing from launcher')
            click('Ghim ' + tooltip_fixture_name); native_keys(chord=[0xff1b])
            for position in ('top', 'bottom'):
                focus_studio(); click('Taskbar Studio')
                if tooltip_config()['position'] != position: click('Trên đỉnh màn hình' if position == 'top' else 'Dưới đáy (Đề xuất)')
                hover_tooltip(tooltip_node('Tìm ứng dụng'), 'Tìm ứng dụng', position)
                hover_tooltip(tooltip_node('Mở lịch'), 'Mở lịch', position)
                hover_tooltip(tooltip_node(tooltip_fixture_name + ' • 0 cửa sổ'), tooltip_fixture_name, position, pixels=True)
                for name in ('Âm thanh', 'Tiện ích hệ thống'):
                    hover_tooltip(tooltip_node(name), name, position)
                hover_tooltip(tooltip_node('CPU:', prefix=True), 'CPU:', position)
                hover_tooltip(tooltip_node('RAM:', prefix=True), 'RAM:', position)
                hover_tooltip(tooltip_node('Đổi hình nền ngẫu nhiên'), 'Đổi hình nền ngẫu nhiên', position)
                for node, _ in descendants(app):
                    if node.get_role_name() == 'button' and (node.get_name().startswith('Pin ') or node.get_name() in ('Mạng', 'Đã ngắt mạng', 'Không đọc được UPower', 'Không đọc được NetworkManager')):
                        hover_tooltip(node, node.get_name(), position)
                passed.append(position + ': launcher/pin/clock/widgets share delay, native focus, work-area bounds and empty input region; long text pixels fit')
                clear_tooltip()
                for action, title, hover in (('Tìm ứng dụng', 'DeskMorph Context Menu', 'Âm thanh'), ('Mở lịch', 'DeskMorph Calendar', 'Tiện ích hệ thống'), ('Âm thanh', 'DeskMorph Context Menu', 'Mở lịch')):
                    native_click_node(tooltip_node(action))
                    wait_tooltip(lambda: title in owned_native_windows(), 'Interactive popup did not open')
                    move_tooltip_pointer(tooltip_node(hover)); time.sleep(0.7)
                    assert not tooltip_mapped(), 'Tooltip appeared over an interactive popup'
                    native_keys(chord=[0xff1b])
                    wait_tooltip(lambda: title not in owned_native_windows(), 'Escape did not close popup')
                passed.append(position + ': launcher/calendar/audio suppress pending and new tooltips while open')
            assert not marker_path.exists(), 'Tooltip interactions accidentally launched the pinned fixture'
        finally:
            clear_tooltip()
            if any(pin.get('desktopId') == 'deskmorph-tooltip-fixture.desktop' for pin in tooltip_config()['pinnedApps']):
                native_click_node(tooltip_node(tooltip_fixture_name + ' • 0 cửa sổ'), button=3); click('Bỏ ghim')
            assert tooltip_config()['pinnedApps'] == tooltip_original['pinnedApps'], 'Tooltip test did not restore original pins'
            click('Taskbar Studio')
            for field, label in widget_fields:
                if tooltip_config()[field] != tooltip_original[field]: click(label)
            if tooltip_config()['position'] != tooltip_original['position']: click('Trên đỉnh màn hình' if tooltip_original['position'] == 'top' else 'Dưới đáy (Đề xuất)')
            if tooltip_config()['autoHide'] != tooltip_original['autoHide']: click('Tự động ẩn Dock Chạm cạnh màn hình để hiện lại; Dock giữ hiện khi bạn thao tác popup.')
            if tooltip_config()['enabled'] != tooltip_original['enabled']: click('Bật Dock')
            marker_path.unlink(missing_ok=True)
        report = {'passed': passed, 'timings': timings, 'pid': app.get_process_id(), 'preferencesRestored': True}
        Path('/tmp/deskmorph-desktop-test/tooltip-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(report, ensure_ascii=False))
    if args.reorder_smoke:
        reorder_path = Path(TEST_CONFIG) / 'com.ducthanhdev.deskmorph/config.json'
        reorder_snapshot = lambda: json.loads(reorder_path.read_text())
        reorder_original = reorder_snapshot()['config']
        original_pins = reorder_original['pinnedApps']
        fixture_ids = [f'deskmorph-reorder-{letter.lower()}.desktop' for letter in 'ABC']
        markers = [Path(f'/tmp/deskmorph-desktop-test/reorder-launched-{letter}') for letter in 'ABC']
        assert not any(pin.get('desktopId') in fixture_ids for pin in original_pins), 'Reorder fixtures must start unpinned'
        assert not any(marker.exists() for marker in markers), 'Do not overwrite existing launch markers'
        reorder_passed = []
        def wait_reorder(predicate, message):
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if predicate(): return
                time.sleep(0.1)
            focused = [(n.get_role_name(), n.get_name()) for n, _ in descendants(app) if n.get_state_set().contains(Atspi.StateType.FOCUSED)]
            raise AssertionError(message + f'; order={fixture_order()}; focus={focused}')
        def order(): return [pin['id'] for pin in reorder_snapshot()['config']['pinnedApps']]
        def fixture_order(): return [pin['desktopId'] for pin in reorder_snapshot()['config']['pinnedApps'] if pin.get('desktopId') in fixture_ids]
        def reorder_node(letter):
            return next(n for n, _ in descendants(app) if n.get_role_name() == 'button' and n.get_name() == f'DeskMorph Reorder {letter} • 0 cửa sổ')
        def focus_pin(letter):
            focus_studio('DeskMorph Taskbar')
            assert reorder_node(letter).get_component_iface().grab_focus()
            time.sleep(0.2)
        def native_drag(source_letter, target_letter, cancel=False):
            before_drag = reorder_snapshot()
            focus_studio(); focus_pin(source_letter); native_keys()
            start = reorder_node(source_letter).get_component_iface().get_extents(Atspi.CoordType.SCREEN)
            end = reorder_node(target_letter).get_component_iface().get_extents(Atspi.CoordType.SCREEN) if target_letter else None
            dock = next(n for n, _ in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Taskbar')
            dock_rect = dock.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
            for rect in (start, end) if end else (start,):
                assert rect.width > 0 and rect.height > 0
                assert dock_rect.x <= rect.x and rect.x + rect.width <= dock_rect.x + dock_rect.width
                assert dock_rect.y <= rect.y and rect.y + rect.height <= dock_rect.y + dock_rect.height
            x11 = ctypes.CDLL('libX11.so.6'); xtst = ctypes.CDLL('libXtst.so.6')
            x11.XOpenDisplay.restype = ctypes.c_void_p
            x11.XFlush.argtypes = [ctypes.c_void_p]; x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
            xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
            xtst.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
            display = x11.XOpenDisplay(None); assert display
            pressed = False
            try:
                sx, sy = start.x + start.width // 2, start.y + start.height // 2
                if end: ex, ey = end.x + end.width // 2, end.y + end.height // 2
                else:
                    studio = next(n for n, _ in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Studio').get_component_iface().get_extents(Atspi.CoordType.SCREEN)
                    heading = next(n for n, _ in descendants(app) if n.get_role_name() == 'heading' and n.get_name() == 'DeskMorph').get_component_iface().get_extents(Atspi.CoordType.SCREEN)
                    ex, ey = studio.x + studio.width - 30, heading.y + heading.height // 2
                    assert not (dock_rect.x <= ex < dock_rect.x + dock_rect.width and dock_rect.y <= ey < dock_rect.y + dock_rect.height), 'Outside drop point must be outside Dock'
                require_unlocked_desktop()
                # Verify both endpoints before pressing; AT-SPI bounds alone do not prove an uncovered target.
                for px, py in ((ex, ey), (sx, sy)):
                    assert xtst.XTestFakeMotionEvent(display, -1, px, py, 0)
                    x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]; x11.XSync(display, 0)
                    assert_pointer_over_test_app()
                time.sleep(0.15)
                assert xtst.XTestFakeButtonEvent(display, 1, 1, 0); pressed = True; x11.XFlush(display); time.sleep(0.15)
                for step in range(1, 13):
                    require_unlocked_desktop()
                    assert xtst.XTestFakeMotionEvent(display, -1, sx + (ex - sx) * step // 12, sy + (ey - sy) * step // 12, 0)
                    x11.XFlush(display); time.sleep(0.05)
                time.sleep(0.2)
                assert reorder_snapshot() == before_drag, 'Dragging before drop must not persist config'
                if cancel: native_keys(chord=[0xff1b])
            finally:
                if pressed: xtst.XTestFakeButtonEvent(display, 1, 0, 0); x11.XFlush(display)
                x11.XCloseDisplay(display)
            time.sleep(0.8)
        try:
            focus_studio(); click('Taskbar Studio')
            if not reorder_original['enabled']: click('Bật Dock')
            if reorder_original['autoHide']: click('Tự động ẩn Dock Chạm cạnh màn hình để hiện lại; Dock giữ hiện khi bạn thao tác popup.')
            if reorder_snapshot()['config']['position'] != 'top': click('Trên đỉnh màn hình')
            native_keys(chord=[0xff1b])  # Dismiss the native select menu before opening a WebView popup.
            wait_reorder(lambda: reorder_snapshot()['config']['position'] == 'top', 'Dock position did not persist')
            def reorder_launcher_focused():
                active = re.search(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)).group(0)
                props = subprocess.check_output(['xprop', '-id', active, '_NET_WM_PID', '_NET_WM_NAME'], text=True)
                return 'DeskMorph Context Menu' in props and re.search(r'_NET_WM_PID.*= ' + str(app.get_process_id()) + r'\b', props)
            for letter in 'ABC':
                focus_studio()
                native_click_node(next(n for n, _ in descendants(app) if n.get_name() == 'Tìm ứng dụng' and n.get_role_name() == 'button'))
                wait_reorder(reorder_launcher_focused, 'Launcher did not receive native focus; no text will be sent')
                entry = next(n for n, _ in descendants(app) if n.get_name() == 'Tìm ứng dụng' and n.get_role_name() == 'entry')
                assert entry.get_component_iface().grab_focus(); time.sleep(0.2)
                native_keys(value='deskmorph reorder')
                wait_reorder(lambda: any(n.get_name() == f'Ghim DeskMorph Reorder {letter}' for n, _ in descendants(app)), 'Reorder fixture missing from launcher')
                click(f'Ghim DeskMorph Reorder {letter}')
                native_keys(chord=[0xff1b])
            assert fixture_order() == fixture_ids
            revision = reorder_snapshot()['revision']
            native_drag('A', 'C')
            wait_reorder(lambda: fixture_order() == [fixture_ids[1], fixture_ids[2], fixture_ids[0]], 'Native drop did not reorder pins')
            assert reorder_snapshot()['revision'] == revision + 1, 'Drag must persist exactly once at drop'
            assert not any(marker.exists() for marker in markers), 'Drag accidentally launched a fixture'
            reorder_passed.append('native drag A to C updates order and persists exactly once without launching app')
            before = reorder_snapshot()
            native_drag('A', 'B', cancel=True)
            assert reorder_snapshot() == before, 'Cancelled drag changed config or revision'
            assert not any(marker.exists() for marker in markers), 'Cancelled drag accidentally launched a fixture'
            reorder_passed.append('Escape cancels native drag without changing order/revision or launching app')
            before = reorder_snapshot()
            native_drag('A', None)
            assert reorder_snapshot() == before and not any(marker.exists() for marker in markers), 'Dropping outside Dock must cancel without writing or launching'
            reorder_passed.append('dropping outside Dock cancels without changing config or launching app')
            focus_pin('A'); revision = reorder_snapshot()['revision']
            native_keys(chord=[0xffe3, 0xffe1, 0xff51])
            wait_reorder(lambda: fixture_order() == [fixture_ids[1], fixture_ids[0], fixture_ids[2]], 'Keyboard reorder left failed')
            assert reorder_snapshot()['revision'] == revision + 1
            wait_reorder(lambda: reorder_node('A').get_component_iface().get_extents(Atspi.CoordType.SCREEN).x < reorder_node('C').get_component_iface().get_extents(Atspi.CoordType.SCREEN).x, 'Dock has not rendered keyboard move yet')
            node = reorder_node('A')
            assert node.get_state_set().contains(Atspi.StateType.FOCUSED), 'Keyboard reorder did not retain moved pin focus'
            time.sleep(0.7)
            active_xid = re.search(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)).group(0)
            active_title = subprocess.check_output(['xprop', '-id', active_xid, '_NET_WM_NAME'], text=True).strip()
            assert 'DeskMorph Taskbar' in active_title, 'Keyboard focus left Dock after tooltip delay: ' + active_title
            native_keys(chord=[0xffe3, 0xffe1, 0xff53])
            wait_reorder(lambda: fixture_order() == [fixture_ids[1], fixture_ids[2], fixture_ids[0]], 'Keyboard reorder right failed')
            before = reorder_snapshot()
            native_keys(chord=[0xffe3, 0xffe1, 0xff53])
            assert reorder_snapshot() == before, 'Boundary keyboard reorder should not write unchanged config'
            reorder_passed.append('Ctrl+Shift+Left/Right moves pins, retains focus and does not write at boundary')
            focus_studio()
            native_click_node(reorder_node('A'), button=3); click('Sang trái')
            wait_reorder(lambda: fixture_order() == [fixture_ids[1], fixture_ids[0], fixture_ids[2]], 'Context-menu reorder failed')
            reorder_passed.append('context-menu move updates same persistent pin order')
            saved_order = order()
            click('Hệ thống'); old_pid = app.get_process_id(); click('Thoát DeskMorph')
            def exited():
                try: return Path(f'/proc/{old_pid}/stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z'
                except FileNotFoundError: return True
            wait_reorder(exited, 'Reorder app did not exit normally')
            try: os.waitpid(old_pid, os.WNOHANG)
            except ChildProcessError: pass
            app = start_isolated_app()
            assert order() == saved_order, 'Restart lost reordered pins'
            rects = [reorder_node(letter).get_component_iface().get_extents(Atspi.CoordType.SCREEN).x for letter in 'BAC']
            assert rects == sorted(rects) and len(set(rects)) == 3, 'Restart Dock positions do not match saved order'
            assert not any(marker.exists() for marker in markers), 'Reordering or restart launched a fixture'
            reorder_passed.append('normal restart preserves pin order and actual native icon positions')
            focus_studio(); native_click_node(reorder_node('A'))
            wait_reorder(markers[0].exists, 'Ordinary click stopped launching a pinned app after pointer capture changes')
            markers[0].unlink()
            focus_studio(); native_click_node(reorder_node('B'), button=2)
            wait_reorder(markers[1].exists, 'Middle click stopped launching a pinned desktop entry')
            markers[1].unlink()
            reorder_passed.append('ordinary and middle click still launch their exact fixture desktop entries')
        finally:
            focus_studio()
            for letter, desktop_id in zip('ABC', fixture_ids):
                if any(pin.get('desktopId') == desktop_id for pin in reorder_snapshot()['config']['pinnedApps']):
                    native_click_node(reorder_node(letter), button=3); click('Bỏ ghim')
            assert reorder_snapshot()['config']['pinnedApps'] == original_pins, 'Reorder test did not restore original pins/order'
            click('Taskbar Studio')
            if reorder_snapshot()['config']['position'] != reorder_original['position']: click('Trên đỉnh màn hình' if reorder_original['position'] == 'top' else 'Dưới đáy (Đề xuất)')
            if reorder_snapshot()['config']['autoHide'] != reorder_original['autoHide']: click('Tự động ẩn Dock Chạm cạnh màn hình để hiện lại; Dock giữ hiện khi bạn thao tác popup.')
            if reorder_snapshot()['config']['enabled'] != reorder_original['enabled']: click('Bật Dock')
            for marker in markers: marker.unlink(missing_ok=True)
        report = {'passed': reorder_passed, 'pid': app.get_process_id(), 'pinsRestored': True}
        Path('/tmp/deskmorph-desktop-test/reorder-result.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
    if args.window_list_smoke:
        import select
        fixture = None
        window_passed = []
        config_path = Path(TEST_CONFIG) / 'com.ducthanhdev.deskmorph/config.json'
        window_config = lambda: json.loads(config_path.read_text())['config']
        original_pins = window_config()['pinnedApps']
        window_original_enabled = window_config()['enabled']
        window_original_auto = window_config()['autoHide']
        assert not any(pin.get('desktopId') == 'deskmorph-window-fixture.desktop' for pin in original_pins), 'Window fixture must start unpinned'
        def wait_windows(predicate, message):
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if predicate(): return
                time.sleep(0.1)
            focused = [(n.get_role_name(), n.get_name()) for n, _ in descendants(app) if n.get_state_set().contains(Atspi.StateType.FOCUSED)]
            rows = [n.get_name() for n, _ in descendants(app) if n.get_role_name() == 'button' and 'Window' in n.get_name()]
            raise AssertionError(message + f'; focus={focused}; rows={rows}; native=' + subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True))
        def fixture_response():
            assert select.select([fixture.stdout], [], [], 5)[0], 'Fixture did not acknowledge command'
            line = fixture.stdout.readline()
            assert line, 'Fixture exited without replying'
            return json.loads(line)
        def fixture_command(action, index, **kwargs):
            fixture.stdin.write(json.dumps(dict(action=action, index=index, **kwargs)) + '\n'); fixture.stdin.flush()
            return fixture_response()
        def managed_fixture():
            return set(re.findall(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True)))
        def row_button(title):
            return next((node for node, _ in descendants(app) if node.get_role_name() == 'button' and node.get_name().startswith(title)), None)
        def row_focused(title):
            node = row_button(title)
            return bool(node and node.get_state_set().contains(Atspi.StateType.FOCUSED))
        def popup_xid():
            for xid in managed_fixture():
                props = subprocess.run(['xprop', '-id', xid, '_NET_WM_PID', '_NET_WM_NAME'], capture_output=True, text=True).stdout
                if 'DeskMorph Context Menu' in props and re.search(r'_NET_WM_PID.*= ' + str(app.get_process_id()) + r'\b', props): return xid
            return None
        def popup_visible(): return popup_xid() is not None
        def group_button(count):
            pinned = any(pin.get('desktopId') == 'deskmorph-window-fixture.desktop' for pin in window_config()['pinnedApps'])
            name = 'DeskMorph Window Fixture' if pinned else 'DeskMorphWindowFixture'
            return f'{name} • {count} cửa sổ'
        def group_node(count):
            dock = next(n for n, _ in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Taskbar')
            return next((n for n, _ in descendants(dock) if n.get_role_name() == 'button' and n.get_name() == group_button(count)), None)
        def open_windows(count):
            wait_windows(lambda: group_node(count) is not None, 'Dock did not reconcile fixture group count')
            node = group_node(count)
            native_click_node(node)
            wait_windows(lambda: popup_visible() and row_button('DeskMorph Window Test 1') is not None, 'Window list did not open')
            wait_windows(lambda: popup_xid() is not None and popup_xid() in subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True), 'Opened window list did not receive native focus')
            wait_windows(lambda: any(n.get_role_name() == 'button' and n.get_name().startswith('DeskMorph Window') and n.get_state_set().contains(Atspi.StateType.FOCUSED) for n, _ in descendants(app)), 'Opened list did not focus a window row')
        def fixture_app():
            desktop = Atspi.get_desktop(0)
            return next((desktop.get_child_at_index(i) for i in range(desktop.get_child_count()) if desktop.get_child_at_index(i).get_process_id() == fixture.pid), None)
        try:
            focus_studio(); click('Taskbar Studio')
            if not window_original_enabled: click('Bật Dock')
            if window_original_auto: click('Tự động ẩn Dock Chạm cạnh màn hình để hiện lại; Dock giữ hiện khi bạn thao tác popup.')
            fixture_env = dict(os.environ, DESKMORPH_CONFIG_HOME=TEST_CONFIG)
            fixture = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).resolve()), '--window-fixture'], env=fixture_env,
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            fixture_state = fixture_response()
            assert fixture.poll() is None, 'Window fixture exited before environment verification'
            assert b'DESKMORPH_CONFIG_HOME=' + TEST_CONFIG.encode() in Path(f'/proc/{fixture.pid}/environ').read_bytes().split(b'\0'), 'Ready window fixture did not retain its isolated profile'
            owned_input_pids.add(fixture.pid)
            assert len(fixture_state) == 3
            wait_windows(lambda: all(v['xid'] in managed_fixture() for v in fixture_state.values()), 'Fixture windows were not managed')
            focus_studio('DeskMorph Window Test 3', fixture.pid)
            time.sleep(1.8)  # Dock snapshot includes the active fixture before opening the list.
            open_windows(3)
            wait_windows(lambda: row_focused('DeskMorph Window Test 3'), 'Initial keyboard focus did not select the active window')
            for keysym, title in ((0xff50, 'DeskMorph Window Test 1'), (0xff57, 'DeskMorph Window Test 3'), (0xff52, 'DeskMorph Window Test 2'), (0xff54, 'DeskMorph Window Test 3')):
                native_keys(chord=[keysym])
                wait_windows(lambda: row_focused(title), f'Window list navigation failed for {hex(keysym)}')
            native_keys(chord=[0xff52]); native_keys(chord=[0xff0d])
            wait_windows(lambda: fixture_state['2']['xid'] in subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True), 'Enter did not activate the exact selected XID')
            wait_windows(lambda: not popup_visible(), 'Activation did not hide window list')
            window_passed.append('unpinned three-window group; active initial focus, Home/End/arrows and Enter activate exact XID')
            open_windows(3)
            fixture_state = fixture_command('title', 2, title='DeskMorph Window Renamed 2')
            wait_windows(lambda: row_button('DeskMorph Window Renamed 2') is not None and row_button('DeskMorph Window Test 2') is None, 'Renamed window did not update in open popup')
            native_keys(chord=[0xff50]); native_keys(chord=[0xff54])
            wait_windows(lambda: row_focused('DeskMorph Window Renamed 2'), 'Renamed row did not preserve keyboard identity')
            fixture_state = fixture_command('close', 2)
            wait_windows(lambda: row_button('DeskMorph Window Renamed 2') is None and row_focused('DeskMorph Window Test 3'), 'Removing selected middle row did not focus the next surviving row')
            fixture_state = fixture_command('add', 4)
            wait_windows(lambda: row_button('DeskMorph Window Test 4') is not None, 'New window did not appear in already open list')
            native_keys(chord=[0xff57])
            wait_windows(lambda: row_focused('DeskMorph Window Test 4'), 'End did not reach newly added row')
            native_keys(chord=[0xff1b]); wait_windows(lambda: not popup_visible(), 'Escape did not dismiss window list')
            window_passed.append('open list refreshes title, adds window and removes external close; nearest-row focus survives')
            # Pin via the real context menu, then repeat native group operations.
            focus_studio()
            native_click_node(group_node(3), button=3)
            click('Ghim')
            wait_windows(lambda: any(pin.get('desktopId') == 'deskmorph-window-fixture.desktop' for pin in window_config()['pinnedApps']), 'Pinning fixture group failed')
            open_windows(3)
            click('Đóng DeskMorph Window Test 1')
            wait_windows(lambda: fixture_app() is not None and any(n.get_name() == 'DeskMorph Window Confirm' for n, _ in descendants(fixture_app())), 'App close confirmation did not open')
            assert fixture_state['1']['xid'] in managed_fixture(), 'Close request removed window before app confirmed'
            candidate = fixture_app()
            cancel = next(n for n, _ in descendants(candidate) if n.get_name() in ('Cancel', 'Hủy') and n.get_action_iface())
            require_unlocked_desktop(); assert cancel.get_action_iface().do_action(0)
            time.sleep(0.4)
            assert fixture_state['1']['xid'] in managed_fixture(), 'Cancel did not preserve window'
            focus_studio(); open_windows(3)
            assert row_button('DeskMorph Window Test 1'), 'Cancelled-close window disappeared from list'
            window_passed.append('pinned group remains present through app-owned close confirmation and cancel')
            fixture_command('close', 3); fixture_command('close', 4)
            wait_windows(lambda: row_button('DeskMorph Window Test 3') is None and row_button('DeskMorph Window Test 4') is None, 'List did not reconcile one remaining window')
            native_keys(chord=[0xff1b]); wait_windows(lambda: not popup_visible(), 'Escape did not dismiss one-window list')
            focus_studio()
            node = group_node(1)
            native_click_node(node)
            wait_windows(lambda: fixture_state['1']['xid'] in subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True), 'Single-window pin did not activate its exact XID')
            assert not popup_visible(), 'Single-window activation unexpectedly opened a list'
            window_passed.append('one-window pin activates exact XID directly')
            fixture_command('add', 5)
            wait_windows(lambda: any(n.get_name() == group_button(2) for n, _ in descendants(app)), 'Second window did not update pinned group')
            focus_studio()
            node = group_node(2)
            native_click_node(node, button=3)
            wait_windows(lambda: row_button('DeskMorph Window Test 5') is not None, 'Context menu did not list fixture windows')
            context_state = fixture_command('title', 5, title='DeskMorph Context Renamed 5')
            wait_windows(lambda: row_button('DeskMorph Context Renamed 5') is not None and row_button('DeskMorph Window Test 5') is None, 'Context menu did not refresh title')
            fixture_command('add', 6)
            wait_windows(lambda: row_button('DeskMorph Window Test 6') is not None, 'Context menu did not add a new window')
            fixture_command('close', 6)
            wait_windows(lambda: row_button('DeskMorph Window Test 6') is None, 'Context menu retained externally closed window')
            window_passed.append('right-click menu refreshes renamed, added and externally closed windows while open')
            click('DeskMorph Context Renamed 5')
            wait_windows(lambda: context_state['5']['xid'] in subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True), 'Context row did not activate exact selected XID')
            wait_windows(lambda: not popup_visible(), 'Context activation did not dismiss popup')
            focus_studio()
            node = group_node(2)
            native_click_node(node, button=3)
            click('Đóng DeskMorph Context Renamed 5')
            wait_windows(lambda: context_state['5']['xid'] not in managed_fixture(), 'Context close did not remove exact target window')
            assert fixture_state['1']['xid'] in managed_fixture(), 'Context close removed a different window'
            window_passed.append('context rows activate exact selected XID and close only the selected window')
            fixture_command('add', 7)
            focus_studio(); open_windows(2)
            fixture_command('close', 7)
            wait_windows(lambda: row_button('DeskMorph Window Test 7') is None, 'Window list retained the last extra fixture')
            fixture_command('close', 1)
            wait_windows(lambda: not popup_visible(), 'Last external close did not dismiss empty list')
            wait_windows(lambda: any(n.get_name() == group_button(0) for n, _ in descendants(app)), 'Pinned app did not remain with zero windows')
            window_passed.append('external close updates 3 to 1 to 0; empty popup hides and pinned app remains')
        finally:
            if fixture:
                owned_input_pids.discard(fixture.pid)
                if fixture.poll() is None: fixture.terminate()
                fixture.communicate(timeout=5)
            focus_studio()
            # Removing the test-only pin keeps every pre-existing pin and order.
            if any(pin.get('desktopId') == 'deskmorph-window-fixture.desktop' for pin in window_config()['pinnedApps']):
                wait_windows(lambda: any(n.get_name() == group_button(0) for n, _ in descendants(app)), 'Test-only pin did not reach zero windows for cleanup')
                node = group_node(0)
                native_click_node(node, button=3); click('Bỏ ghim')
            assert window_config()['pinnedApps'] == original_pins, 'Window test changed original pins'
            wait_windows(lambda: not any(n.get_name() in ('DeskMorph Window Fixture • 0 cửa sổ', 'DeskMorphWindowFixture • 0 cửa sổ') for n, _ in descendants(app)), 'Unpinned group did not disappear at zero windows')
            click('Taskbar Studio')
            if window_config()['autoHide'] != window_original_auto: click('Tự động ẩn Dock Chạm cạnh màn hình để hiện lại; Dock giữ hiện khi bạn thao tác popup.')
            if window_config()['enabled'] != window_original_enabled: click('Bật Dock')
        report = {'passed': window_passed, 'pid': app.get_process_id(), 'fixturePid': fixture.pid, 'pinsRestored': True}
        Path('/tmp/deskmorph-desktop-test/window-list-result.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
    if args.registration_smoke:
        from gi.repository import Gio
        import shutil
        test_root = Path('/tmp/deskmorph-desktop-test')
        menu_file = test_root / 'data/applications/deskmorph.desktop'
        autostart_file = Path(TEST_CONFIG) / 'autostart/deskmorph.desktop'
        targets = (menu_file, autostart_file)
        saved_entries = {p: (p.read_bytes(), p.stat().st_mode & 0o777) if p.is_file() else None for p in targets}
        assert all(not p.exists() or p.is_file() for p in targets), 'Registration targets must be absent or regular test files'
        registration_binary = test_root / 'registration space " 100% $fixture' / 'deskmorph'
        registration_binary.parent.mkdir(exist_ok=True)
        assert not registration_binary.exists(), 'Do not overwrite an existing binary fixture'
        source_binary = Path(__file__).resolve().parents[1] / 'src-tauri/target/agent/debug/deskmorph'
        try: os.link(source_binary, registration_binary)
        except OSError: shutil.copy2(source_binary, registration_binary)
        registration_passed = []
        registration_pids = []
        def wait_registration(predicate, message):
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                if predicate(): return
                time.sleep(0.1)
            raise AssertionError(message)
        def registered_alert():
            # WebKit/AT-SPI may expose a DOM role=alert as a paragraph.
            # Check the actual IO failure text, not a platform role spelling.
            for node, _ in descendants(app):
                text = node.get_name() or ''
                interface = node.get_text_iface()
                if interface: text += Atspi.Text.get_text(interface, 0, -1)
                if 'os error 21' in text: return True
            return False
        def autostart_checked():
            checkbox = next(n for n, _ in descendants(app) if n.get_name() == 'Khởi động cùng hệ thống' and n.get_role_name() == 'check box')
            return checkbox.get_state_set().contains(Atspi.StateType.CHECKED)
        def exit_registration():
            focus_studio(); click('Hệ thống'); pid = app.get_process_id(); click('Thoát DeskMorph')
            def stopped():
                try: return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z'
                except FileNotFoundError: return True
            wait_registration(stopped, 'Registration test instance did not exit')
            try: os.waitpid(pid, os.WNOHANG)
            except ChildProcessError: pass
        try:
            exit_registration()
            app = start_isolated_app(registration_binary)
            registration_pids.append(app.get_process_id())
            assert os.readlink(f'/proc/{app.get_process_id()}/exe') == str(registration_binary), 'Fixture must run at the path being registered'
            focus_studio(); click('Hệ thống')
            if autostart_checked(): click('Khởi động cùng hệ thống')
            click('Đăng ký vào menu ứng dụng')
            click('Khởi động cùng hệ thống')
            assert autostart_checked()
            for entry_path in targets:
                entry = Gio.DesktopAppInfo.new_from_filename(str(entry_path))
                assert entry is not None, 'GIO could not parse installed desktop entry'
                assert '100%%' in entry_path.read_text() and 'space' in entry_path.read_text()
            assert 'X-GNOME-Autostart-enabled=true' in autostart_file.read_text()
            registration_passed.append('UI installs menu/autostart entries for actual executable path containing spaces, quotes, percent and dollar')
            # Start via each generated entry through GIO, not a shell or copied argv.
            # Temporarily set only app-owned profile variables inherited by GIO children.
            launch_vars = dict(DESKMORPH_CONFIG_HOME=TEST_CONFIG, XDG_DATA_HOME=str(test_root / 'data'), XDG_CACHE_HOME=str(test_root / 'cache'))
            previous_vars = {key: os.environ.get(key) for key in launch_vars}
            os.environ.update(launch_vars)
            try:
                pid = app.get_process_id()
                close_studio_native()
                Gio.DesktopAppInfo.new_from_filename(str(menu_file)).launch([], None)
                time.sleep(1)
                app = test_app()
                assert app.get_process_id() == pid
                focus_studio()
                registration_passed.append('installed menu entry launches quoted binary and reopens existing Studio')
                exit_registration()
                Gio.DesktopAppInfo.new_from_filename(str(autostart_file)).launch([], None)
                def registered_app_ready():
                    try: return any(n.get_role_name() == 'button' for n, _ in descendants(test_app()))
                    except RuntimeError: return False
                wait_registration(registered_app_ready, 'Generated autostart entry did not launch isolated app')
                app = test_app(); registration_pids.append(app.get_process_id())
                assert app.get_process_id() != pid
                assert os.readlink(f'/proc/{app.get_process_id()}/exe') == str(registration_binary)
                registration_passed.append('generated autostart entry launches fresh app through GIO (manual launch, not desktop login)')
            finally:
                for key, value in previous_vars.items():
                    if value is None: os.environ.pop(key, None)
                    else: os.environ[key] = value
            focus_studio(); click('Hệ thống')
            assert autostart_checked(), 'Autostart registration was not detected after restart'
            click('Khởi động cùng hệ thống')
            assert not autostart_file.exists() and not autostart_checked()
            registration_passed.append('autostart detection survives restart and disabling removes entry')
            for entry_path, label in ((autostart_file, 'Khởi động cùng hệ thống'), (menu_file, 'Đăng ký vào menu ứng dụng')):
                click('Đăng ký vào menu ứng dụng')
                wait_registration(lambda: not registered_alert(), 'Successful registration did not clear previous error')
                if entry_path.exists(): entry_path.unlink()
                entry_path.mkdir()
                try:
                    click(label)
                    wait_registration(registered_alert, 'Write failure did not appear as UI alert')
                    assert entry_path.is_dir(), 'Failed registration replaced fixture unexpectedly'
                    if entry_path == autostart_file: assert not autostart_checked(), 'Failed write falsely enabled autostart'
                finally: entry_path.rmdir()
            registration_passed.append('menu/autostart write failures reach UI; failed enable does not report enabled')
        finally:
            try:
                app = test_app(); exit_registration()
            except RuntimeError: pass
            for entry_path, original in saved_entries.items():
                if entry_path.is_dir(): entry_path.rmdir()
                if original:
                    entry_path.write_bytes(original[0]); entry_path.chmod(original[1])
                elif entry_path.exists(): entry_path.unlink()
            registration_binary.unlink(missing_ok=True)
            app = start_isolated_app()
        report = {'passed': registration_passed, 'pids': registration_pids, 'entriesRestored': True}
        (test_root / 'registration-result.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
    if args.lifecycle_smoke:
        lifecycle_path = Path(TEST_CONFIG) / 'com.ducthanhdev.deskmorph/config.json'
        lifecycle_config = lambda: json.loads(lifecycle_path.read_text())['config']
        lifecycle_original = lifecycle_config()
        lifecycle_passed = []
        lifecycle_pids = [app.get_process_id()]
        def wait_lifecycle(predicate, message):
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if predicate(): return
                time.sleep(0.1)
            raise AssertionError(message)
        def lifecycle_alive(pid):
            try: return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] != 'Z'
            except FileNotFoundError: return False
        def managed_titles():
            titles = []
            for xid in re.findall(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True)):
                props = subprocess.run(['xprop', '-id', xid, '_NET_WM_PID', '_NET_WM_NAME'], capture_output=True, text=True).stdout
                if re.search(r'_NET_WM_PID.*= ' + str(app.get_process_id()) + r'\b', props):
                    titles.append(props)
            return titles
        def title_count(title): return sum(title in props for props in managed_titles())
        def set_lifecycle(field, value, tab, label):
            click(tab)
            if lifecycle_config()[field] != value: click(label)
            assert lifecycle_config()[field] == value, f'{field} was not persisted'
        def expect_exit(pid):
            wait_lifecycle(lambda: not lifecycle_alive(pid), 'Isolated app did not exit normally')
            try: os.waitpid(pid, os.WNOHANG)
            except ChildProcessError: pass
        def fresh_lifecycle():
            candidate = start_isolated_app()
            lifecycle_pids.append(candidate.get_process_id())
            return candidate
        def quit_lifecycle():
            focus_studio(); click('Hệ thống')
            pid = app.get_process_id(); click('Thoát DeskMorph'); expect_exit(pid)
        try:
            focus_studio()
            set_lifecycle('autoHide', False, 'Taskbar Studio', 'Tự động ẩn Dock Chạm cạnh màn hình để hiện lại; Dock giữ hiện khi bạn thao tác popup.')
            set_lifecycle('keepDockOnClose', True, 'Hệ thống', 'Giữ Dock khi đóng Studio')
            for enabled in (False, True, False, True):
                set_lifecycle('enabled', enabled, 'Taskbar Studio', 'Bật Dock')
                wait_lifecycle(lambda: title_count('DeskMorph Taskbar') == int(enabled), 'Toggle did not update native Dock visibility')
                old_pid = app.get_process_id()
                quit_lifecycle(); app = fresh_lifecycle()
                assert app.get_process_id() != old_pid
                assert lifecycle_config()['enabled'] == enabled
                wait_lifecycle(lambda: title_count('DeskMorph Taskbar') == int(enabled), 'Restart did not preserve Dock visibility')
                # Allow delayed startup/layout callbacks to run before checking again.
                time.sleep(1.2)
                assert title_count('DeskMorph Taskbar') == int(enabled), 'Delayed startup reversed enabled state'
            lifecycle_passed.append('enabled false/true persists across four normal restarts and delayed layout')
            for repeat in range(3):
                focus_studio(); close_studio_native()
                pid = app.get_process_id()
                assert lifecycle_alive(pid) and title_count('DeskMorph Taskbar') == 1
                assert title_count('DeskMorph Studio') == 0
                reopen_studio(); app = test_app()
                assert app.get_process_id() == pid
                wait_lifecycle(lambda: title_count('DeskMorph Studio') == 1, 'Forwarding did not reopen Studio')
            lifecycle_passed.append('closing Studio keeps enabled Dock; relaunch reopens same instance three times')
            # Concurrent invocations use the same verified profile and must ACK/exit.
            test_root = Path('/tmp/deskmorph-desktop-test')
            entry_env = dict(os.environ, DESKMORPH_CONFIG_HOME=TEST_CONFIG,
                             XDG_DATA_HOME=str(test_root / 'data'), XDG_CACHE_HOME=str(test_root / 'cache'), WEBKIT_DISABLE_DMABUF_RENDERER='1')
            executable = Path(__file__).resolve().parents[1] / 'src-tauri/target/agent/debug/deskmorph'
            entrants = [subprocess.Popen([str(executable)], env=entry_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(4)]
            try:
                for entrant in entrants:
                    out, err = entrant.communicate(timeout=8)
                    assert entrant.returncode == 0, f'Forwarded instance failed: {err.decode()[-500:]}'
            finally:
                for entrant in entrants:
                    if entrant.poll() is None: entrant.terminate()
                    entrant.wait(timeout=5)
            assert test_app().get_process_id() == app.get_process_id()
            assert title_count('DeskMorph Studio') == 1 and title_count('DeskMorph Taskbar') == 1
            lifecycle_passed.append('four concurrent launches ACK and exit with one Studio and one Dock')
            for enabled, keep in ((False, True), (True, False)):
                focus_studio()
                set_lifecycle('enabled', enabled, 'Taskbar Studio', 'Bật Dock')
                set_lifecycle('keepDockOnClose', keep, 'Hệ thống', 'Giữ Dock khi đóng Studio')
                pid = app.get_process_id(); close_studio_native(); expect_exit(pid)
                app = fresh_lifecycle()
            lifecycle_passed.append('closing Studio exits when Dock disabled or keep-Dock option off')
            set_lifecycle('enabled', True, 'Taskbar Studio', 'Bật Dock')
            set_lifecycle('keepDockOnClose', True, 'Hệ thống', 'Giữ Dock khi đóng Studio')
            quit_lifecycle(); app = fresh_lifecycle()
            lifecycle_passed.append('explicit Quit exits even when keep-Dock option on')
        finally:
            try:
                app = test_app()
                reopen_studio()
            except RuntimeError: app = fresh_lifecycle()
            focus_studio()
            set_lifecycle('keepDockOnClose', lifecycle_original['keepDockOnClose'], 'Hệ thống', 'Giữ Dock khi đóng Studio')
            set_lifecycle('enabled', lifecycle_original['enabled'], 'Taskbar Studio', 'Bật Dock')
            set_lifecycle('autoHide', lifecycle_original['autoHide'], 'Taskbar Studio', 'Tự động ẩn Dock Chạm cạnh màn hình để hiện lại; Dock giữ hiện khi bạn thao tác popup.')
        report = {'passed': lifecycle_passed, 'pids': lifecycle_pids, 'preferencesRestored': True}
        Path('/tmp/deskmorph-desktop-test/lifecycle-result.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
    if args.shortcut_smoke:
        config_path = Path(TEST_CONFIG) / 'com.ducthanhdev.deskmorph/config.json'
        shortcut_config = lambda: json.loads(config_path.read_text())['config']
        original_shortcut = shortcut_config()['launcherShortcut']
        original_enabled = shortcut_config()['enabled']
        def wait_shortcut(predicate, message):
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if predicate(): return
                time.sleep(0.1)
            raise AssertionError(message)
        def text_present(value):
            return any(n.get_text_iface() and value in Atspi.Text.get_text(n.get_text_iface(), 0, -1) for n, _ in descendants(app))
        def launcher_mapped():
            for xid in re.findall(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True)):
                props = subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID', '_NET_WM_NAME'], text=True)
                if 'DeskMorph Context Menu' in props and re.search(r'_NET_WM_PID.*= ' + str(app.get_process_id()) + r'\b', props): return True
            return False
        class Cookie(ctypes.Structure): _fields_ = [('sequence', ctypes.c_uint)]
        xcb = ctypes.CDLL('libxcb.so.1'); x11 = ctypes.CDLL('libX11.so.6'); libc = ctypes.CDLL(None)
        xcb.xcb_connect.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]; xcb.xcb_connect.restype = ctypes.c_void_p
        xcb.xcb_disconnect.argtypes = [ctypes.c_void_p]
        xcb.xcb_grab_key_checked.argtypes = [ctypes.c_void_p, ctypes.c_ubyte, ctypes.c_uint, ctypes.c_ushort, ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_ubyte]; xcb.xcb_grab_key_checked.restype = Cookie
        xcb.xcb_request_check.argtypes = [ctypes.c_void_p, Cookie]; xcb.xcb_request_check.restype = ctypes.c_void_p
        libc.free.argtypes = [ctypes.c_void_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p; x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]; x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]; x11.XKeysymToKeycode.restype = ctypes.c_ubyte
        display = x11.XOpenDisplay(None); assert display
        root = x11.XDefaultRootWindow(display)
        codes = {key: x11.XKeysymToKeycode(display, key) for key in (0x6b, 0x6a)}
        x11.XCloseDisplay(display)
        def claim(key):
            connection = xcb.xcb_connect(None, None); assert connection
            error = xcb.xcb_request_check(connection, xcb.xcb_grab_key_checked(connection, 0, root, 4 | 8 | 64, codes[key], 1, 1))
            if error:
                code = ctypes.cast(error, ctypes.POINTER(ctypes.c_ubyte))[1]
                libc.free(error); xcb.xcb_disconnect(connection)
                assert code == 10, 'Unexpected native key-grab error'
                return None
            return connection
        def free_chord(key):
            probe = claim(key)
            if not probe: return False
            xcb.xcb_disconnect(probe); return True
        def save_shortcut(value):
            click('Hệ thống')
            type_entry('Tổ hợp phím', value)
            click('Lưu phím tắt')
            wait_shortcut(lambda: shortcut_config()['launcherShortcut'] == value, 'Shortcut was not persisted')
        def expect_open(key, fixture=None):
            if fixture is None: focus_studio()
            else:
                assert fixture.poll() is None, 'Owned keyboard fixture exited'
                focus_studio('DeskMorph Smoke 2', fixture.pid)
            native_keys(chord=[0xffe3, 0xffe9, 0xffeb, key])
            wait_shortcut(launcher_mapped, 'Registered shortcut did not open the launcher')
            def launcher_focused():
                xid = re.search(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)).group(0)
                props = subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID', '_NET_WM_NAME'], text=True)
                return 'DeskMorph Context Menu' in props and bool(re.search(r'_NET_WM_PID.*= ' + str(app.get_process_id()) + r'\b', props))
            wait_shortcut(launcher_focused, 'Shortcut launcher did not receive native keyboard focus')
            native_keys(chord=[0xff1b])
            wait_shortcut(lambda: not launcher_mapped(), 'Shortcut launcher did not dismiss with Escape')
        holder = None
        keyboard_fixture = None
        passed = []
        try:
            if not original_enabled:
                click('Taskbar Studio'); click('Bật Dock')
            click('Hệ thống')
            if original_shortcut is not None:
                click('Tắt phím tắt')
                wait_shortcut(lambda: text_present('Phím tắt đang tắt'), 'Could not disable existing test-profile shortcut')
            holder = claim(0x6b)
            assert holder, 'Reference Ctrl+Alt+Super+K is already owned; no shortcut input will be sent'
            save_shortcut('Ctrl+Alt+Super+K')
            wait_shortcut(lambda: text_present('Tổ hợp phím đã được ứng dụng hoặc desktop khác sử dụng'), 'Conflict did not produce a clear UI error')
            passed.append('checked native conflict is visible without stealing the existing grab')
            xcb.xcb_disconnect(holder); holder = None
            click('Thử lại')
            wait_shortcut(lambda: text_present('Phím tắt đang hoạt động: Ctrl+Alt+Super+K'), 'Retry did not register released shortcut')
            expect_open(0x6b)
            passed.append('retry and physical shortcut open launcher, Escape dismisses')
            fixture_env = dict(os.environ, DESKMORPH_CONFIG_HOME=TEST_CONFIG)
            keyboard_fixture = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).resolve()), '--fixture'], env=fixture_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            expected_env = b'DESKMORPH_CONFIG_HOME=' + TEST_CONFIG.encode()
            assert expected_env in Path(f'/proc/{keyboard_fixture.pid}/environ').read_bytes().split(b'\0')
            owned_input_pids.add(keyboard_fixture.pid)
            time.sleep(0.8)
            expect_open(0x6b, keyboard_fixture)
            passed.append('global shortcut opens focused launcher from a separate owned GTK fixture')
            focus_studio()
            save_shortcut('Ctrl+Alt+Super+J')
            wait_shortcut(lambda: text_present('Phím tắt đang hoạt động: Ctrl+Alt+Super+J'), 'Changed shortcut was not registered')
            wait_shortcut(lambda: free_chord(0x6b), 'Previous shortcut was not released after change')
            expect_open(0x6a)
            passed.append('changing shortcut releases the old chord and activates the new chord')
            click('Taskbar Studio'); click('Bật Dock')
            wait_shortcut(lambda: free_chord(0x6a), 'Disabling Dock did not release shortcut')
            click('Hệ thống')
            wait_shortcut(lambda: text_present('Phím tắt tạm dừng vì Dock đang tắt'), 'Paused shortcut state was not visible')
            click('Taskbar Studio'); click('Bật Dock'); click('Hệ thống')
            wait_shortcut(lambda: text_present('Phím tắt đang hoạt động: Ctrl+Alt+Super+J'), 'Enabling Dock did not restore shortcut')
            expect_open(0x6a)
            passed.append('disabling Dock pauses grabs and enabling restores saved shortcut')
            click('Hệ thống')
            old_pid = app.get_process_id()
            click('Thoát DeskMorph')
            wait_shortcut(lambda: free_chord(0x6a), 'Normal exit did not release shortcut')
            # This is a fresh long-running process, unlike reopen_studio(),
            # which forwards to an existing instance and waits for its ACK.
            try:
                if process.pid == old_pid: process.wait(timeout=8)
            except NameError: pass
            app = start_isolated_app()
            assert app.get_process_id() != old_pid, 'Shortcut restart did not create a new isolated app process'
            click('Hệ thống')
            wait_shortcut(lambda: text_present('Phím tắt đang hoạt động: Ctrl+Alt+Super+J'), 'Saved shortcut did not register on startup')
            expect_open(0x6a)
            passed.append('normal exit releases grabs and startup restores saved shortcut')
            click('Hệ thống'); click('Tắt phím tắt')
            wait_shortcut(lambda: free_chord(0x6a), 'Disable left the shortcut registered')
            assert shortcut_config()['launcherShortcut'] is None
            passed.append('disable persists null and releases native grab')
        finally:
            if holder: xcb.xcb_disconnect(holder)
            if keyboard_fixture:
                owned_input_pids.discard(keyboard_fixture.pid)
                if keyboard_fixture.poll() is None: keyboard_fixture.terminate()
                keyboard_fixture.wait(timeout=5)
            try: app = test_app()
            except RuntimeError: app = start_isolated_app()
            focus_studio(); click('Hệ thống')
            if original_shortcut is None:
                if shortcut_config()['launcherShortcut'] is not None: click('Tắt phím tắt')
            else: save_shortcut(original_shortcut)
            if shortcut_config()['enabled'] != original_enabled:
                click('Taskbar Studio'); click('Bật Dock')
        report = {'passed': passed, 'pid': app.get_process_id(), 'originalShortcutRestored': True}
        Path('/tmp/deskmorph-desktop-test/shortcut-result.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
    if args.focus_smoke:
        from popup_focus_smoke import run
        try:
            run(app, TEST_CONFIG, click, focus_studio, native_keys, native_click_node, owned_input_pids)
        finally:
            if args.focus_smoke:
                assert test_app().get_process_id() == app.get_process_id()
                os.kill(app.get_process_id(), signal.SIGTERM)
                process.wait(timeout=5)
                app = start_isolated_app()  # Remove debug timing control after the test.

    if args.popup_smoke:
        popup_config_path = Path(TEST_CONFIG) / 'com.ducthanhdev.deskmorph/config.json'
        popup_config = lambda: json.loads(popup_config_path.read_text())['config']
        original_auto = popup_config()['autoHide']
        auto_label = 'Tự động ẩn Dock Chạm cạnh màn hình để hiện lại; Dock giữ hiện khi bạn thao tác popup.'
        focus_studio()
        click('Taskbar Studio')
        if original_auto: click(auto_label)
        try:
            for popup_round in range(3):
                def visible_frames():
                    frames = {}
                    for xid in re.findall(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True)):
                        props = subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID', '_NET_WM_NAME'], text=True)
                        pid = re.search(r'_NET_WM_PID.*= (\d+)', props)
                        if pid and int(pid.group(1)) == app.get_process_id():
                            title = re.search(r'_NET_WM_NAME\([^)]*\) = "(.*)"', props)
                            if title: frames[title.group(1)] = xid
                    return frames
                def wait_popup(predicate, message, stable_for=0):
                    deadline = time.monotonic() + 8
                    stable_since = None
                    while time.monotonic() < deadline:
                        if predicate():
                            if stable_since is None: stable_since = time.monotonic()
                            if time.monotonic() - stable_since >= stable_for: return
                        else: stable_since = None
                        time.sleep(0.1)
                    raise AssertionError(message + ': ' + str(visible_frames()) + '; ' + subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True).strip()
                                         + '; mute=' + str(any(n.get_name() == 'Tắt tiếng' for n, _ in descendants(app))))
                popup_titles = {'DeskMorph Context Menu', 'DeskMorph Calendar'}
                focus_studio()
                click('Tìm ứng dụng')
                wait_popup(lambda: popup_titles & visible_frames().keys() == {'DeskMorph Context Menu'}, 'Launcher popup not the only active popup')
                launcher_section = next(n for n, _ in descendants(app) if n.get_role_name() == 'landmark' and n.get_name() == 'Tìm ứng dụng')
                launch_actions = [n.get_name() for n, _ in descendants(launcher_section) if n.get_role_name() == 'button' and n.get_name().startswith('Mở ')]
                assert launch_actions and all(name in ('Mở DeskMorph Smoke Fixture', 'Mở DeskMorph Stress Noop') for name in launch_actions), 'Stress launcher exposed a non-fixture application'
                native_keys(chord=[0xff1b])
                wait_popup(lambda: not popup_titles & visible_frames().keys(), 'Escape did not hide launcher')
                click('Mở lịch')
                wait_popup(lambda: popup_titles & visible_frames().keys() == {'DeskMorph Calendar'}, 'Calendar not the only popup')
                click('Âm thanh', 'button')
                wait_popup(lambda: popup_titles & visible_frames().keys() == {'DeskMorph Context Menu'}, 'Audio did not replace calendar')
                focus_studio()
                wait_popup(lambda: not popup_titles & visible_frames().keys(), 'Focus loss did not dismiss popup')
                studio_xid = visible_frames()['DeskMorph Studio']
                time.sleep(0.5)
                assert studio_xid in subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True), 'Popup dismissal stole focus from selected Studio'
                click('Tìm ứng dụng')
                heading = next(n for n, _ in descendants(app) if n.get_role_name() == 'heading' and n.get_name() == 'DeskMorph')
                studio_frame = next(n for n, _ in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Studio')
                studio_rect = studio_frame.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
                heading_rect = heading.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
                # The top-positioned launcher can cover the brand heading.
                # Click the empty right side of our Studio header, and prove
                # the point is outside every mapped popup before sending input.
                outside = (studio_rect.x + studio_rect.width - 30, heading_rect.y + heading_rect.height // 2)
                for frame, _ in descendants(app):
                    if frame.get_role_name() == 'frame' and frame.get_name() in popup_titles and frame.get_state_set().contains(Atspi.StateType.SHOWING):
                        rect = frame.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
                        assert not (rect.x <= outside[0] < rect.x + rect.width and rect.y <= outside[1] < rect.y + rect.height), 'Safe header point is covered by a popup'
                native_click_node(studio_frame, point=outside)
                wait_popup(lambda: not popup_titles & visible_frames().keys(), 'Click outside popup did not dismiss it')
                assert studio_xid in subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True), 'Outside click did not retain selected Studio focus'
                for _ in range(5):
                    for name in ('Tìm ứng dụng', 'Mở lịch', 'Âm thanh'):
                        require_unlocked_desktop()
                        node = next(n for n, _ in descendants(app) if n.get_role_name() == 'button' and n.get_name() == name)
                        assert node.get_action_iface().do_action(0)
                    # AT-SPI queues actions; a previous audio popup can satisfy the same
                    # title/content predicate before this batch has reached the UI.
                    # Require the final state and native focus to stay settled before
                    # sending Escape, while keeping the three actions themselves rapid.
                    def final_audio():
                        frames = visible_frames()
                        active = subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)
                        return (popup_titles & frames.keys() == {'DeskMorph Context Menu'}
                                and frames['DeskMorph Context Menu'] in active
                                and any(n.get_name() == 'Tắt tiếng' for n, _ in descendants(app)))
                    wait_popup(final_audio, 'Rapid replacement left wrong, unfocused or orphaned popup', stable_for=0.5)
                    assert 'DeskMorph Tooltip' not in visible_frames(), 'Tooltip remained over active popup'
                print('Popup focus before Escape:', subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True).strip(),
                      [(n.get_role_name(), n.get_name()) for n, _ in descendants(app) if n.get_state_set().contains(Atspi.StateType.FOCUSED)], flush=True)
                native_keys(chord=[0xff1b])
                wait_popup(lambda: not popup_titles & visible_frames().keys(), 'Escape after rapid replacement left a popup')
                report = {'passed': ['launcher Escape', 'calendar/audio replace each other with one active popup', 'focus loss dismisses without stealing selected Studio focus', 'outside click dismisses and retains selected focus', 'five rapid launcher/calendar/audio cycles without orphaned popup or overlapping tooltip', 'Escape after rapid replacement'], 'pid': app.get_process_id()}
                report['completedRounds'] = popup_round + 1
                Path('/tmp/deskmorph-desktop-test/popup-result.json').write_text(json.dumps(report, indent=2))
                print(json.dumps(report))
        finally:
            focus_studio()
            click('Taskbar Studio')
            if popup_config()['autoHide'] != original_auto: click(auto_label)
    if args.basic:
        path = Path(TEST_CONFIG) / 'com.ducthanhdev.deskmorph/config.json'
        config = lambda: json.loads(path.read_text())
        click('Taskbar Studio')
        initial = config()
        def set_position(value):
            click('Dưới đáy (Đề xuất)' if value == 'bottom' else 'Trên đỉnh màn hình')
        set_position('top')
        assert config()['config']['position'] == 'top', 'Top position was not persisted'
        dock = next(n for n, _ in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Taskbar')
        top = dock.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        set_position('bottom')
        assert config()['config']['position'] == 'bottom', 'Bottom position was not persisted'
        bottom = dock.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        assert bottom.y > top.y, 'Native Dock did not move from top to bottom'
        click('Bật Dock')
        assert config()['config']['enabled'] is False, 'Disabled state was not persisted'
        click('Bật Dock')
        assert config()['config']['enabled'] is True, 'Enabled state was not persisted'
        assert config()['revision'] >= initial['revision'] + 4, 'Native revisions did not advance'
        click('Mở lịch')
        assert any(n.get_name() == 'DeskMorph Calendar' for n, _ in descendants(app)), 'Calendar window did not open'
        report = {'passed': ['native top/bottom positioning', 'config persistence and revisions', 'disable/enable Dock', 'calendar popup opens'],
                  'pid': app.get_process_id(), 'top': [top.x, top.y, top.width, top.height],
                  'bottom': [bottom.x, bottom.y, bottom.width, bottom.height]}
        print(json.dumps(report, ensure_ascii=False))
        Path('/tmp/deskmorph-desktop-test/basic-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if args.studio_smoke:
        path = Path(TEST_CONFIG) / 'com.ducthanhdev.deskmorph/config.json'
        config = lambda: json.loads(path.read_text())['config']
        original = config()
        click('Giao diện')
        click('Nord tối giản')
        applied = config()
        assert applied['height'] == 48 and applied['accentColor'] == '#88c0d0', 'Preset was not persisted'
        for field in ('pinnedApps', 'enabled', 'autoHide', 'monitor', 'keepDockOnClose', 'language'):
            assert applied[field] == original[field], f'Preset overwrote {field}'
        click('Hoàn tác')
        assert config() == original, 'Preset undo did not restore configuration'
        type_entry('Tên preset', 'smoke preset')
        click('Lưu giao diện hiện tại')
        assert any(p['name'] == 'smoke preset' for p in config()['presets']), 'Custom preset was not saved'
        click('Đổi tên')
        type_entry('Tên preset', 'smoke renamed')
        # The rename action and the editor submit share a label; choose the last.
        rename = [n for n, _ in descendants(app) if n.get_name() == 'Đổi tên' and n.get_role_name() == 'button']
        require_unlocked_desktop()
        assert rename[-1].get_action_iface().do_action(0)
        time.sleep(0.7)
        assert any(p['name'] == 'smoke renamed' for p in config()['presets']), 'Custom preset rename failed'
        click('Xóa')
        assert config()['presets'] == original['presets'], 'Custom preset delete failed'
        click('Hệ thống')
        click('English')
        assert config()['language'] == 'en', 'Language was not persisted'
        assert any(n.get_name() == 'Search applications' for n, _ in descendants(app)), 'Dock did not receive English language setting'
        click('Tiếng Việt')
        assert config()['language'] == 'vi'
        before = config()
        click('Khôi phục cấu hình mặc định')
        assert config() == before, 'Opening reset review changed configuration'
        click('Hủy')
        assert config() == before, 'Cancelling reset changed configuration'
        click('Xuất cấu hình')
        click('Hủy')
        assert config() == before, 'Cancelling export changed configuration'
        click('Khôi phục cấu hình mặc định')
        click('Xác nhận khôi phục')
        defaults = json.loads((Path(__file__).resolve().parents[1] / 'src/config/defaults.json').read_text())
        expected = dict(defaults, language=before['language'], presets=before['presets'])
        assert config() == expected, 'Confirmed reset did not match the documented scope'
        click('Hoàn tác')
        assert config() == before, 'Reset undo did not restore the previous configuration'
        report = {'passed': ['preset applies and persists', 'preset scope preserves pins and lifecycle', 'preset undo', 'custom preset save/rename/delete',
                             'language persists and synchronizes to Dock', 'reset review and cancellation', 'native export dialog cancellation', 'confirmed reset scope and undo'], 'pid': app.get_process_id()}
        print(json.dumps(report, ensure_ascii=False))
        Path('/tmp/deskmorph-desktop-test/studio-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if args.command_errors_smoke:
        from command_errors_smoke import run
        run(app, TEST_CONFIG, click, focus_studio, native_keys, type_entry, native_click_node)
    if args.config_smoke:
        focus_studio()
        click('Hệ thống')
        path = Path(TEST_CONFIG) / 'com.ducthanhdev.deskmorph/config.json'
        snapshot = lambda: json.loads(path.read_text())
        before = snapshot()
        test_root = Path('/tmp/deskmorph-desktop-test')
        exported = test_root / f'export-{int(time.time())}.json'
        click('Xuất cấu hình')
        focus_studio('Xuất cấu hình')
        native_keys(chord=[0xffe3, ord('l')])
        native_keys(value=str(exported))
        click('Lưu')
        assert exported.exists(), 'Export dialog did not create the chosen file'
        document = json.loads(exported.read_text())
        assert document == {'schemaVersion': 1, 'config': before['config']}, 'Export does not match persisted config'
        assert snapshot() == before, 'Export changed active configuration'
        changed = dict(before['config'], height=64 if before['config']['height'] != 64 else 52)
        valid = test_root / 'import-valid.json'
        valid.write_text(json.dumps({'schemaVersion': 1, 'config': changed}))
        invalid = test_root / 'import-invalid.json'
        invalid.write_text(json.dumps({'schemaVersion': 1, 'config': {'height': 1000}}))
        broken = test_root / 'import-broken.json'
        broken.write_text('{broken')
        def choose_file(file):
            focus_studio()
            click('Nhập cấu hình')
            focus_studio('Select File')
            native_keys(chord=[0xffe3, ord('l')])
            native_keys(value=str(file))
            native_keys(chord=[0xff0d])
            time.sleep(0.8)
        choose_file(valid)
        assert snapshot() == before, 'Review changed active configuration before confirmation'
        assert any(n.get_name() == 'Áp dụng cấu hình đã nhập' for n, _ in descendants(app)), 'Import summary is missing'
        click('Áp dụng cấu hình đã nhập')
        assert snapshot()['config'] == changed, 'Import did not persist reviewed configuration'
        click('Hoàn tác')
        assert snapshot()['config'] == before['config'], 'Import undo failed'
        for file in (invalid, broken):
            saved = snapshot()
            choose_file(file)
            assert snapshot() == saved, 'Invalid JSON changed active configuration'
            assert any((n.get_role_name() in ('alert', 'notification') or n.get_attributes().get('xml-roles') == 'alert') for n, _ in descendants(app)), 'Invalid JSON did not show an accessible error'
            assert not any(n.get_name() == 'Áp dụng cấu hình đã nhập' for n, _ in descendants(app)), 'Invalid JSON offered an apply action'
        choose_file(valid)
        click('Giữ Dock khi đóng Studio')
        concurrent = snapshot()
        click('Áp dụng cấu hình đã nhập')
        assert snapshot() == concurrent, 'Stale review overwrote a concurrent edit'
        click('Hủy')
        click('Giữ Dock khi đóng Studio')
        assert snapshot()['config'] == before['config'], 'Test failed to restore lifecycle option'
        report = {'passed': ['native JSON export contents', 'native JSON import review and apply', 'import undo',
                             'invalid schema and malformed JSON preserve state', 'stale review preserves concurrent edit'], 'pid': app.get_process_id()}
        print(json.dumps(report, ensure_ascii=False))
        (test_root / 'config-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if args.system_open_smoke:
        def cosmic_windows():
            root = subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True)
            result = {}
            for xid in re.findall(r'0x[0-9a-fA-F]+', root):
                props = subprocess.run(['xprop', '-id', xid, 'WM_CLASS', '_NET_WM_NAME', '_NET_WM_PID'], capture_output=True, text=True).stdout
                if '"cosmic-files"' in props: result[xid] = props
            return result
        previous = cosmic_windows()
        focus_studio(); click('Tiện ích hệ thống', 'button')
        trash_button = next(n for n, _ in descendants(app) if n.get_name() == 'Mở Thùng rác' and n.get_role_name() == 'button')
        gi.require_version('Gio', '2.0')
        from gi.repository import Gio
        trash_handler = Gio.AppInfo.get_default_for_uri_scheme('trash')
        trash_available = bool(trash_handler and trash_handler.supports_uris() and
                               not (isinstance(trash_handler, Gio.DesktopAppInfo) and trash_handler.get_is_hidden()))
        assert trash_button.get_state_set().contains(Atspi.StateType.ENABLED) == trash_available, 'Trash button does not match desktop capability'
        click('Mở Downloads')
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            new = {xid: props for xid, props in cosmic_windows().items() if xid not in previous and 'Downloads' in props}
            if len(new) == 1: break
            time.sleep(0.2)
        else: raise AssertionError('Downloads did not open in a new COSMIC Files window')
        xid, props = next(iter(new.items()))
        # Close only the exact new window produced by this test, never an older file-manager window.
        class Message(ctypes.Structure):
            _fields_ = [('type', ctypes.c_int), ('serial', ctypes.c_ulong), ('send_event', ctypes.c_int), ('display', ctypes.c_void_p), ('window', ctypes.c_ulong), ('message_type', ctypes.c_ulong), ('format', ctypes.c_int), ('data', ctypes.c_long * 5)]
        class Event(ctypes.Union): _fields_ = [('client', Message), ('pad', ctypes.c_long * 24)]
        x11 = ctypes.CDLL('libX11.so.6'); x11.XOpenDisplay.restype = ctypes.c_void_p; x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]; x11.XInternAtom.restype = ctypes.c_ulong
        x11.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long, ctypes.POINTER(Event)]
        x11.XFlush.argtypes = [ctypes.c_void_p]; x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        display = x11.XOpenDisplay(None); assert display
        try:
            current = cosmic_windows().get(xid)
            assert current == props, 'Downloads window identity changed before cleanup'
            event = Event(); event.client.type = 33; event.client.display = display; event.client.window = int(xid, 16)
            event.client.message_type = x11.XInternAtom(display, b'WM_PROTOCOLS', 0); event.client.format = 32
            event.client.data[0] = x11.XInternAtom(display, b'WM_DELETE_WINDOW', 0)
            assert x11.XSendEvent(display, int(xid, 16), 0, 0, ctypes.byref(event)); x11.XFlush(display)
        finally: x11.XCloseDisplay(display)
        time.sleep(0.7)
        assert xid not in cosmic_windows(), 'Downloads fixture window survived close request'
        assert all(xid in cosmic_windows() for xid in previous), 'An older file-manager window was closed'
        report = {'passed': ['Downloads opens through identified file manager', 'Trash availability reflects URI handler', 'new Downloads window cleaned without closing older windows'], 'pid': app.get_process_id()}
        print(json.dumps(report, ensure_ascii=False))
        Path('/tmp/deskmorph-desktop-test/system-open-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if args.system_unavailable:
        focus_studio(); click('Tiện ích hệ thống', 'button')
        def system_error_text():
            return ' '.join(Atspi.Text.get_text(n.get_text_iface(), 0, -1) for n, _ in descendants(app) if n.get_text_iface())
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            value = system_error_text()
            if 'Không đọc được UPower' in value and 'Không đọc được NetworkManager' in value and 'GiB (' in value: break
            time.sleep(0.15)
        else: raise AssertionError('Missing services hid errors or broke CPU/RAM popup')
        click('Đóng', 'button'); click('Tìm ứng dụng', 'button')
        assert any(n.get_name() == 'Tìm ứng dụng' and n.get_role_name() == 'entry' for n, _ in descendants(app)), 'System bus error broke launcher'
        focus_studio('DeskMorph Context Menu'); native_keys(chord=[0xff1b]); time.sleep(0.3)
        report = {'passed': ['missing UPower/NetworkManager state', 'CPU/RAM remains available', 'launcher remains available'], 'pid': app.get_process_id()}
        print(json.dumps(report, ensure_ascii=False))
        Path('/tmp/deskmorph-desktop-test/system-unavailable-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if args.system_smoke:
        gi.require_version('Gio', '2.0')
        from gi.repository import Gio, GLib
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        def property_value(name, path, interface, key):
            return bus.call_sync(name, path, 'org.freedesktop.DBus.Properties', 'Get', GLib.Variant('(ss)', (interface, key)), None, Gio.DBusCallFlags.NO_AUTO_START, 2000, None).unpack()[0]
        battery_path = bus.call_sync('org.freedesktop.UPower', '/org/freedesktop/UPower', 'org.freedesktop.UPower', 'GetDisplayDevice', None, None, Gio.DBusCallFlags.NO_AUTO_START, 2000, None).unpack()[0]
        percentage = property_value('org.freedesktop.UPower', battery_path, 'org.freedesktop.UPower.Device', 'Percentage')
        network_type = property_value('org.freedesktop.NetworkManager', '/org/freedesktop/NetworkManager', 'org.freedesktop.NetworkManager', 'PrimaryConnectionType')
        path = Path(TEST_CONFIG) / 'com.ducthanhdev.deskmorph/config.json'
        config = lambda: json.loads(path.read_text())['config']
        original = config()
        focus_studio(); click('Taskbar Studio')
        fields = [('showBattery', 'Hiện pin trên Dock'), ('showNetwork', 'Hiện mạng trên Dock'), ('showSystem', 'Nút tiện ích hệ thống')]
        def wait_system(predicate, message):
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                if predicate(): return
                time.sleep(0.15)
            raise AssertionError(message)
        def all_text():
            return ' '.join(Atspi.Text.get_text(n.get_text_iface(), 0, -1) for n, _ in descendants(app) if n.get_text_iface())
        try:
            for field, label in fields:
                if not config()[field]: click(label)
            wait_system(lambda: any(n.get_role_name() == 'button' and n.get_name().startswith('Pin ') and n.get_name().endswith('%') for n, _ in descendants(app)), 'Native battery widget missing')
            names = [n.get_name() for n, _ in descendants(app) if n.get_role_name() == 'button' and n.get_name().startswith('Pin ') and n.get_name().endswith('%')]
            actual = int(re.search(r'(\d+)%', names[0]).group(1))
            assert abs(actual - percentage) <= 1, 'Battery widget differs from UPower aggregate'
            click('Tiện ích hệ thống', 'button')
            wait_system(lambda: 'GiB (' in all_text() and 'CPU:' in all_text(), 'System popup did not show real CPU/RAM with units')
            assert '2 giây' in all_text(), 'CPU/RAM refresh interval missing'
            if network_type == '802-11-wireless': assert 'Wi-Fi' in all_text(), 'Network kind differs from NetworkManager'
            assert 'không bảo đảm mọi dịch vụ Internet' in all_text(), 'Network local/probe distinction missing'
            monitor = next(n for n, _ in descendants(app) if n.get_name() == 'Mở giám sát hệ thống' and n.get_role_name() == 'button')
            available = any(a.get_id() in ['org.gnome.SystemMonitor.desktop', 'gnome-system-monitor.desktop', 'org.gnome.Usage.desktop', 'org.kde.plasma-systemmonitor.desktop', 'plasma-systemmonitor.desktop', 'ksysguard.desktop'] and a.should_show() for a in Gio.AppInfo.get_all())
            assert monitor.get_state_set().contains(Atspi.StateType.ENABLED) == available, 'Monitor capability UI differs from installed apps'
            click('Đóng', 'button')
        finally:
            focus_studio(); click('Taskbar Studio')
            for field, label in fields:
                if config()[field] != original[field]: click(label)
            assert all(config()[field] == original[field] for field, _ in fields), 'System widget preferences were not restored'
        report = {'passed': ['battery widget matches UPower aggregate', 'widget preferences persist and restore', 'CPU/RAM popup values units and interval', 'network kind matches NetworkManager with probe explanation', 'system monitor availability matches installed apps'], 'pid': app.get_process_id()}
        print(json.dumps(report, ensure_ascii=False))
        Path('/tmp/deskmorph-desktop-test/system-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if args.audio_unavailable:
        focus_studio()
        click('Âm thanh', 'button')
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if any(n.get_role_name() in ('alert', 'notification') or n.get_attributes().get('xml-roles') == 'alert' for n, _ in descendants(app)): break
            time.sleep(0.2)
        else: raise AssertionError('Missing audio service did not produce an accessible error')
        if args.audio_tool_missing:
            assert any(n.get_text_iface() and 'audio_tool_missing' in Atspi.Text.get_text(n.get_text_iface(), 0, -1) for n, _ in descendants(app)), 'Missing pactl did not expose a distinct error code'
        assert any(n.get_name() == 'Thử lại' for n, _ in descendants(app)), 'No retry action for missing audio service'
        click('Đóng', 'button')
        click('Tìm ứng dụng', 'button')
        assert any(n.get_name() == 'Tìm ứng dụng' and n.get_role_name() == 'entry' for n, _ in descendants(app)), 'Audio error broke launcher'
        focus_studio('DeskMorph Context Menu'); native_keys(chord=[0xff1b]); time.sleep(0.4)
        report = {'passed': ['missing audio service error and retry', 'launcher remains usable'], 'pid': app.get_process_id()}
        print(json.dumps(report, ensure_ascii=False))
        Path('/tmp/deskmorph-desktop-test/' + ('audio-tool-missing-result.json' if args.audio_tool_missing else 'audio-unavailable-result.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if args.media_smoke:
        root = Path('/tmp/deskmorph-desktop-test')
        fixtures = []
        gi.require_version('GdkPixbuf', '2.0')
        from gi.repository import GdkPixbuf
        artwork_path = root / 'media-cover.png'
        cover = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 32, 16)
        cover.fill(0x48b9c7ff); cover.savev(str(artwork_path), 'png', [], [])
        def wait_media(predicate, message):
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if predicate(): return
                time.sleep(0.15)
            media = next((n for n, _ in descendants(app) if n.get_role_name() == 'landmark' and n.get_name() == 'Media'), None)
            details = []
            if media:
                for n, _ in descendants(media):
                    interface = n.get_text_iface()
                    if interface: details.append(Atspi.Text.get_text(interface, 0, -1))
            raise AssertionError(message + ': ' + json.dumps(details, ensure_ascii=False))
        def has_text(value):
            for node, _ in descendants(app):
                text = node.get_text_iface()
                if text and value in Atspi.Text.get_text(text, 0, -1): return True
            return False
        def calls(log): return log.read_text().splitlines() if log.exists() else []
        try:
            for suffix in ('A', 'B'):
                log = root / f'mpris-{os.getpid()}-{suffix}.jsonl'
                name = f'org.mpris.MediaPlayer2.deskmorph_test_{os.getpid()}_{suffix}'
                process = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('mpris_fixture.py')), '--name', name, '--identity', 'DeskMorph_Player_' + suffix, '--log', str(log), '--artwork', artwork_path.as_uri() if suffix == 'B' else 'https://example.invalid/artwork.png', *(['--can-next'] if suffix == 'A' else [])], stdin=subprocess.PIPE, text=True)
                fixtures.append((process, log))
                wait_media(lambda: Path(str(log) + '.ready').exists(), 'MPRIS fixture failed to register')
            focus_studio()
            click('Âm thanh', 'button')
            wait_media(lambda: any(n.get_name() == 'DeskMorph_Player_B' and n.get_role_name() == 'radio button' for n, _ in descendants(app)), 'Two-player discovery failed')
            click('DeskMorph_Player_B', 'radio button')
            wait_media(lambda: has_text('DeskMorph_Player_B Track'), 'Selected player metadata missing')
            wait_media(lambda: any(n.get_name() == 'Ảnh bìa' and n.get_role_name() == 'image' for n, _ in descendants(app)), 'Local artwork was not rendered')
            next_button = next(n for n, _ in descendants(app) if n.get_name() == 'Bài tiếp' and n.get_role_name() == 'button')
            assert not next_button.get_state_set().contains(Atspi.StateType.ENABLED), 'Unsupported next action was enabled'
            before_a = calls(fixtures[0][1])
            click('Tạm dừng')
            wait_media(lambda: any('Pause' in row for row in calls(fixtures[1][1])), 'Pause did not reach selected player')
            assert calls(fixtures[0][1]) == before_a, 'Command reached unselected fixture'
            wait_media(lambda: has_text('Đã tạm dừng'), 'Playback state signal did not update UI')
            click('Phát')
            wait_media(lambda: any('Play' in row for row in calls(fixtures[1][1])), 'Play did not reach selected player')
            click('Bài trước')
            wait_media(lambda: any('Previous' in row for row in calls(fixtures[1][1])), 'Previous did not reach selected player')
            click('DeskMorph_Player_A', 'radio button')
            click('Bài tiếp')
            wait_media(lambda: any('Next' in row for row in calls(fixtures[0][1])), 'Supported next action did not reach player A')
            assert not any('Next' in row for row in calls(fixtures[1][1])), 'Next reached unselected player B'
            click('DeskMorph_Player_B', 'radio button')
            process = fixtures[1][0]
            process.stdin.write(json.dumps({'title': 'Updated Fixture Title'}) + '\n'); process.stdin.flush()
            wait_media(lambda: has_text('Updated Fixture Title'), 'Metadata signal did not update UI')
            process.terminate(); process.wait(timeout=5)
            wait_media(lambda: not any(n.get_name() == 'DeskMorph_Player_B' and n.get_role_name() == 'radio button' for n, _ in descendants(app)), 'Exited player stayed in chooser')
            wait_media(lambda: has_text('DeskMorph_Player_A Track'), 'Remaining player was not available after exit')
            wait_media(lambda: has_text('Ảnh bìa không khả dụng'), 'Unsupported remote artwork lacked fallback')
            focus_studio('DeskMorph Context Menu'); native_keys(chord=[0xff1b]); time.sleep(0.4)
        finally:
            for process, _ in fixtures:
                if process.poll() is None: process.terminate()
                process.wait(timeout=5)
        report = {'passed': ['two MPRIS fixture players discovered', 'explicit player selection and metadata', 'unsupported capability disabled', 'play/pause/previous/next target selected unique owner only', 'playback and metadata signals', 'local artwork and remote fallback', 'player exit refresh and fallback'], 'pid': app.get_process_id(), 'fixturesRemoved': True}
        print(json.dumps(report, ensure_ascii=False))
        (root / 'media-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if args.audio_smoke:
        def pactl(*args):
            return subprocess.check_output(['pactl', *args], text=True, timeout=6).strip()
        def audio_info(): return json.loads(pactl('--format=json', 'info'))
        def sinks(): return json.loads(pactl('--format=json', 'list', 'sinks'))
        original_default = audio_info()['default_sink_name']
        sink_name = 'deskmorph_test_' + str(os.getpid())
        module = pactl('load-module', 'module-null-sink', 'sink_name=' + sink_name, 'sink_properties=device.description=DeskMorph_Test_Output')
        passed = []
        def wait_audio(predicate, message):
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                if predicate(): return
                time.sleep(0.15)
            node = slider()
            details = {'sliderValue': slider_value(), 'focused': bool(node and node.get_state_set().contains(Atspi.StateType.FOCUSED)), 'showing': bool(node and node.get_state_set().contains(Atspi.StateType.SHOWING)), 'fixtureVolume': [c['value'] for c in fixture_sink()['volume'].values()], 'fixtureIsDefault': audio_info()['default_sink_name'] == sink_name}
            if node:
                rect = node.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
                details['sliderRect'] = [rect.x, rect.y, rect.width, rect.height]
            raise AssertionError(message + ': ' + json.dumps(details))
        def fixture_sink(): return next(s for s in sinks() if s['name'] == sink_name)
        def slider(): return next((n for n, _ in descendants(app) if n.get_name() == 'Âm lượng' and n.get_role_name() == 'slider'), None)
        def slider_value():
            node = slider()
            return node.get_value_iface().get_current_value() if node else None
        def popup_text():
            values = []
            for node, _ in descendants(app):
                text = node.get_text_iface()
                if text: values.append(Atspi.Text.get_text(text, 0, -1))
            return ' '.join(values)
        try:
            pactl('set-sink-volume', sink_name, '37%')
            focus_studio()
            click('Âm thanh', 'button')
            wait_audio(lambda: any(n.get_name() == 'DeskMorph_Test_Output' and n.get_role_name() == 'radio button' for n, _ in descendants(app)), 'Virtual output choice missing')
            click('DeskMorph_Test_Output', 'radio button')
            wait_audio(lambda: audio_info()['default_sink_name'] == sink_name, 'UI failed to select virtual output')
            # Session audio policy may restore the sink volume when it becomes
            # default. Compare with the server, not its pre-selection value.
            def server_volume():
                values = [channel['value'] for channel in fixture_sink()['volume'].values()]
                return round(sum(values) / len(values) / 65536 * 100)
            wait_audio(lambda: slider_value() == server_volume(), 'UI failed to read selected virtual sink volume')
            passed.append('output selection through native UI')
            pactl('set-sink-volume', sink_name, '62%')
            wait_audio(lambda: slider_value() == 62, 'External volume did not update popup')
            passed.append('subscription reflects external volume')
            def subscriptions():
                children = set()
                for entry in Path(f'/proc/{app.get_process_id()}/task').glob('*/children'):
                    try: children.update(entry.read_text().split())
                    except OSError: pass
                result = []
                for child in children:
                    try:
                        argv = Path(f'/proc/{child}/cmdline').read_bytes().split(b'\0')
                        if argv[:2] == [b'pactl', b'subscribe']: result.append(int(child))
                    except OSError: pass
                return result
            wait_audio(lambda: len(subscriptions()) == 1, 'Expected one subscription while popup visible')
            old_subscription = subscriptions()[0]
            os.kill(old_subscription, signal.SIGTERM)
            wait_audio(lambda: len(subscriptions()) == 1 and subscriptions()[0] != old_subscription, 'Subscription did not reconnect after owned pactl exited')
            pactl('set-sink-volume', sink_name, '61%')
            wait_audio(lambda: slider_value() == 61, 'Reconnected subscription did not deliver events')
            passed.append('one audio subscription and reconnect after child exit')
            focus_studio('DeskMorph Context Menu')
            native_click_node(slider())
            native_keys(chord=[0xff50])
            wait_audio(lambda: all(c['value'] == 0 for c in fixture_sink()['volume'].values()), 'Slider did not set volume to zero')
            passed.append('keyboard slider writes system volume')
            click('Tắt tiếng')
            wait_audio(lambda: fixture_sink()['mute'], 'Mute checkbox did not mute virtual output')
            pactl('set-sink-mute', sink_name, '0')
            wait_audio(lambda: not next(n for n, _ in descendants(app) if n.get_name() == 'Tắt tiếng' and n.get_role_name() == 'check box').get_state_set().contains(Atspi.StateType.CHECKED), 'External unmute did not update UI')
            passed.append('mute and external unmute synchronization')
            pactl('set-sink-volume', sink_name, '120%')
            wait_audio(lambda: '120%' in popup_text(), 'Existing amplified volume was clamped or hidden')
            assert all(c['value'] > 65536 for c in fixture_sink()['volume'].values())
            passed.append('existing amplification preserved until adjustment')
            focus_studio('DeskMorph Context Menu')
            native_click_node(slider())
            native_keys(chord=[0xff51])
            wait_audio(lambda: all(c['value'] < 65536 for c in fixture_sink()['volume'].values()), 'Slider adjustment did not leave amplification')
            native_keys(chord=[0xff57])
            wait_audio(lambda: all(c['value'] == 65536 for c in fixture_sink()['volume'].values()), 'Slider did not enforce 100 percent upper limit')
            passed.append('slider caps adjustments at 100 percent')
            pactl('unload-module', module); module = None
            wait_audio(lambda: 'DeskMorph_Test_Output' not in [n.get_name() for n, _ in descendants(app) if n.get_role_name() == 'radio button'], 'Removed output stayed in popup')
            passed.append('output removal refreshes choices')
            focus_studio('DeskMorph Context Menu'); native_keys(chord=[0xff1b]); time.sleep(0.5)
            wait_audio(lambda: len(subscriptions()) == 0, 'Audio subscription survived hidden popup')
            passed.append('hidden popup stops subscription')
            for _ in range(3):
                click('Âm thanh', 'button')
                wait_audio(lambda: len(subscriptions()) == 1, 'Repeated popup did not own exactly one subscription')
                click('Đóng', 'button')
                wait_audio(lambda: len(subscriptions()) == 0, 'Repeated popup leaked subscription')
            passed.append('repeated popup open/close without duplicate subscriptions')
        finally:
            pactl('set-default-sink', original_default)
            if module is not None: pactl('unload-module', module)
            assert audio_info()['default_sink_name'] == original_default, 'Original default output was not restored'
        report = {'passed': passed, 'pid': app.get_process_id(), 'audioFixtureRemoved': True, 'defaultOutputRestored': True}
        print(json.dumps(report, ensure_ascii=False))
        Path('/tmp/deskmorph-desktop-test/audio-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if args.audio_exit:
        focus_studio()
        click('Âm thanh', 'button')
        old_pid = app.get_process_id()
        def owned_subscriptions():
            result = set()
            for entry in Path(f'/proc/{old_pid}/task').glob('*/children'):
                try: children = entry.read_text().split()
                except OSError: continue
                for child in children:
                    try:
                        if Path(f'/proc/{child}/cmdline').read_bytes().split(b'\0')[:2] == [b'pactl', b'subscribe']: result.add(int(child))
                    except OSError: pass
            return result
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            children = owned_subscriptions()
            if len(children) == 1: break
            time.sleep(0.1)
        else: raise AssertionError('Audio exit test did not start a subscription')
        click('Hệ thống')
        click('Thoát DeskMorph')
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            alive = []
            for pid in children:
                try:
                    if Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')[:2] == [b'pactl', b'subscribe']: alive.append(pid)
                except OSError: pass
            if not alive: break
            time.sleep(0.1)
        else: raise AssertionError('Audio child survived normal app exit')
        test_root = Path('/tmp/deskmorph-desktop-test')
        env = dict(os.environ, DESKMORPH_CONFIG_HOME=TEST_CONFIG, XDG_DATA_HOME=str(test_root / 'data'), XDG_CACHE_HOME=str(test_root / 'cache'), WEBKIT_DISABLE_DMABUF_RENDERER='1')
        binary = Path(__file__).resolve().parents[1] / 'src-tauri/target/agent/debug/deskmorph'
        with (test_root / 'runtime.log').open('a') as log:
            process = subprocess.Popen([str(binary)], env=env, stdout=log, stderr=log, start_new_session=True)
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            time.sleep(0.2)
            try:
                app = test_app()
                if app.get_process_id() != old_pid and any(n.get_role_name() == 'button' for n, _ in descendants(app)): break
            except RuntimeError: pass
        else: raise AssertionError('Fresh app did not become accessible after exit')
        assert process.poll() is None, 'Relaunched app exited unexpectedly'
        report = {'passed': ['normal exit cleans owned audio subscription', 'relaunch after exit'], 'previousPid': old_pid, 'pid': app.get_process_id()}
        print(json.dumps(report, ensure_ascii=False))
        Path('/tmp/deskmorph-desktop-test/audio-exit-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if args.library_stress:
        gi.require_version('GdkPixbuf', '2.0')
        from gi.repository import GdkPixbuf
        root = Path('/tmp/deskmorph-desktop-test/stress-library')
        root.mkdir(parents=True, exist_ok=True)
        seed = root.parent / 'stress-seed.png'
        pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 32, 16)
        pixbuf.fill(0x48b9c7ff); pixbuf.savev(str(seed), 'png', [], [])
        for index in range(5001):
            target = root / f'stress-{index:05d}.png'
            if not target.exists(): target.hardlink_to(seed)
        path = Path(TEST_CONFIG) / 'com.ducthanhdev.deskmorph/config.json'
        config = lambda: json.loads(path.read_text())['config']
        original = config()
        assert not original['wallpaperScheduleEnabled'], 'Stress test requires disabled isolated scheduler'
        click('Hình nền')
        def rendered(): return {n.get_name() for n, _ in descendants(app) if n.get_name().startswith('Áp dụng stress-')}
        def wait_rows():
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                rows = rendered()
                if len(rows) == 24: return rows
                time.sleep(0.2)
            raise AssertionError('Large library did not render a bounded page')
        try:
            for folder in original['wallpaperFolders']: click('Xóa ' + folder)
            type_entry('Thư mục ảnh', str(root))
            started = time.monotonic(); click('Thêm thư mục')
            first = wait_rows(); elapsed = time.monotonic() - started
            click('Trang sau'); second = wait_rows()
            assert first.isdisjoint(second), 'Pagination did not change the rendered image set'
            assert len(rendered()) == 24, 'Gallery rendered more than one page'
            def limited_notice():
                for node, _ in descendants(app):
                    text = node.get_text_iface()
                    if text and 'Đã tới giới hạn quét' in Atspi.Text.get_text(text, 0, -1): return True
                return False
            assert limited_notice(), 'Native scan did not expose the 5,000-image limit'
            click('Trang trước'); assert wait_rows() == first, 'Previous page did not restore the same images'
            report = {'passed': ['5,001-file native library scan', '5,000-image limit is visible', '24-image render bound', 'next and previous pagination'],
                      'firstPageSeconds': round(elapsed, 3), 'pid': app.get_process_id()}
            print(json.dumps(report, ensure_ascii=False))
            Path('/tmp/deskmorph-desktop-test/library-stress-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        finally:
            if str(root) in config()['wallpaperFolders']: click('Xóa ' + str(root))
            for folder in original['wallpaperFolders']:
                type_entry('Thư mục ảnh', folder); click('Thêm thư mục')
            assert config()['wallpaperFolders'] == original['wallpaperFolders']
    if args.wallpaper_smoke:
        gi.require_version('GdkPixbuf', '2.0')
        from gi.repository import GdkPixbuf
        root = Path('/tmp/deskmorph-desktop-test/wallpapers')
        (root / 'nested').mkdir(parents=True, exist_ok=True)
        for image, color in ((root / 'one image.png', 0x48b9c7ff), (root / 'nested/two.png', 0x8b5cf6ff)):
            pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 640, 360)
            pixbuf.fill(color)
            pixbuf.savev(str(image), 'png', [], [])
        (root / 'broken.png').write_text('not an image')
        if not (root / 'nested/loop').exists(): (root / 'nested/loop').symlink_to(root, target_is_directory=True)
        path = Path(TEST_CONFIG) / 'com.ducthanhdev.deskmorph/config.json'
        config = lambda: json.loads(path.read_text())['config']
        original = config()
        def has(name): return any(n.get_name() == name for n, _ in descendants(app))
        def wait(predicate, message):
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                if predicate(): return
                time.sleep(0.2)
            raise AssertionError(message)
        # Preserve both GNOME color-scheme wallpaper values exactly after the test.
        previous = {key: subprocess.check_output(['gsettings', 'get', 'org.gnome.desktop.background', key], text=True).strip() for key in ('picture-uri', 'picture-uri-dark')}
        favorite_added = False
        click('Hình nền')
        try:
            for folder in original['wallpaperFolders']: click('Xóa ' + folder)
            type_entry('Thư mục ảnh', str(root))
            click('Thêm thư mục')
            wait(lambda: has('Áp dụng one image.png'), 'Fixture wallpaper was not scanned')
            assert config()['wallpaperFolders'] == [str(root)], 'Wallpaper folder was not persisted'
            if not config()['wallpaperRecursive']:
                click('Quét cả thư mục con Không đi theo symlink thư mục. Mỗi lượt giới hạn 20.000 mục và 5.000 ảnh.')
            wait(lambda: has('Áp dụng two.png'), 'Recursive scan missed nested image')
            assert not has('Áp dụng broken.png'), 'Corrupt image was offered as a wallpaper'
            cache = Path('/tmp/deskmorph-desktop-test/cache/com.ducthanhdev.deskmorph/wallpaper-thumbnails-v1')
            wait(lambda: cache.exists() and len(list(cache.glob('*.png'))) >= 2, 'Background thumbnails were not cached')
            # Verify actual asset rendering, not just the existence of a cache
            # file or an accessible button whose image may have failed CSP.
            gi.require_version('Gdk', '3.0')
            from gi.repository import Gdk
            focus_studio()
            card = next(n for n, _ in descendants(app) if n.get_name() == 'Áp dụng two.png')
            require_unlocked_desktop()
            assert card.get_component_iface().grab_focus(), 'Cannot scroll fixture thumbnail into view'
            colored_pixels = 0
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                require_unlocked_desktop()
                target = card.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
                frame = next(n for n, _ in descendants(app) if n.get_name() == 'DeskMorph Studio' and n.get_role_name() == 'frame').get_component_iface().get_extents(Atspi.CoordType.SCREEN)
                x, y = max(target.x, frame.x), max(target.y, frame.y)
                width = min(target.x + target.width, frame.x + frame.width) - x
                height = min(target.y + target.height, frame.y + frame.height) - y
                if width > 0 and height > 0:
                    rendered = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), x, y, width, height)
                    if rendered:
                        pixels, channels, stride = rendered.get_pixels(), rendered.get_n_channels(), rendered.get_rowstride()
                        colored_pixels = sum(1 for row in range(height) for column in range(width) if all(abs(pixels[row * stride + column * channels + c] - expected) <= 3 for c, expected in enumerate((139, 92, 246))))
                        if colored_pixels > 500:
                            rendered.savev('/tmp/deskmorph-desktop-test/thumbnail-render.png', 'png', [], [])
                            break
                time.sleep(0.2)
            assert colored_pixels > 500, 'Cached thumbnail did not render its fixture pixels through asset/CSP policy'
            if str(root / 'one image.png') not in config()['wallpaperFavorites']:
                click('Yêu thích one image.png'); favorite_added = True
            assert str(root / 'one image.png') in config()['wallpaperFavorites'], 'Favorite was not persisted'
            click('Chỉ ảnh yêu thích')
            wait(lambda: not has('Áp dụng two.png'), 'Favorite filter did not hide other image')
            click('Chỉ ảnh yêu thích')
            type_entry('Tìm hình nền', 'two')
            wait(lambda: has('Áp dụng two.png') and not has('Áp dụng one image.png'), 'Filename search failed')
            type_entry('Tìm hình nền', '')
            click('Áp dụng one image.png')
            expected = (root / 'one image.png').as_uri()
            for key in previous:
                assert subprocess.check_output(['gsettings', 'get', 'org.gnome.desktop.background', key], text=True).strip().strip("'") == expected, 'GNOME did not retain escaped wallpaper URI'
            click('Đổi ngẫu nhiên')
            for key in previous:
                def selected_other():
                    value = subprocess.check_output(['gsettings', 'get', 'org.gnome.desktop.background', key], text=True).strip().strip("'")
                    return value == (root / 'nested/two.png').as_uri()
                wait(selected_other, 'Shuffle did not apply the other image: ' + key)
            # Repeat in the same process so a stale GSettings cache cannot pass
            # merely because a random choice happened to select the other image.
            for relative in ('one image.png', 'nested/two.png'):
                click('Đổi ngẫu nhiên')
                for key in previous:
                    wait(lambda: subprocess.check_output(['gsettings', 'get', 'org.gnome.desktop.background', key], text=True).strip().strip("'") == (root / relative).as_uri(), 'Repeated shuffle used a stale current image')
            # Change settings outside DeskMorph and observe its normal polling,
            # without refreshing the page or invoking a DeskMorph apply command.
            def wallpaper_texts():
                for node, _ in descendants(app):
                    try: yield Atspi.Text.get_text(node, 0, -1)
                    except Exception: pass
            for relative in ('one image.png', 'nested/two.png'):
                external = root / relative
                for key in previous:
                    subprocess.run(['gsettings', 'set', 'org.gnome.desktop.background', key, external.as_uri()], check=True)
                wait(lambda: any('Hình nền hiện tại:' in text and str(external) in text for text in wallpaper_texts()),
                     'External wallpaper change was not reflected by normal polling')
            if args.scheduler_smoke:
                assert not original['wallpaperScheduleEnabled'], 'Scheduler test requires an initially disabled isolated scheduler'
                assert config()['keepDockOnClose'], 'Scheduler test requires keep-Dock lifecycle option'
                click('1 phút')
                def toggle_schedule():
                    checkbox = next(n for n, _ in descendants(app) if n.get_role_name() == 'check box' and n.get_name().startswith('Đổi hình nền tự động'))
                    require_unlocked_desktop()
                    assert checkbox.get_action_iface().do_action(0)
                    time.sleep(0.7)
                toggle_schedule()
                assert config()['wallpaperScheduleEnabled'], 'Scheduler toggle was not persisted'
                started = time.monotonic()
                click('Hệ thống'); click('Hình nền')
                close_studio_native()
                print('Scheduler test: isolated Studio is closed; waiting for the 1-minute native deadline', flush=True)
                deadline = time.monotonic() + 75
                while time.monotonic() < deadline:
                    value = subprocess.check_output(['gsettings', 'get', 'org.gnome.desktop.background', 'picture-uri'], text=True).strip().strip("'")
                    if value == (root / 'one image.png').as_uri(): break
                    time.sleep(1)
                else: raise AssertionError('Scheduler did not run while Studio was closed')
                assert time.monotonic() - started >= 54, 'Scheduler fired immediately or duplicated a previous timer'
                reopen_studio()
                assert test_app().get_process_id() == app.get_process_id(), 'Reopening Studio created another instance'
                toggle_schedule()
                assert not config()['wallpaperScheduleEnabled'], 'Scheduler did not disable'
                value = subprocess.check_output(['gsettings', 'get', 'org.gnome.desktop.background', 'picture-uri'], text=True).strip()
                time.sleep(3)
                assert subprocess.check_output(['gsettings', 'get', 'org.gnome.desktop.background', 'picture-uri'], text=True).strip() == value, 'Scheduler changed wallpaper after disable'
                print('Scheduler test: background deadline, Studio reopen, and disable passed', flush=True)
                if args.scheduler_recovery_smoke:
                    from desktop_scheduler_recovery import run_scheduler_recovery
                    run_scheduler_recovery(app, root, config, toggle_schedule, descendants,
                                           require_unlocked_desktop)
            click('Xóa ' + str(root))
            assert str(root / 'one image.png') in config()['wallpaperFavorites'], 'Removing a folder lost its favorites'
            report = {'passed': ['saved library folder', 'bounded recursive scan and corrupt-image filtering', 'background thumbnail cache', 'rendered thumbnail pixels through production asset/CSP policy',
                                 'favorite persistence and filter', 'filename search', 'GNOME applies escaped URI in both color schemes',
                                 'shuffle excludes current image', 'two external GNOME changes reflected by normal polling',
                                 'favorites survive removed folder'], 'pid': app.get_process_id()}
            if args.scheduler_smoke: report['passed'].extend(['one native deadline while Studio closed', 'second launch reopens the same instance', 'scheduler disable stops changes'])
        finally:
            if args.scheduler_smoke:
                if not any('DeskMorph Studio' in subprocess.run(['xprop', '-id', xid, '_NET_WM_NAME'], capture_output=True, text=True).stdout for xid in re.findall(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True))):
                    reopen_studio()
                if config().get('wallpaperScheduleEnabled'):
                    checkbox = next(n for n, _ in descendants(app) if n.get_role_name() == 'check box' and n.get_name().startswith('Đổi hình nền tự động'))
                    require_unlocked_desktop()
                    assert checkbox.get_action_iface().do_action(0)
                    time.sleep(0.7)
                click(str(original['wallpaperIntervalMinutes']) + ' phút')
            for key, value in previous.items(): subprocess.run(['gsettings', 'set', 'org.gnome.desktop.background', key, value], check=True)
            # Restore library settings through the UI; never edit a live config file directly.
            type_entry('Tìm hình nền', '')
            if str(root) not in config()['wallpaperFolders']:
                type_entry('Thư mục ảnh', str(root)); click('Thêm thư mục')
                wait(lambda: has('Yêu thích one image.png'), 'Cannot restore favorite after test')
            if favorite_added and str(root / 'one image.png') not in original['wallpaperFavorites']:
                click('Yêu thích one image.png')
            if config()['wallpaperRecursive'] != original['wallpaperRecursive']:
                click('Quét cả thư mục con Không đi theo symlink thư mục. Mỗi lượt giới hạn 20.000 mục và 5.000 ảnh.')
            click('Xóa ' + str(root))
            for folder in original['wallpaperFolders']:
                type_entry('Thư mục ảnh', folder); click('Thêm thư mục')
            assert all(config()[key] == original[key] for key in ('wallpaperFolders', 'wallpaperFavorites', 'wallpaperRecursive')), 'Wallpaper test did not restore library settings'
        print(json.dumps(report, ensure_ascii=False))
        Path('/tmp/deskmorph-desktop-test/wallpaper-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if args.launcher_smoke:
        def wait_until(predicate, message, timeout=10):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if predicate(): return
                time.sleep(0.2)
            raise AssertionError(message)
        def find(name, role=None):
            return [n for n, _ in descendants(app) if n.get_name() == name and (role is None or n.get_role_name() == role)]
        focus_studio()
        click('Tìm ứng dụng')
        entry = find('Tìm ứng dụng', 'entry')
        assert len(entry) == 1, 'Search field not accessible'
        # AT-SPI EditableText can alter WebKit's DOM value without dispatching
        # React's input event. Always type through the guarded native helper.
        focus_studio('DeskMorph Context Menu')
        assert entry[0].get_component_iface().grab_focus(), 'Cannot focus the native search field'
        native_keys(value='deskmorph smoke')
        assert Atspi.Text.get_text(entry[0].get_text_iface(), 0, -1) == 'deskmorph smoke'
        wait_until(lambda: bool(find('Mở DeskMorph Smoke Fixture')), 'Fixture not found in installed apps')
        path = Path(TEST_CONFIG) / 'com.ducthanhdev.deskmorph/config.json'
        snapshot = json.loads(path.read_text())
        was_pinned = any(p.get('desktopId') == 'deskmorph-smoke-fixture.desktop' for p in snapshot['config']['pinnedApps'])
        if was_pinned:
            click('Bỏ ghim DeskMorph Smoke Fixture')
        click('Ghim DeskMorph Smoke Fixture')
        assert any(p.get('desktopId') == 'deskmorph-smoke-fixture.desktop' for p in json.loads(path.read_text())['config']['pinnedApps'])
        click('Mở DeskMorph Smoke Fixture')
        group = 'DeskMorph Smoke Fixture • 2 cửa sổ'
        wait_until(lambda: bool(find(group)), 'Launched fixture windows not grouped on Dock')
        click(group)
        wait_until(lambda: bool(find('Đóng DeskMorph Smoke 1')), 'Grouped window popup did not list fixture')
        click('Đóng DeskMorph Smoke 1')
        fixture = None
        root = Atspi.get_desktop(0)
        for i in range(root.get_child_count()):
            candidate = root.get_child_at_index(i)
            try:
                command = Path(f'/proc/{candidate.get_process_id()}/cmdline').read_bytes().split(b'\0')
                if b'--fixture' in command and str(Path(__file__).resolve()).encode() in command:
                    fixture = candidate
                    break
            except OSError:
                continue
        assert fixture, 'Fixture process missing'
        try:
            wait_until(lambda: any(n.get_name() == 'DeskMorph Smoke Confirm' for n, _ in descendants(fixture)), 'Close confirmation did not appear')
            assert any(n.get_name() == 'DeskMorph Smoke 1' for n, _ in descendants(fixture)), 'Window disappeared before close confirmation'
            def cancel_button():
                return next((n for n, _ in descendants(fixture) if n.get_name() == 'Hủy' and n.get_action_iface()), None)
            wait_until(lambda: cancel_button() is not None, 'Close-confirmation cancel button is not ready')
            require_unlocked_desktop()
            assert cancel_button().get_action_iface().do_action(0)
            time.sleep(0.3)
            report = {'passed': ['installed desktop entry discovery', 'search UI', 'pin persistence by desktop ID', 'GIO native launch',
                                 'grouped native windows', 'window list popup', 'close confirmation preserves window'], 'fixturePid': fixture.get_process_id()}
            print(json.dumps(report, ensure_ascii=False))
            Path('/tmp/deskmorph-desktop-test/launcher-result.json').write_text(json.dumps(report, indent=2))
        finally:
            os.kill(fixture.get_process_id(), signal.SIGTERM)
    if args.force_close_smoke:
        require_unlocked_desktop()
        def managed_windows():
            return set(re.findall(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True)))
        before = managed_windows()
        protected = set()
        for xid in before:
            properties = subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID', 'WM_CLASS'], text=True)
            pid = re.search(r'_NET_WM_PID.*= (\d+)', properties)
            # Our own popup is expected to hide, and the preceding launcher
            # fixture may still be completing its requested termination.
            if (not pid or int(pid.group(1)) != app.get_process_id()) and 'DeskMorphSmokeFixture' not in properties:
                protected.add(xid)
        sentinel = subprocess.Popen(['/bin/sleep', '120'])
        root = Path('/tmp/deskmorph-desktop-test')
        with (root / 'force-close-fixture.log').open('a') as log:
            fixture = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).resolve()), '--fixture'], stdout=log, stderr=log)
        try:
            fixture_windows = {}
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                fixture_windows = {}
                for xid in managed_windows() - before:
                    properties = subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID', '_NET_WM_NAME', 'WM_CLASS'], text=True)
                    pid = re.search(r'_NET_WM_PID.*= (\d+)', properties)
                    if pid and int(pid.group(1)) == fixture.pid and 'DeskMorphSmokeFixture' in properties:
                        fixture_windows[xid] = properties
                if len(fixture_windows) == 2: break
                time.sleep(0.1)
            assert len(fixture_windows) == 2 and fixture.poll() is None, 'Owned force-close fixture did not create exactly two windows'
            # Spoof only our owned GTK fixture's advisory PID. A regression to
            # kill(_NET_WM_PID) would terminate this separate owned sentinel.
            for xid in fixture_windows:
                subprocess.run(['xprop', '-id', xid, '-f', '_NET_WM_PID', '32c', '-set', '_NET_WM_PID', str(sentinel.pid)], check=True, capture_output=True)
                assert str(sentinel.pid) in subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID'], text=True)
            focus_studio()
            deadline = time.monotonic() + 10
            group = None
            while time.monotonic() < deadline:
                group = next((n for n, _ in descendants(app) if n.get_name() == 'DeskMorph Smoke Fixture • 2 cửa sổ' and n.get_role_name() == 'button'), None)
                if group: break
                time.sleep(0.1)
            assert group, 'Force-close fixture is not the Dock target'
            native_click_node(group, button=3)
            assert any(n.get_name() == 'DeskMorph Smoke 1' for n, _ in descendants(app)), 'Context menu does not belong to fixture'
            click('Buộc dừng…'); click('Hủy')
            assert fixture.poll() is None and sentinel.poll() is None, 'Cancel force-close changed an owned process'
            click('Buộc dừng…'); click('Xác nhận buộc dừng')
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline and (fixture.poll() is None or set(fixture_windows) & managed_windows()): time.sleep(0.1)
            assert fixture.poll() is not None, 'Force-close did not disconnect the owned X client'
            assert not set(fixture_windows) & managed_windows(), 'An owned fixture X resource survived force-close'
            assert sentinel.poll() is None, 'Force-close trusted spoofed _NET_WM_PID and killed an unrelated process'
            assert protected <= managed_windows(), 'A pre-existing external window disappeared during the fixture test'
            report = {'passed': ['force-close requires confirmation', 'cancel preserves both owned processes', 'force-close disconnects exact fixture X client and both client windows', 'spoofed PID does not kill the separate sentinel', 'pre-existing managed windows remain'], 'pid': app.get_process_id(), 'fixturePid': fixture.pid, 'sentinelPid': sentinel.pid}
            (root / 'force-close-result.json').write_text(json.dumps(report, indent=2))
            print(json.dumps(report))
        finally:
            for process in (fixture, sentinel):
                if process.poll() is None: process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
    if args.screenshot:
        require_unlocked_desktop()
        gi.require_version('Gdk', '3.0')
        gi.require_version('GdkX11', '3.0')
        from gi.repository import Gdk, GdkX11
        frame = next(n for n, _ in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Studio')
        root_properties = subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True)
        for xid in re.findall(r'0x[0-9a-fA-F]+', root_properties):
            properties = subprocess.run(['xprop', '-id', xid, '_NET_WM_PID', '_NET_WM_NAME'], capture_output=True, text=True).stdout
            pid = re.search(r'_NET_WM_PID.*= (\d+)', properties)
            if pid and int(pid.group(1)) == app.get_process_id() and 'DeskMorph Studio' in properties:
                window = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(), int(xid, 16))
                window.raise_()
                window.focus(Gdk.CURRENT_TIME)
                Gdk.flush()
                time.sleep(0.4)
                break
        else:
            raise RuntimeError('Cannot locate the isolated Studio X11 window')
        rect = frame.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        pixbuf = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), rect.x, rect.y, rect.width, rect.height)
        pixbuf.savev(args.screenshot, 'png', [], [])
    if not args.performance_smoke or args.inspect: inspect(app)
