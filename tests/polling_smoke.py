"""Native command counts across real Dock/Studio/popup visibility transitions."""
from collections import Counter
import ctypes
import json
from pathlib import Path
import time
from gi.repository import Atspi
from dock_layout_smoke import descendants


def run(app, config_home, click, focus_studio, native_keys, native_click_node, require_unlocked, assert_pointer_owned, close_studio, reopen_studio):
    root = Path('/tmp/deskmorph-desktop-test')
    path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    config = lambda: json.loads(path.read_text())['config']
    original = config()
    observations = []
    auto_label = 'Tự động ẩn Dock Chạm cạnh màn hình để hiện lại; Dock giữ hiện khi bạn thao tác popup.'

    def wait(predicate, message):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(.1)
        raise AssertionError(message)

    def node(name, role=None):
        return next((n for n in descendants(app) if n.get_name() == name and (role is None or n.get_role_name() == role)), None)

    def dock_rect(): return node('DeskMorph Taskbar', 'frame').get_component_iface().get_extents(Atspi.CoordType.SCREEN)

    def import_config(value, label):
        if config() == value: return
        file = root / f'polling-{label}.json'
        file.write_text(json.dumps({'schemaVersion': 1, 'config': value}))
        focus_studio(); click('Hệ thống'); click('Nhập cấu hình'); focus_studio('Select File')
        native_keys(chord=[0xffe3, ord('l')]); native_keys(value=str(file)); native_keys(chord=[0xff0d])
        time.sleep(.8); click('Áp dụng cấu hình đã nhập')
        wait(lambda: config() == value, 'Polling import failed')

    def move_to(target):
        require_unlocked(); native_keys()
        rect = target.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        assert rect.width > 0 and rect.height > 0 and target in list(descendants(app)), 'Motion target must belong to the verified test accessibility tree'
        x11 = ctypes.CDLL('libX11.so.6'); xtst = ctypes.CDLL('libXtst.so.6')
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XFlush.argtypes = [ctypes.c_void_p]; x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
        display = x11.XOpenDisplay(None); assert display
        try:
            require_unlocked()
            assert xtst.XTestFakeMotionEvent(display, -1, rect.x + rect.width // 2, rect.y + rect.height // 2, 0)
            x11.XFlush(display)
        finally: x11.XCloseDisplay(display)

    def sample(label, duration=4.7):
        begin = time.time() * 1000
        time.sleep(duration)
        end = time.time() * 1000
        events = []
        for line in (root / 'runtime.log').read_text().splitlines():
            if not line.startswith('deskmorph_command '): continue
            event = json.loads(line.removeprefix('deskmorph_command '))
            if event['pid'] == app.get_process_id() and begin <= event['atUnixMs'] < end: events.append(event)
        counts = Counter(e['command'] for e in events if e['phase'] == 'start')
        assert events, 'Debug command tracing did not record native activity'
        record = dict(phase=label, seconds=duration, counts=dict(counts))
        observations.append(record); print(json.dumps(record), flush=True)
        return counts

    def visible_counts(counts):
        assert 2 <= counts['get_open_windows'] <= 4, 'Window poll is missing or duplicated'
        assert 2 <= counts['get_system_stats'] <= 3, 'Dock stats poll is missing or duplicated'
        assert counts['sample_system_stats'] <= 3, 'Shared native sampler computed too often'

    try:
        initial = dict(original, language='vi', enabled=True, autoHide=False, showApps=True, showStats=True, showSystem=True,
                       showClock=True, clockSeconds=True, showBattery=False, showNetwork=False, keepDockOnClose=True, wallpaperScheduleEnabled=False)
        import_config(initial, 'initial')
        focus_studio(); click('Ứng dụng')  # Unmount preview; isolate Dock's consumers.
        time.sleep(.5); visible_counts(sample('Dock visible, Studio apps tab'))
        click('Taskbar Studio'); click('Ứng dụng trên Dock'); click('Ứng dụng')
        time.sleep(.5); counts = sample('App list widget disabled')
        assert counts['get_open_windows'] == 0 and counts['get_system_stats'] >= 2
        click('Taskbar Studio'); click('Ứng dụng trên Dock'); click(auto_label); click('Ứng dụng')
        focus_studio(); move_to(node('DeskMorph', 'heading'))
        wait(lambda: dock_rect().height <= 4, 'Dock did not auto-hide')
        time.sleep(.6); counts = sample('Dock auto-hidden, pointer trigger remains live')
        assert counts['get_open_windows'] == counts['get_system_stats'] == counts['sample_system_stats'] == 0
        assert counts['is_pointer_over_dock'] >= 10, 'Auto-hide trigger polling stopped'
        move_to(node('DeskMorph Taskbar', 'frame'))
        wait(lambda: dock_rect().height > 4, 'Pointer trigger failed to reveal Dock after UI polls stopped')
        time.sleep(.35); move_to(node('DeskMorph Taskbar', 'frame')); assert_pointer_owned()
        time.sleep(.6); visible_counts(sample('Edge reveal resumes one Dock poll loop'))
        # Keep one system popup open. Dock and popup share the 2-second native sampler.
        click('Tiện ích hệ thống', role='button'); focus_studio('DeskMorph Context Menu')
        time.sleep(.6); counts = sample('System popup plus Dock')
        assert 4 <= counts['get_system_stats'] <= 6 and counts['sample_system_stats'] <= 3
        native_keys(chord=[0xff1b]); focus_studio()
        # Disable auto-hide, then repeatedly mount and hide system popup consumers.
        click('Taskbar Studio'); click(auto_label); click('Ứng dụng')
        for _ in range(4):
            click('Tiện ích hệ thống', role='button'); focus_studio('DeskMorph Context Menu'); native_keys(chord=[0xff1b])
        focus_studio(); time.sleep(.6); counts = sample('Four closed system popups leave no polling consumers')
        visible_counts(counts); assert counts['get_system_status'] == 0
        click('Hình nền'); time.sleep(.6); counts = sample('Studio wallpaper visible')
        assert counts['get_current_wallpaper'] >= 1 and counts['get_wallpaper_schedule_status'] >= 2
        close_studio(); time.sleep(.8); counts = sample('Studio natively hidden, Dock remains visible')
        assert counts['get_current_wallpaper'] == counts['get_wallpaper_schedule_status'] == 0, 'Hidden Studio still polls'
        visible_counts(counts)
        reopen_studio(); focus_studio(); time.sleep(.6); counts = sample('Studio shown again retains one wallpaper poll loop')
        assert 1 <= counts['get_current_wallpaper'] <= 2 and 2 <= counts['get_wallpaper_schedule_status'] <= 3
    finally:
        reopen_studio(); focus_studio(); import_config(original, 'restore')
    report = dict(pid=app.get_process_id(), observations=observations, configRestored=True)
    (root / 'polling-result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
