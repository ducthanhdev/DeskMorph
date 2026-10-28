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
    parser.add_argument('--force-close-smoke', action='store_true')
    parser.add_argument('--popup-smoke', action='store_true')
    parser.add_argument('--autohide-smoke', action='store_true')
    parser.add_argument('--studio-smoke', action='store_true')
    parser.add_argument('--config-smoke', action='store_true')
    parser.add_argument('--wallpaper-smoke', action='store_true')
    parser.add_argument('--scheduler-smoke', action='store_true')
    parser.add_argument('--system-open-smoke', action='store_true')
    parser.add_argument('--system-unavailable', action='store_true')
    parser.add_argument('--system-smoke', action='store_true')
    parser.add_argument('--audio-exit', action='store_true')
    parser.add_argument('--audio-tool-missing', action='store_true')
    parser.add_argument('--audio-unavailable', action='store_true')
    parser.add_argument('--media-smoke', action='store_true')
    parser.add_argument('--audio-smoke', action='store_true')
    parser.add_argument('--library-stress', action='store_true')
    parser.add_argument('--fixture', action='store_true')
    parser.add_argument('--environment', action='store_true')
    parser.add_argument('--platform-tool-missing', action='store_true', help='Read-only startup check with an empty PATH in the isolated app')
    args = parser.parse_args()
    if args.audio_tool_missing: args.audio_unavailable = True
    if args.force_close_smoke: args.launcher_smoke = True
    if args.popup_smoke: args.restart = True
    if args.platform_tool_missing: args.restart = True
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
    input_tests = any((args.action, args.screenshot, args.basic, args.popup_smoke, args.autohide_smoke, args.launcher_smoke, args.studio_smoke, args.config_smoke,
                       args.wallpaper_smoke, args.scheduler_smoke, args.library_stress, args.audio_smoke, args.media_smoke,
                       args.audio_exit, args.audio_unavailable, args.system_smoke, args.system_unavailable, args.system_open_smoke))
    if input_tests: require_unlocked_desktop()
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
        if args.audio_unavailable: env['PULSE_SERVER'] = 'unix:/tmp/deskmorph-nonexistent-audio-service'
        if args.audio_tool_missing or args.platform_tool_missing:
            empty_path = test_root / 'empty-tool-path'
            empty_path.mkdir(exist_ok=True)
            assert not any(empty_path.iterdir()), 'The missing-tool test PATH must stay empty'
            env['PATH'] = str(empty_path)
        if args.system_unavailable: env['DBUS_SYSTEM_BUS_ADDRESS'] = 'unix:path=/tmp/deskmorph-nonexistent-system-bus'
        binary = Path(__file__).resolve().parents[1] / 'src-tauri/target/agent/debug/deskmorph'
        with (test_root / 'runtime.log').open('a') as log:
            process = subprocess.Popen([str(binary)], env=env, stdout=log, stderr=log, start_new_session=True)
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
    if args.platform_tool_missing:
        observed = ''
        for _ in range(50):
            texts = []
            for node, _ in descendants(app):
                texts.append(node.get_name() or '')
                interface = node.get_text_iface()
                if interface: texts.append(Atspi.Text.get_text(interface, 0, -1))
            observed = '\n'.join(texts)
            if 'xprop_unavailable:' in observed: break
            time.sleep(0.1)
        assert 'xprop_unavailable:' in observed, 'Missing xprop capability error did not reach Studio'
        assert any(node.get_name() in ('Tìm ứng dụng', 'Search applications') for node, _ in descendants(app)), 'Dock launcher disappeared when window management was unavailable'
        report = {'passed': ['missing xprop reaches Studio capability status', 'Dock and launcher remain available'], 'pid': app.get_process_id(), 'inputSent': False}
        Path('/tmp/deskmorph-desktop-test/platform-tool-missing-result.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
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
    def focus_studio(title="DeskMorph Studio"):
        require_unlocked_desktop()
        gi.require_version('Gdk', '3.0')
        gi.require_version('GdkX11', '3.0')
        from gi.repository import Gdk, GdkX11
        clients = subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True)
        for xid in re.findall(r'0x[0-9a-fA-F]+', clients):
            properties = subprocess.run(['xprop', '-id', xid, '_NET_WM_PID', '_NET_WM_NAME'], capture_output=True, text=True).stdout
            pid = re.search(r'_NET_WM_PID.*= (\d+)', properties)
            if pid and int(pid.group(1)) == app.get_process_id() and title in properties:
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
        require_unlocked_desktop()
        active = subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)
        xid = re.search(r'0x[0-9a-fA-F]+', active).group(0)
        pid = subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID'], text=True)
        assert int(pid.split('=')[1].strip()) == app.get_process_id(), 'Keyboard focus left isolated test app'
        x11 = ctypes.CDLL('libX11.so.6')
        xtst = ctypes.CDLL('libXtst.so.6')
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        x11.XKeysymToKeycode.restype = ctypes.c_uint
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
                key(0xffe3, 1)
                key(ord('a'), 1); key(ord('a'), 0); key(0xffe3, 0)
                if value == '': key(0xff08, 1); key(0xff08, 0)
                for char in value:
                    assert char in 'abcdefghijklmnopqrstuvwxyz0123456789 -./', 'Test helper accepts lowercase ASCII only'
                    key(ord(char), 1); key(ord(char), 0)
            x11.XFlush(display)
        finally:
            x11.XCloseDisplay(display)
        if chord or value is not None: time.sleep(0.4)
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
    # The dedicated case above exercises auto-hide. Other cases interact with
    # a fully shown Dock; AT-SPI actions on off-screen children are not a real
    # user interaction and can leave the popup unfocused during native resize.
    if any((args.popup_smoke, args.audio_smoke, args.media_smoke, args.launcher_smoke)):
        baseline_path = Path(TEST_CONFIG) / 'com.ducthanhdev.deskmorph/config.json'
        focus_studio()
        click('Taskbar Studio')
        if json.loads(baseline_path.read_text())['config']['autoHide']:
            click('Tự động ẩn Dock Chạm cạnh màn hình để hiện lại; Dock giữ hiện khi bạn thao tác popup.')
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
        assert trash_button.get_state_set().contains(Atspi.StateType.ENABLED) == (Gio.AppInfo.get_default_for_uri_scheme('trash') is not None), 'Trash button does not match desktop capability'
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
            click('Xóa ' + str(root))
            assert str(root / 'one image.png') in config()['wallpaperFavorites'], 'Removing a folder lost its favorites'
            report = {'passed': ['saved library folder', 'bounded recursive scan and corrupt-image filtering', 'background thumbnail cache', 'rendered thumbnail pixels through production asset/CSP policy',
                                 'favorite persistence and filter', 'filename search', 'GNOME applies escaped URI in both color schemes',
                                 'shuffle excludes current image', 'favorites survive removed folder'], 'pid': app.get_process_id()}
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
        editable = entry[0].get_editable_text_iface()
        if editable:
            editable.set_text_contents('deskmorph smoke')
        else:
            assert entry[0].get_component_iface().grab_focus(), 'Cannot focus the native search field'
            time.sleep(0.3)
            active_info = subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)
            active_xid = re.search(r'0x[0-9a-fA-F]+', active_info).group(0)
            active_pid = subprocess.check_output(['xprop', '-id', active_xid, '_NET_WM_PID'], text=True)
            assert int(active_pid.split('=')[1].strip()) == app.get_process_id(), 'Keyboard focus left isolated test app'
            x11 = ctypes.CDLL('libX11.so.6')
            xtst = ctypes.CDLL('libXtst.so.6')
            x11.XOpenDisplay.restype = ctypes.c_void_p
            x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
            x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            x11.XKeysymToKeycode.restype = ctypes.c_uint
            x11.XFlush.argtypes = [ctypes.c_void_p]
            x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
            xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
            display = x11.XOpenDisplay(None)
            assert display, 'Cannot connect to X11 for native keyboard test'
            try:
                for char in 'deskmorph smoke':
                    code = x11.XKeysymToKeycode(display, ord(char))
                    assert code, f'No key mapping for {char}'
                    xtst.XTestFakeKeyEvent(display, code, 1, 0)
                    xtst.XTestFakeKeyEvent(display, code, 0, 0)
                x11.XFlush(display)
            finally:
                x11.XCloseDisplay(display)
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
    inspect(app)
