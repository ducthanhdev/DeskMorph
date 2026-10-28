"""Real-window indicator checks at the supported size limits, using owned fixtures."""
import json
import os
from pathlib import Path
import re
import select
import subprocess
import time
from gi.repository import Atspi
from dock_layout_smoke import descendants, native_pixels, save_native

def run(app, config_home, click, focus_studio, native_keys, owned_input_pids):
    root = Path('/tmp/deskmorph-desktop-test')
    config_file = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    config = lambda: json.loads(config_file.read_text())['config']
    original = config()
    assert not any(pin.get('desktopId') == 'deskmorph-layout.desktop' for pin in original['pinnedApps'])
    fixture = None
    observations = []

    def wait(predicate, message):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(.1)
        raise AssertionError(message)

    def pin(count):
        return next((node for node in descendants(app) if node.get_role_name() == 'button' and node.get_name() == f'DeskMorph Layout Fixture • {count} cửa sổ'), None)

    def import_config(value, label):
        file = root / f'indicator-{label}.json'
        file.write_text(json.dumps({'schemaVersion': 1, 'config': value}))
        focus_studio(); click('Hệ thống'); click('Nhập cấu hình'); focus_studio('Select File')
        native_keys(chord=[0xffe3, ord('l')]); native_keys(value=str(file)); native_keys(chord=[0xff0d])
        time.sleep(.8); click('Áp dụng cấu hình đã nhập')
        wait(lambda: config() == value, 'Indicator import did not persist reviewed configuration')

    def reply():
        assert select.select([fixture.stdout], [], [], 5)[0], 'Fixture did not acknowledge request'
        line = fixture.stdout.readline()
        assert line, 'Fixture exited before replying'
        return json.loads(line)

    def geometry():
        output = subprocess.check_output(['xwininfo', '-id', dock_xid], text=True)
        return tuple(int(re.search(re.escape(label) + r':\s*(-?\d+)', output).group(1)) for label in ('Absolute upper-left X', 'Absolute upper-left Y', 'Width', 'Height'))

    def set_range(field, label, value, high):
        if config()[field] == value: return
        focus_studio()
        slider = next(node for node in descendants(app) if node.get_role_name() == 'slider' and node.get_name() == label)
        assert slider.get_component_iface().grab_focus()
        native_keys(chord=[0xff57 if high else 0xff50])
        wait(lambda: config()[field] == value, 'Range keyboard input did not save ' + field)

    def sample(count, active):
        dx, dy, dw, dh = geometry()
        assert dh == config()['height'], 'Native height differs from persisted setting'
        box = pin(count).get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        assert dx <= box.x and box.x + box.width <= dx + dw and dy <= box.y and box.y + box.height <= dy + dh
        data, stride, size, (red, green, blue) = native_pixels(dock_xid, box.x - dx, box.y - dy, box.width, box.height)
        icon = min(config()['iconSize'], config()['height'] - 14)
        left, top = (box.width - icon) / 2, (box.height - icon) / 2
        badge, dot = [], []
        for y in range(box.height):
            for x in range(box.width):
                offset = y * stride + x * size
                r, g, b = (data[offset + channel] for channel in (red, green, blue))
                if 50 <= r <= 90 and 160 <= g <= 210 and 175 <= b <= 220: badge.append((x, y))
                # The translucent white dot becomes pink over the magenta fixture,
                # and gray over the tile. Match both composites in the bottom band.
                is_dot = (r < 35 and g > 150 and b < 35) if active else ((min(r, g, b) > 65 and max(r, g, b) - min(r, g, b) < 18) or (r > 180 and b > 180 and 40 < g < 130))
                if y >= top + icon - 8 and is_dot: dot.append((x, y))
        def bounds(pixels, name):
            if len(pixels) < (15 if name == 'badge' else 3):
                save_native(dock_xid, dw, dh, root / 'indicator-failure.png')
                rows = []
                for y in range(int(top + icon - 7), min(box.height, int(top + icon))):
                    rows.append([(x, y, tuple(data[y * stride + x * size + channel] for channel in (red, green, blue))) for x in range(max(0, box.width // 2 - 7), min(box.width, box.width // 2 + 7))])
                print('Indicator pixel diagnostic:', rows, flush=True)
            assert len(pixels) >= (15 if name == 'badge' else 3), f'{name} did not render; count={count}, active={active}, pixels={len(pixels)}'
            xs, ys = zip(*pixels)
            assert min(xs) >= left - 1 and max(xs) < left + icon + 1 and min(ys) >= top - 1 and max(ys) < top + icon + 1, name + ' escaped its icon tile'
            return [min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1]
        if count > 1: badge_bounds = bounds(badge, 'badge')
        else: assert not badge, 'Window-count badge remained at zero/one window'; badge_bounds = None
        if count: dot_bounds = bounds(dot, 'dot')
        else: assert not dot, 'Running dot remained at zero windows'; dot_bounds = None
        return dict(count=count, active=active, height=config()['height'], iconSize=config()['iconSize'], position=config()['position'], hitTarget=[box.x, box.y, box.width, box.height], badge=badge_bounds, dot=dot_bounds)

    try:
        test_pin = dict(id='deskmorph-layout.desktop', desktopId='deskmorph-layout.desktop', name='DeskMorph Layout Fixture', command='desktop:deskmorph-layout.desktop', matchClasses=['DeskMorphLayout'], iconType='custom', enabled=True, color='#00ff00')
        initial = dict(original, position='top', enabled=True, autoHide=False, height=40, iconSize=24, iconSpacing=0, showApps=True, pinnedApps=[test_pin] + original['pinnedApps'])
        import_config(initial, 'initial')
        wait(lambda: pin(0) is not None, 'Indicator pin missing')
        clients = re.findall(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True))
        dock_xid = next(xid for xid in clients if re.search(r'_NET_WM_PID.*= ' + str(app.get_process_id()) + r'\b', subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID', '_NET_WM_NAME'], text=True)) and 'DeskMorph Taskbar' in subprocess.check_output(['xprop', '-id', xid, '_NET_WM_NAME'], text=True))
        fixture = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('desktop_smoke.py').resolve()), '--indicator-fixture'], env=dict(os.environ, DESKMORPH_CONFIG_HOME=config_home), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        state = reply()
        assert len(state) == 2 and fixture.poll() is None
        assert b'DESKMORPH_CONFIG_HOME=' + config_home.encode() in Path(f'/proc/{fixture.pid}/environ').read_bytes().split(b'\0')
        owned_input_pids.add(fixture.pid)
        for item in state.values():
            props = subprocess.check_output(['xprop', '-id', item['xid'], '_NET_WM_PID'], text=True)
            assert re.search(r'= ' + str(fixture.pid) + r'\b', props), 'Unexpected fixture XID owner'
        wait(lambda: pin(2) is not None, 'Dock did not reconcile two real fixture windows')
        for position in ('top', 'bottom'):
            focus_studio(); click('Taskbar Studio')
            if config()['position'] != position:
                click('Trên đỉnh màn hình' if position == 'top' else 'Dưới đáy (Đề xuất)')
                native_keys(chord=[0xff1b])
                wait(lambda: config()['position'] == position, 'Position did not persist')
            for height, icon, spacing in ((40, 24, 0), (90, 56, 24)):
                set_range('height', 'Chiều cao Dock', height, height == 90)
                set_range('iconSize', 'Kích thước icon', icon, icon == 56)
                set_range('iconSpacing', 'Khoảng cách icon', spacing, spacing == 24)
                focus_studio(); time.sleep(1.8)
                inactive = sample(2, False)
                focus_studio('DeskMorph Indicator Test 1', fixture.pid)
                time.sleep(1.8)
                active_xid = re.search(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)).group(0)
                assert active_xid == state['1']['xid'], 'Fixture did not receive native focus'
                active = sample(2, True)
                assert active['hitTarget'] == inactive['hitTarget'], 'Active indicator changed the hit bounds'
                observations += [inactive, active]
                save_native(dock_xid, *geometry()[2:], root / f'indicator-{position}-{height}.png')
                print(f'Indicator case passed: {position}/{height}/{icon}, active and inactive', flush=True)
        focus_studio(); click('Taskbar Studio')
        if config()['position'] != 'top':
            click('Trên đỉnh màn hình'); native_keys(chord=[0xff1b])
        set_range('height', 'Chiều cao Dock', 40, False)
        set_range('iconSize', 'Kích thước icon', 24, False)
        for index in range(3, 13):
            fixture.stdin.write(json.dumps(dict(action='add', index=index)) + '\n'); fixture.stdin.flush()
            state = reply(); assert len(state) == index
        wait(lambda: pin(12) is not None, 'Accessible label lost full count of 12 real windows')
        focus_studio(); time.sleep(1.8)
        observations.append(sample(12, False))
        save_native(dock_xid, *geometry()[2:], root / 'indicator-many.png')
        focus_studio('DeskMorph Taskbar')
        assert pin(12).get_component_iface().grab_focus()
        wait(lambda: any(node.get_role_name() == 'tool tip' and 'DeskMorph Layout Fixture' in node.get_name() and '12 cửa sổ' in node.get_name() for node in descendants(app)), 'Tooltip lost the full count behind its compact badge')
        # Move DOM focus off the measured pin before checking badge absence.
        # GTK focus loss alone preserves WebKit's cyan focus-visible outline,
        # which intentionally uses the same color as the badge background.
        native_keys(chord=[0xff09])
        assert not pin(12).get_state_set().contains(Atspi.StateType.FOCUSED)
        focus_studio()
        for item in state.values():
            props = subprocess.check_output(['xprop', '-id', item['xid'], '_NET_WM_PID'], text=True)
            assert re.search(r'= ' + str(fixture.pid) + r'\b', props), 'Many-window fixture XID changed owner'
        for index in range(12, 1, -1):
            fixture.stdin.write(json.dumps(dict(action='close', index=index)) + '\n'); fixture.stdin.flush()
            assert len(reply()) == index - 1
        wait(lambda: pin(1) is not None, 'Dock did not reconcile 12 to one real window')
        time.sleep(.3); observations.append(sample(1, False))
        save_native(dock_xid, *geometry()[2:], root / 'indicator-one-window.png')
        fixture.stdin.write(json.dumps(dict(action='close', index=1)) + '\n'); fixture.stdin.flush()
        assert len(reply()) == 0
        wait(lambda: pin(0) is not None, 'Dock did not reconcile external fixture close')
        time.sleep(.3); observations.append(sample(0, False))
    finally:
        if fixture:
            owned_input_pids.discard(fixture.pid)
            if fixture.poll() is None: fixture.terminate()
            fixture.communicate(timeout=5)
        import_config(original, 'restore')
        assert config() == original, 'Indicator test did not restore original configuration'
        (root / 'indicator-observations.json').write_text(json.dumps(observations, indent=2))
    report = dict(pid=app.get_process_id(), fixturePid=fixture.pid, observations=observations, fullCountAccessible=True, fullCountTooltip=True, preferencesRestored=True)
    (root / 'indicator-result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
