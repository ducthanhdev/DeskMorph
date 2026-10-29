"""Real WebView/IPC capability loss/recovery and declared-session UI gates.

The Wayland metadata case still renders with X11; it is not a Wayland runtime test.
Only the isolated DeskMorph profile and private executable directory are changed.
"""
import json
import os
from pathlib import Path
import shutil
import signal
import tempfile
import time
from gi.repository import Atspi
from dock_layout_smoke import descendants


def run(app, config_home, click, focus_studio, native_keys, test_app, start_app, set_app):
    root = Path('/tmp/deskmorph-desktop-test')
    owned = Path(tempfile.mkdtemp(prefix='capabilities-', dir=root))
    binaries = owned / 'bin'
    binaries.mkdir()
    for name in ('xprop', 'xkill', 'pactl'):
        tool = shutil.which(name)
        if tool:
            (binaries / name).symlink_to(tool)
    config_path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = config_path.read_bytes()
    passed, pids = [], []

    def wait(predicate, message):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(.15)
        raise AssertionError(message)

    def stopped(pid):
        try:
            return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z'
        except FileNotFoundError:
            return True

    def stop():
        pid = test_app().get_process_id()
        assert pid == app.get_process_id()
        env = Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
        assert f'DESKMORPH_CONFIG_HOME={config_home}'.encode() in env
        os.kill(pid, signal.SIGTERM)
        wait(lambda: stopped(pid), 'Owned app did not stop')
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass

    def start(overrides=None):
        nonlocal app
        app = start_app(env_overrides=overrides)
        set_app(app)
        pids.append(app.get_process_id())
        focus_studio()

    def names():
        output = []
        for item in descendants(app):
            output.append(item.get_name() or '')
            try:
                output.append(Atspi.Text.get_text(item, 0, -1))
            except Exception:
                pass
        return '\n'.join(output)

    def node(name):
        return next((n for n in descendants(app) if n.get_name() == name), None)

    def enabled(name, value):
        item = node(name)
        return item is not None and item.get_state_set().contains(Atspi.StateType.SENSITIVE) == value

    def open_mapping():
        click('Ứng dụng')
        summary = wait(lambda: next((n for n in descendants(app) if n.get_name().startswith('Ghép lớp cửa sổ ') and n.get_role_name() == 'unknown'), None), 'Mapping summary absent')
        assert summary.get_action_iface().do_action(0)

    def configure(**patch):
        document = json.loads(original)
        document['config'].update(language='vi', enabled=True, **patch)
        config_path.write_text(json.dumps(document))

    try:
        stop()
        configure(autoHide=False)
        start({'PATH': str(binaries)})
        open_mapping()
        wait(lambda: enabled('Đọc lớp cửa sổ đang mở', True), 'Supported class reader unavailable')
        (binaries / 'xprop').unlink()
        click('Hệ thống')
        click('Kiểm tra lại khả năng desktop')
        wait(lambda: 'xprop' in names(), 'Missing xprop reason absent')
        open_mapping()
        wait(lambda: enabled('Đọc lớp cửa sổ đang mở', False), 'Class reader did not revoke capability')
        assert any('Chưa đọc được trạng thái cửa sổ' in (n.get_name() or '') for n in descendants(app)), 'Dock did not revoke running-window count'
        click('Tìm ứng dụng')
        wait(lambda: any(n.get_name() == 'Tìm ứng dụng' and n.get_role_name() == 'entry' for n in descendants(app)), 'Launcher stopped working without enumeration')
        native_keys(chord=[0xff1b])
        focus_studio()
        (binaries / 'xprop').symlink_to(shutil.which('xprop'))
        click('Hệ thống')
        click('Kiểm tra lại khả năng desktop')
        open_mapping()
        wait(lambda: enabled('Đọc lớp cửa sổ đang mở', True), 'Class reader did not recover')
        passed.append('native capability loss/recovery broadcasts to Studio and Dock; launcher remains usable')

        stop()
        configure(autoHide=False)
        start({'XDG_CURRENT_DESKTOP': 'DeskMorphUnsupportedFixture'})
        click('Hình nền')
        wait(lambda: 'GNOME' in names(), 'Specific wallpaper adapter reason absent')
        assert enabled('Đổi hình nền tự động', False) or any(
            n.get_role_name() == 'check box' and n.get_name().startswith('Đổi hình nền tự động') and
            not n.get_state_set().contains(Atspi.StateType.SENSITIVE) for n in descendants(app))
        click('Hệ thống')
        wait(lambda: 'Đang phát triển' in names(), 'Workspace development status absent')
        passed.append('unsupported desktop disables wallpaper actions and explains adapter; workspaces marked in development')

        stop()
        configure(autoHide=True)
        start({'XDG_SESSION_TYPE': 'wayland', 'GDK_BACKEND': 'x11'})
        click('Taskbar Studio')
        wait(lambda: 'Tùy chọn tự ẩn đã lưu đang tạm dừng' in names(), 'Saved auto-hide suspension explanation absent')
        assert enabled('Vị trí', False), 'Position selector enabled in unverified session'
        assert any(n.get_role_name() == 'check box' and n.get_name().startswith('Tự động ẩn') and
                   not n.get_state_set().contains(Atspi.StateType.SENSITIVE) for n in descendants(app))
        time.sleep(1.5)
        dock = node('DeskMorph Taskbar')
        assert dock and dock.get_state_set().contains(Atspi.StateType.SHOWING)
        assert dock.get_component_iface().get_extents(Atspi.CoordType.SCREEN).height >= 40, 'Dock remained collapsed at the edge'
        assert json.loads(config_path.read_text())['config']['autoHide'] is True
        assert any('Chưa đọc được trạng thái cửa sổ' in (n.get_name() or '') for n in descendants(app))
        passed.append('Wayland-declared X11-rendered fixture disables placement/auto-hide and keeps saved auto-hide Dock visible; not native Wayland proof')
    finally:
        stop()
        config_path.write_bytes(original)
        start()
        assert all(stopped(pid) for pid in pids[:-1]), 'Fixture process leaked'
        shutil.rmtree(owned)
    report = {'passed': passed, 'fixturePids': pids[:-1], 'normalPid': pids[-1], 'configRestored': config_path.read_bytes() == original, 'fixturesRemoved': not owned.exists()}
    (root / 'capabilities-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return app
