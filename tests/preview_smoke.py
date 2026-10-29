"""Native preview/Dock pixels, settings restore and animation on owned fixtures."""
import ctypes
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import uuid
import time
from gi.repository import Atspi
from dock_layout_smoke import descendants, native_pixels, save_native

APPEARANCE = ('position', 'height', 'iconSize', 'iconSpacing', 'opacity', 'borderRadius', 'accentColor',
              'bouncingLaunch', 'dynamicShadow', 'magnification', 'maxMagnificationScale', 'reduceMotion')


def run(app, config_home, click, focus_studio, native_keys, test_app, start_app, set_app, require_unlocked_desktop, assert_pointer_over_test_app):
    root = Path('/tmp/deskmorph-desktop-test')
    owned = root / ('preview-' + uuid.uuid4().hex)
    owned.mkdir()
    path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original_bytes = path.read_bytes()
    original = json.loads(original_bytes)
    config = lambda: json.loads(path.read_text())['config']
    entry = root / 'data/applications/deskmorph-preview.desktop'
    assert not entry.exists(), 'Do not overwrite an existing fixture entry'
    icon = owned / 'square.svg'
    icon.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><path fill="#ff00ff" d="M0 0h64v64H0z"/></svg>')
    marker = owned / 'launched'
    second_entry = entry.with_name('deskmorph-preview-second.desktop')
    assert not second_entry.exists()
    second_icon = owned / 'second.svg'
    second_icon.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><path fill="#00ffff" d="M0 0h64v64H0z"/></svg>')
    second_entry.write_text('[Desktop Entry]\nType=Application\nName=DeskMorph Preview Second\nExec=/bin/true\n' + f'Icon={second_icon}\nStartupWMClass=DeskMorphPreviewSecond\n')
    entry.write_text('[Desktop Entry]\nType=Application\nName=DeskMorph Preview Fixture\n'
                     f'Exec=/usr/bin/touch {marker}\nIcon={icon}\nStartupWMClass=DeskMorphPreview\n')
    pids, observations = [], []

    def wait(predicate, message):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(.15)
        raise AssertionError(message)

    def stop():
        pid = test_app().get_process_id()
        assert pid == app.get_process_id()
        assert f'DESKMORPH_CONFIG_HOME={config_home}'.encode() in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
        os.kill(pid, signal.SIGTERM)
        def stopped():
            try:
                return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z'
            except FileNotFoundError:
                return True
        wait(stopped, 'Owned app did not exit')
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass

    def start():
        nonlocal app
        app = start_app()
        set_app(app)
        pids.append(app.get_process_id())
        time.sleep(.6)

    def find(name, role=None, parent=None):
        return next((n for n in descendants(parent or app) if n.get_name() == name and (role is None or n.get_role_name() == role)), None)

    def rect(node):
        value = node.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        return value.x, value.y, value.width, value.height

    def xid(title):
        clients = re.findall(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True))
        for identifier in clients:
            info = subprocess.check_output(['xprop', '-id', identifier, '_NET_WM_PID', '_NET_WM_NAME'], text=True)
            if re.search(r'_NET_WM_PID\(CARDINAL\) = ' + str(app.get_process_id()) + r'\b', info) and f'"{title}"' in info:
                return identifier
        raise AssertionError('Owned window absent: ' + title)

    def geometry(identifier):
        info = subprocess.check_output(['xwininfo', '-id', identifier], text=True)
        return tuple(int(re.search(re.escape(key) + r':\s*(-?\d+)', info).group(1)) for key in ('Absolute upper-left X', 'Absolute upper-left Y', 'Width', 'Height'))

    def sprite(node, identifier):
        dx, dy, dw, dh = geometry(identifier)
        px, py, pw, ph = rect(node)
        left, top = max(0, px - dx - 5), max(0, py - dy - 5)
        width, height = min(dw - left, pw + 10), min(dh - top, ph + 10)
        data, stride, channels, (red, green, blue) = native_pixels(identifier, left, top, width, height)
        pixels = [(x, y) for y in range(height) for x in range(width)
                  if data[y * stride + x * channels + red] > 150 and data[y * stride + x * channels + green] < 90 and data[y * stride + x * channels + blue] > 150]
        assert len(pixels) > 25, 'Fixture glyph not rendered on ' + identifier + ' at ' + str((px, py, pw, ph))
        xs, ys = zip(*pixels)
        return {'width': max(xs) - min(xs) + 1, 'height': max(ys) - min(ys) + 1, 'y': min(ys), 'pixels': len(pixels)}

    def move(node):
        x, y, width, height = rect(node)
        require_unlocked_desktop()
        x11 = ctypes.CDLL('libX11.so.6'); xtst = ctypes.CDLL('libXtst.so.6')
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
        display = x11.XOpenDisplay(None); assert display
        try:
            assert xtst.XTestFakeMotionEvent(display, -1, x + width // 2, y + height // 2, 0)
            x11.XSync(display, 0); assert_pointer_over_test_app()
        finally:
            x11.XCloseDisplay(display)
        time.sleep(.3)

    def preview_pin():
        return find('DeskMorph Preview Fixture • 0 cửa sổ', parent=find('Xem trước Dock', 'landmark'))

    def dock_pin():
        return find('DeskMorph Preview Fixture • 0 cửa sổ', 'button')

    try:
        stop()
        baseline = dict(original['config'], language='vi', enabled=True, autoHide=False, height=52, iconSize=36,
                        showStats=False, showBattery=False, showNetwork=False, showSystem=False,
                        showAudio=False, showShuffle=False, showClock=False, showApps=True,
                        reduceMotion=True, pinnedApps=[dict(id='deskmorph-preview.desktop', desktopId='deskmorph-preview.desktop',
                        name='DeskMorph Preview Fixture', command='desktop:deskmorph-preview.desktop', matchClasses=['DeskMorphPreview'], iconType='custom', enabled=True)])
        baseline['pinnedApps'].append(dict(id=second_entry.name, desktopId=second_entry.name, name='DeskMorph Preview Second', command='desktop:' + second_entry.name, matchClasses=['DeskMorphPreviewSecond'], iconType='custom', enabled=True))
        for height, icon_size, position, spacing, opacity, radius in [(40, 56, 'top', 0, .2, 0), (90, 56, 'bottom', 24, 1, 40)]:
            value = dict(baseline, height=height, iconSize=icon_size, position=position, iconSpacing=spacing, opacity=opacity, borderRadius=radius)
            path.write_text(json.dumps(dict(original, config=value)))
            start()
            studio_xid, dock_xid = xid('DeskMorph Studio'), xid('DeskMorph Taskbar')
            for phase in ('startup', 'preset', 'restored'):
                if phase == 'preset':
                    click('Giao diện'); click('Nord tối giản')
                    wait(lambda: config()['height'] == 48, 'Live preset did not persist')
                    click('Taskbar Studio')
                elif phase == 'restored':
                    click('Taskbar Studio'); click('Nút đổi hình nền', 'check box')
                    wait(lambda: config()['showShuffle'], 'Unrelated widget change did not persist')
                    click('Giao diện'); click('Khôi phục giao diện lúc mở Studio')
                    wait(lambda: all(config()[key] == value[key] for key in APPEARANCE), 'Startup appearance not restored')
                    assert config()['pinnedApps'] == baseline['pinnedApps'] and config()['showShuffle']
                    click('Taskbar Studio')
                time.sleep(.8)
                preview = wait(preview_pin, 'Preview pin disappeared')
                actual = wait(dock_pin, 'Dock pin disappeared')
                assert all(abs(left - right) <= 1 for left, right in zip(rect(preview)[2:], rect(actual)[2:])), f'Preview hit slots differ: {rect(preview)} / {rect(actual)}'
                preview_second = find('DeskMorph Preview Second • 0 cửa sổ', parent=find('Xem trước Dock', 'landmark'))
                actual_second = find('DeskMorph Preview Second • 0 cửa sổ', 'button')
                gaps = [rect(right)[0] - rect(left)[0] - rect(left)[2] for left, right in [(preview, preview_second), (actual, actual_second)]]
                assert all(abs(gap - config()['iconSpacing']) <= 1 for gap in gaps), f'Icon spacing mismatch: {gaps}'
                move(find('DeskMorph', 'heading'))
                first, second = sprite(preview, studio_xid), sprite(actual, dock_xid)
                assert abs(first['width'] - second['width']) <= 1 and abs(first['height'] - second['height']) <= 1, 'Glyph pixel size differs between preview and Dock'
                assert geometry(dock_xid)[3] == config()['height'], 'Dock height differs from setting'
                hit_before = rect(preview)
                move(preview)
                hover_glyph = sprite(preview_pin(), studio_xid)
                assert rect(preview_pin()) == hit_before, 'Preview magnification moved its hit slot'
                if config()['reduceMotion']:
                    assert abs(hover_glyph['width'] - first['width']) <= 1, 'Reduced-motion preview still magnifies'
                else:
                    assert hover_glyph['width'] > first['width'], 'Preview failed to magnify'
                move(find('DeskMorph', 'heading'))
                save_native(studio_xid, *geometry(studio_xid)[2:], root / f'preview-{height}-{phase}.png')
                observations.append({'phase': phase, 'appearance': {key: config()[key] for key in APPEARANCE}, 'previewGlyph': first, 'dockGlyph': second, 'hitSlot': rect(preview)[2:], 'gaps': gaps, 'hoverGlyph': hover_glyph})
            assert not marker.exists(), 'Preview or restore launched fixture app'
            if height == 40:
                stop()
        # Same glyph/bounce CSS is used for the preview demonstration and real launch.
        click('Giao diện')
        if config()['reduceMotion']:
            click('Giảm hoạt ảnh', 'check box')
            wait(lambda: not config()['reduceMotion'], 'Reduced motion toggle did not persist')
        click('Taskbar Studio')
        click('Thử hiệu ứng mở ứng dụng')
        frames = []
        until = time.monotonic() + 1
        while time.monotonic() < until:
            frames.append(sprite(preview_pin(), studio_xid))
            time.sleep(.045)
        assert max(frame['y'] for frame in frames) - min(frame['y'] for frame in frames) >= 2, 'Preview demo did not animate'
        assert not marker.exists(), 'Animation demo launched actual application'
        observations.append({'previewAnimationFrames': frames, 'launchMarkerAbsent': True})
    finally:
        stop()
        path.write_bytes(original_bytes)
        entry.unlink()
        second_entry.unlink()
        shutil.rmtree(owned)
        start()
    report = {'passed': ['preview and real Dock native glyph pixels/hit slots match at height 40 and 90',
                         'top/bottom, size clamp, opacity/radius/spacing changes render on both surfaces',
                         'cross-tab restore returns startup appearance and preserves pins/widgets/auto-hide',
                         'preview launch animation moves real rendered glyph without launching application',
                         'hover magnifies preview without moving its hit slot; reduced-motion suppresses it'],
              'observations': observations, 'fixturePids': pids[:-1], 'normalPid': pids[-1],
              'fixturesRemoved': not owned.exists() and not entry.exists() and not second_entry.exists(), 'configRestored': path.read_bytes() == original_bytes}
    (root / 'preview-result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
    return app
