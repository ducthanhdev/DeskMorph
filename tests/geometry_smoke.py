"""Measure owned native Dock/popup rectangles against each current X11 work area."""
import json
import os
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
    expected_scale = float(os.environ.get('DESKMORPH_EXPECT_SCALE', '1'))
    monitors = []
    topology = subprocess.check_output(['xrandr', '--query'], text=True)
    for match in re.finditer(r'^(\S+) connected (?:primary )?(\d+)x(\d+)([+-]\d+)([+-]\d+)', topology, re.M):
        name, width, height, x, y = match.groups()
        x, y, width, height = map(int, (x, y, width, height))
        monitor = display.get_monitor_at_point(round((x + width / 2) / expected_scale), round((y + height / 2) / expected_scale))
        assert monitor and monitor.get_scale_factor() == expected_scale, f'Expected GTK scale {expected_scale}; mixed-DPI remains a separate gate'
        area = monitor.get_workarea()
        monitors.append((name, [round(area.x * expected_scale), round(area.y * expected_scale), round(area.width * expected_scale), round(area.height * expected_scale)]))
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
        native_keys(chord=[0xffe3, ord('l')]); native_keys(value=str(file)); click('Open', 'button')
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
    # GTK reports logical dimensions while xwininfo reports physical pixels.
    # All CSS geometry constants therefore need the active scale applied.
    margin = round(16 * expected_scale)
    popup_margin = round(10 * expected_scale)
    popup_gap = round(14 * expected_scale)
    dock_height = round(52 * expected_scale)
    popup_sizes = {
        'Tìm ứng dụng': [round(500 * expected_scale), round(580 * expected_scale)],
        'Âm thanh': [round(360 * expected_scale), round(540 * expected_scale)],
        'Tiện ích hệ thống': [round(380 * expected_scale), round(620 * expected_scale)],
        'Mở lịch': [round(320 * expected_scale), round(340 * expected_scale)],
    }
    fixture_pins = [dict(id=f'geometry-fixture-{index}', name=f'Geometry Fixture {index}', command='/bin/true',
        matchClasses=[f'DeskMorphGeometry{index}'], iconType='custom', enabled=True) for index in range(40)]

    def output_cycle(output):
        # Explicitly opt in: this changes the real desktop output topology.
        physical = os.environ.get('DESKMORPH_GEOMETRY_PHYSICAL_HOTPLUG') == '1'
        assert expected_scale == 1 and len(monitors) == 2
        areas = dict(monitors)
        assert output in areas
        remaining = next(name for name in areas if name != output)
        restore = ['xrandr']
        for name in areas:
            line = next(line for line in topology.splitlines() if line.startswith(name + ' connected '))
            match = re.search(r'(\d+x\d+)([+-]\d+)([+-]\d+) \(normal ', line)
            assert match, 'Output cycle supports unrotated outputs only'
            mode, x, y = match.groups()
            restore += ['--output', name, '--mode', mode, '--pos', f'{int(x)}x{int(y)}', '--rotate', 'normal']
            if ' connected primary ' in line: restore += ['--primary']
            section = topology.split(line, 1)[1].split('\n', 1)[1]
            section = re.split(r'\n\S', section, maxsplit=1)[0]
            current = re.search(r'^\s+' + re.escape(mode) + r'\s+.*?([\d.]+)\*', section, re.M)
            assert current, 'Cannot preserve active output refresh rate'
            restore += ['--rate', current.group(1)]

        def active_outputs():
            query = subprocess.check_output(['xrandr', '--query'], text=True, timeout=8)
            return re.findall(r'^(\S+) connected (?:primary )?\d+x\d+[+-]\d+[+-]\d+', query, re.M)

        def cable_state(connected, stage):
            (root / 'physical-hotplug-stage.json').write_text(json.dumps(dict(stage=stage, output=output)))
            print(f'PHYSICAL_HOTPLUG {stage}: {output}', flush=True)
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                query = subprocess.check_output(['xrandr', '--query'], text=True, timeout=8)
                state = re.search(r'^' + re.escape(output) + r' (connected|disconnected)\b', query, re.M)
                if state and (state.group(1) == 'connected') == connected:
                    return query
                time.sleep(1)
            raise AssertionError('Timed out waiting for physical cable ' + stage)

        def dock_on(area, position):
            rect = native_rect('DeskMorph Taskbar')
            if not rect: return None
            ax, ay, aw, ah = area
            y = ay + 16 if position == 'top' else ay + ah - 68
            return rect if rect[1] == y and rect[3] == 52 and ax <= rect[0] and rect[0] + rect[2] <= ax + aw and abs(rect[0] + rect[2] / 2 - ax - aw / 2) <= .5 else None

        def calendar(area, position):
            focus_studio('DeskMorph Taskbar')
            source = wait(lambda: node('Mở lịch', 'button'), 'Calendar source missing after output change')
            assert source.get_component_iface().grab_focus()
            wait(lambda: source.get_state_set().contains(Atspi.StateType.FOCUSED), 'Calendar source not focused')
            native_keys(chord=[0xff0d])
            def settled_calendar():
                rect = native_rect('DeskMorph Calendar')
                dock = dock_on(area, position)
                if not rect or not dock: return None
                ax, ay, aw, ah = area
                y = dock[1] + dock[3] + 14 if position == 'top' else dock[1] - 354
                y = max(ay + 10, min(y, ay + ah - 350))
                return rect if rect[2:] == [320, 340] and rect[1] == y and ax <= rect[0] and rect[0] + rect[2] <= ax + aw else None
            try:
                rect = wait(settled_calendar, 'Calendar did not settle on the current output after topology change')
            except AssertionError as error:
                raise AssertionError(f'{error}; area={area}; dock={native_rect("DeskMorph Taskbar")}; calendar={native_rect("DeskMorph Calendar")}') from error
            inside(area, rect)
            return rect

        result = dict(pid=app.get_process_id(), output=output, remaining=remaining, cycles=[],
            scope='Physical connector state change reported by XRandR' if physical else 'Real XRandR output off/on; cable remains connected, not physical unplug evidence')
        try:
            for position in (('bottom',) if physical else ('top', 'bottom')):
                desired = dict(original, language='vi', enabled=True, autoHide=False, monitor=output, position=position, height=52)
                import_config(desired, 'output-cycle')
                wait(lambda: dock_on(areas[output], position), 'Dock not on preferred output before cycle')
                for index in range(1 if physical else 3):
                    calendar(areas[output], position)
                    started = time.monotonic()
                    if physical:
                        result['disconnectedTopology'] = cable_state(False, 'unplug')
                        started = time.monotonic()
                    else:
                        subprocess.run(['xrandr', '--output', output, '--off'], check=True, timeout=10)
                    wait(lambda: active_outputs() == [remaining], 'Output remained active after off')
                    fallback = wait(lambda: dock_on(areas[remaining], position), 'Dock did not fall back to remaining output')
                    wait(lambda: native_rect('DeskMorph Calendar') is None, 'Old calendar survived topology removal')
                    fallback_seconds = round(time.monotonic() - started, 3)
                    popup = calendar(areas[remaining], position)
                    started = time.monotonic()
                    if physical:
                        result['reconnectedTopology'] = cable_state(True, 'replug')
                        started = time.monotonic()
                    subprocess.run(restore, check=True, timeout=10)
                    wait(lambda: set(active_outputs()) == set(areas), 'Outputs not restored')
                    returned = wait(lambda: dock_on(areas[output], position), 'Dock did not return to preferred output')
                    wait(lambda: native_rect('DeskMorph Calendar') is None, 'Fallback calendar survived output restoration')
                    assert config() == desired, 'Fallback overwrote monitor preference or other configuration'
                    result['cycles'].append(dict(position=position, index=index, fallbackDock=fallback, fallbackPopup=popup,
                        returnedDock=returned, fallbackSeconds=fallback_seconds, returnSeconds=round(time.monotonic() - started, 3)))
                    print(json.dumps(result['cycles'][-1]), flush=True)
        finally:
            subprocess.run(restore, check=True, timeout=10)
            wait(lambda: set(active_outputs()) == set(areas), 'Final output restoration failed')
        result['outputsRestored'] = True
        result['passed'] = True
        (root / ('physical-hotplug-result.json' if physical else 'output-cycle-result.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')

    try:
        if output := os.environ.get('DESKMORPH_GEOMETRY_OUTPUT_CYCLE'):
            output_cycle(output)
            return
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
                    expected_y = ay + margin if position == 'top' else ay + ah - dock_height - margin
                    width_ready = dock[2] == aw - 2 * margin if position == 'bottom' else dock[2] <= aw - 2 * margin
                    return dock if width_ready and dock[1] == expected_y and dock[3] == dock_height and abs(dock[0] + dock[2] / 2 - (ax + aw / 2)) <= .5 else None
                try:
                    dock = wait(dock_settled, f'Dock did not settle on {name}/{position}')
                except AssertionError as error:
                    raise AssertionError(f'{error}; area={area}; actual={native_rect("DeskMorph Taskbar")}') from error
                inside(area, dock)
                for button, title in [('Tìm ứng dụng', 'DeskMorph Context Menu'),
                        ('Âm thanh', 'DeskMorph Context Menu'),
                        ('Tiện ích hệ thống', 'DeskMorph Context Menu'),
                        ('Mở lịch', 'DeskMorph Calendar')]:
                    size = [min(popup_sizes[button][0], aw - 2 * popup_margin),
                            min(popup_sizes[button][1], ah - 2 * popup_margin)]
                    focus_studio('DeskMorph Taskbar')
                    source = wait(lambda: node(button, 'button'), 'Missing Dock source')
                    assert source.get_component_iface().grab_focus()
                    bounds = source.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
                    anchor = (bounds.x + bounds.width / 2) * expected_scale
                    native_keys(chord=[0xff0d])
                    popup = wait(lambda: native_rect(title), 'Popup did not map')
                    inside(area, popup)
                    assert popup[2:] == size, (button, popup, size)
                    expected_x = max(ax + popup_margin, min(round(anchor) - popup[2] // 2, ax + aw - popup[2] - popup_margin))
                    wanted_y = dock[1] + dock[3] + popup_gap if position == 'top' else dock[1] - popup[3] - popup_gap
                    expected_y = max(ay + popup_margin, min(wanted_y, ay + ah - popup[3] - popup_margin))
                    assert abs(popup[0] - expected_x) <= 1 and popup[1] == expected_y, (button, popup, expected_x, expected_y)
                    if position == 'bottom' and button == 'Tìm ứng dụng': assert popup[0] == ax + popup_margin, 'Left-edge clamp was not exercised'
                    if position == 'bottom' and button == 'Mở lịch': assert popup[0] + popup[2] == ax + aw - popup_margin, 'Right-edge clamp was not exercised'
                    observations.append(dict(monitor=name, workArea=area, position=position, dock=dock, mode=button, anchorX=anchor, popup=popup))
                    print(f'{name}/{position}/{button}: Dock={dock}, popup={popup}', flush=True)
                    native_keys(chord=[0xff1b])
                    wait(lambda: native_rect(title) is None, 'Popup did not hide after geometry measurement')
        report = dict(pid=app.get_process_id(), scale=expected_scale, monitors=[n for n, _ in monitors], observations=observations)
        (root / 'geometry-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(report, ensure_ascii=False), flush=True)
    finally:
        if config() != original: import_config(original, 'restore')
        assert config() == original
