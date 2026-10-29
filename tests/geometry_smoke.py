"""Measure owned native Dock/popup rectangles against each current X11 work area."""
import json
from pathlib import Path
import re
import subprocess
import time
import gi
gi.require_version('Gdk', '3.0')
from gi.repository import Atspi, Gdk, GLib
from dock_layout_smoke import descendants


def run(app, config_home, click, focus_studio, native_keys):
    root = Path('/tmp/deskmorph-desktop-test')
    config_path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    config = lambda: json.loads(config_path.read_text())['config']
    original = config()
    display = Gdk.Display.get_default()
    monitors = []
    topology = subprocess.check_output(['xrandr', '--query'], text=True)
    for match in re.finditer(r'^(\S+) connected (?:primary )?(\d+)x(\d+)([+-]\d+)([+-]\d+)', topology, re.M):
        name, width, height, x, y = match.groups()
        x, y, width, height = map(int, (x, y, width, height))
        monitor = display.get_monitor_at_point(x + width // 2, y + height // 2)
        assert monitor and monitor.get_scale_factor() == 1, 'This native pixel harness verifies reference scale 1 only'
        area = monitor.get_workarea()
        monitors.append((name, [area.x, area.y, area.width, area.height]))
    assert monitors, 'No current X11 output; do not infer geometry success'

    def node(name, role):
        try: return next((n for n in descendants(app) if n.get_name() == name and n.get_role_name() == role), None)
        except GLib.GError: return None

    def wait(predicate, message):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            value = predicate()
            if value: return value
            time.sleep(.1)
        raise AssertionError(message)

    def import_config(value, label):
        file = root / ('geometry-' + label + '.json')
        file.write_text(json.dumps({'schemaVersion': 1, 'config': value}))
        focus_studio(); click('Hệ thống'); click('Nhập cấu hình'); focus_studio('Select File')
        native_keys(chord=[0xffe3, ord('l')]); native_keys(value=str(file)); native_keys(chord=[0xff0d])
        wait(lambda: node('Áp dụng cấu hình đã nhập', 'button'), 'Geometry import review not ready')
        click('Áp dụng cấu hình đã nhập')
        wait(lambda: config() == value, 'Geometry configuration not persisted')

    def native_rect(title):
        clients = subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True)
        for xid in re.findall(r'0x[0-9a-fA-F]+', clients):
            props = subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID', '_NET_WM_NAME'], text=True)
            if not re.search(r'_NET_WM_PID.*= ' + str(app.get_process_id()) + r'\b', props): continue
            if f'= "{title}"' not in props: continue
            info = subprocess.check_output(['xwininfo', '-id', xid], text=True)
            values = [int(re.search(pattern + r':\s+(-?\d+)', info).group(1)) for pattern in ['Absolute upper-left X', 'Absolute upper-left Y', 'Width', 'Height']]
            return values
        return None

    def inside(area, rect):
        x, y, w, h = rect; ax, ay, aw, ah = area
        assert w > 0 and h > 0 and ax <= x and ay <= y and x + w <= ax + aw and y + h <= ay + ah, (area, rect)

    observations = []
    fixture_pins = [dict(id=f'geometry-fixture-{index}', name=f'Geometry Fixture {index}', command='/bin/true',
        matchClasses=[f'DeskMorphGeometry{index}'], iconType='custom', enabled=True) for index in range(40)]
    try:
        for name, area in monitors:
            for position in ['top', 'bottom']:
                desired = dict(original, language='vi', enabled=True, autoHide=False, monitor=name, position=position,
                    height=52, iconSize=36, iconSpacing=8, showApps=True, showAudio=True, showSystem=True, showClock=True,
                    pinnedApps=original['pinnedApps'] + (fixture_pins if position == 'bottom' else []))
                import_config(desired, 'setup')
                ax, ay, aw, ah = area
                def dock_settled():
                    dock = native_rect('DeskMorph Taskbar')
                    if not dock: return None
                    expected_y = ay + 16 if position == 'top' else ay + ah - 52 - 16
                    width_ready = dock[2] >= aw - 40 if position == 'bottom' else dock[2] < aw - 40
                    return dock if width_ready and dock[1] == expected_y and dock[3] == 52 and abs(dock[0] + dock[2] / 2 - (ax + aw / 2)) <= .5 else None
                try:
                    dock = wait(dock_settled, f'Dock did not settle on {name}/{position}')
                except AssertionError as error:
                    raise AssertionError(f'{error}; area={area}; actual={native_rect("DeskMorph Taskbar")}') from error
                inside(area, dock)
                for button, title, size in [('Tìm ứng dụng', 'DeskMorph Context Menu', [500, 580]),
                        ('Âm thanh', 'DeskMorph Context Menu', [360, 540]),
                        ('Tiện ích hệ thống', 'DeskMorph Context Menu', [380, 620]),
                        ('Mở lịch', 'DeskMorph Calendar', [320, 340])]:
                    focus_studio('DeskMorph Taskbar')
                    source = wait(lambda: node(button, 'button'), 'Missing Dock source')
                    assert source.get_component_iface().grab_focus()
                    bounds = source.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
                    anchor = bounds.x + bounds.width / 2
                    native_keys(chord=[0xff0d])
                    popup = wait(lambda: native_rect(title), 'Popup did not map')
                    inside(area, popup)
                    assert popup[2:] == size, (button, popup, size)
                    expected_x = max(ax + 10, min(round(anchor) - popup[2] // 2, ax + aw - popup[2] - 10))
                    wanted_y = dock[1] + dock[3] + 14 if position == 'top' else dock[1] - popup[3] - 14
                    expected_y = max(ay + 10, min(wanted_y, ay + ah - popup[3] - 10))
                    assert abs(popup[0] - expected_x) <= 1 and popup[1] == expected_y, (button, popup, expected_x, expected_y)
                    if position == 'bottom' and button == 'Tìm ứng dụng': assert popup[0] == ax + 10, 'Left-edge clamp was not exercised'
                    if position == 'bottom' and button == 'Mở lịch': assert popup[0] + popup[2] == ax + aw - 10, 'Right-edge clamp was not exercised'
                    observations.append(dict(monitor=name, workArea=area, position=position, dock=dock, mode=button, anchorX=anchor, popup=popup))
                    print(f'{name}/{position}/{button}: Dock={dock}, popup={popup}', flush=True)
                    native_keys(chord=[0xff1b])
                    wait(lambda: native_rect(title) is None, 'Popup did not hide after geometry measurement')
        report = dict(pid=app.get_process_id(), scale=1, monitors=[n for n, _ in monitors], observations=observations)
        (root / 'geometry-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(report, ensure_ascii=False), flush=True)
    finally:
        if config() != original: import_config(original, 'restore')
        assert config() == original
