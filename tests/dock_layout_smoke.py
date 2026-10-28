"""Native geometry and pixel checks; called with the guarded desktop harness."""
import ctypes
import json
from pathlib import Path
import re
import subprocess
import time
import gi

gi.require_version('Atspi', '2.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkX11', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Atspi, Gdk, GdkX11, GdkPixbuf, GLib

def native_pixels(xid, x, y, width, height):
    # Foreign GDK windows retain their old allocation after a native resize.
    # Read current server pixels so a 52 -> 90 resize cannot fabricate black rows.
    class XImage(ctypes.Structure):
        _fields_ = [('width', ctypes.c_int), ('height', ctypes.c_int), ('xoffset', ctypes.c_int), ('format', ctypes.c_int),
                    ('data', ctypes.c_void_p), ('byte_order', ctypes.c_int), ('bitmap_unit', ctypes.c_int), ('bitmap_bit_order', ctypes.c_int),
                    ('bitmap_pad', ctypes.c_int), ('depth', ctypes.c_int), ('bytes_per_line', ctypes.c_int), ('bits_per_pixel', ctypes.c_int),
                    ('red_mask', ctypes.c_ulong), ('green_mask', ctypes.c_ulong), ('blue_mask', ctypes.c_ulong)]
    x11 = ctypes.CDLL('libX11.so.6')
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x11.XGetImage.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_ulong, ctypes.c_int]
    x11.XGetImage.restype = ctypes.POINTER(XImage)
    x11.XDestroyImage.argtypes = [ctypes.POINTER(XImage)]
    display = x11.XOpenDisplay(None); assert display
    try:
        picture = x11.XGetImage(display, int(xid, 16), x, y, width, height, ctypes.c_ulong(-1).value, 2)
        assert picture, 'Cannot read owned native Dock pixels'
        try:
            info = picture.contents
            assert info.bits_per_pixel in (24, 32)
            size = info.bits_per_pixel // 8
            offsets = []
            for mask in (info.red_mask, info.green_mask, info.blue_mask):
                shift = (mask & -mask).bit_length() - 1
                assert shift % 8 == 0 and mask == 255 << shift
                offsets.append(shift // 8 if info.byte_order == 0 else size - 1 - shift // 8)
            return ctypes.string_at(info.data, info.bytes_per_line * height), info.bytes_per_line, size, offsets
        finally: x11.XDestroyImage(picture)
    finally: x11.XCloseDisplay(display)

def save_native(xid, width, height, file):
    data, stride, size, offsets = native_pixels(xid, 0, 0, width, height)
    rgb = bytes(data[y * stride + x * size + offset] for y in range(height) for x in range(width) for offset in offsets)
    picture = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(rgb), GdkPixbuf.Colorspace.RGB, False, 8, width, height, width * 3)
    picture.savev(str(file), 'png', [], [])

def descendants(node):
    yield node
    for index in range(node.get_child_count()):
        child = node.get_child_at_index(index)
        if child: yield from descendants(child)

def run(app, config_home, click, focus_studio, native_keys, native_click_node,
        require_unlocked_desktop, assert_pointer_over_test_app):
    root = Path('/tmp/deskmorph-desktop-test')
    config_file = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    config = lambda: json.loads(config_file.read_text())['config']
    original = config()
    marker = root / 'layout-launched'
    assert not marker.exists(), 'Do not overwrite an existing layout marker'
    assert not any(pin.get('desktopId') == 'deskmorph-layout.desktop' for pin in original['pinnedApps'])
    observations = []
    passed = []
    motion_key = ['org.gnome.desktop.interface', 'enable-animations']
    original_motion = subprocess.check_output(['gsettings', 'get', *motion_key], text=True).strip()
    assert original_motion in ('true', 'false')

    def system_motion(value):
        subprocess.run(['gsettings', 'set', *motion_key, value], check=True)
        assert subprocess.check_output(['gsettings', 'get', *motion_key], text=True).strip() == value
        time.sleep(.8)

    def wait(predicate, message):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(.05)
        raise AssertionError(message)

    def find(role, name):
        return next((node for node in descendants(app) if node.get_role_name() == role and node.get_name() == name), None)

    def rect(node):
        box = node.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        return (box.x, box.y, box.width, box.height)

    def pin(): return find('button', 'DeskMorph Layout Fixture • 0 cửa sổ')

    def import_config(value, label):
        file = root / f'layout-{label}.json'
        file.write_text(json.dumps({'schemaVersion': 1, 'config': value}))
        focus_studio(); click('Hệ thống'); click('Nhập cấu hình'); focus_studio('Select File')
        native_keys(chord=[0xffe3, ord('l')]); native_keys(value=str(file)); native_keys(chord=[0xff0d])
        time.sleep(.8); click('Áp dụng cấu hình đã nhập')
        wait(lambda: config() == value, 'Layout import did not persist reviewed config')

    def move(node):
        native_keys()
        x, y, width, height = rect(node)
        assert width > 0 and height > 0
        x11 = ctypes.CDLL('libX11.so.6'); xtst = ctypes.CDLL('libXtst.so.6')
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
        display = x11.XOpenDisplay(None); assert display
        try:
            require_unlocked_desktop()
            assert xtst.XTestFakeMotionEvent(display, -1, x + width // 2, y + height // 2, 0)
            x11.XSync(display, 0); assert_pointer_over_test_app()
        finally: x11.XCloseDisplay(display)

    def clear_hover():
        focus_studio(); move(find('heading', 'DeskMorph')); time.sleep(.25)

    def set_range(field, label, value, high):
        if config()[field] == value: return
        focus_studio()
        node = find('slider', label)
        assert node and node.get_component_iface().grab_focus()
        native_keys(chord=[0xff57 if high else 0xff50])
        wait(lambda: config()[field] == value, 'Native range key did not save ' + field)

    def dock_geometry():
        output = subprocess.check_output(['xwininfo', '-id', xid], text=True)
        return tuple(int(re.search(re.escape(label) + r':\s*(-?\d+)', output).group(1)) for label in ('Absolute upper-left X', 'Absolute upper-left Y', 'Width', 'Height'))

    def sprite():
        # The fixture is the only magenta square; capture its owned window region.
        dx, dy, width, height = dock_geometry()
        px, _, pw, _ = rect(pin())
        left = max(0, px - dx - pw)
        right = min(width, px - dx + 2 * pw)
        data, stride, channels, (red, green, blue) = native_pixels(xid, left, 0, right - left, height)
        pixels = [(x, y) for y in range(height) for x in range(right - left)
                  if data[y * stride + x * channels + red] > 150 and data[y * stride + x * channels + green] < 90 and data[y * stride + x * channels + blue] > 150]
        assert len(pixels) > 25, 'Fixture icon did not render'
        xs, ys = zip(*pixels)
        return dict(x=min(xs) + left, y=min(ys), width=max(xs) - min(xs) + 1, height=max(ys) - min(ys) + 1, pixels=len(pixels))

    def check_motion(label, moving, bouncing=None):
        if bouncing is None: bouncing = moving
        before = rect(pin()); initial_dock = dock_geometry()
        active = subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)
        baseline = sprite()
        move(pin()); time.sleep(.25)
        after = rect(pin())
        assert after == before, f'Hover changed native accessible hit target: {before} -> {after}'
        magnified = sprite()
        if moving: assert magnified['width'] > baseline['width'], 'Magnification did not enlarge the visual icon'
        else: assert abs(magnified['width'] - baseline['width']) <= 1, 'Reduced/disabled motion still magnifies'
        assert subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True) == active, 'Hover tooltip stole native focus'
        if marker.exists(): marker.unlink()
        native_click_node(pin())
        wait(marker.exists, 'Animation interaction launched wrong app')
        active = subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)
        frames = []
        until = time.monotonic() + 1.1
        while time.monotonic() < until:
            sample = sprite(); frames.append(sample)
            actual = rect(pin())
            assert actual == before, f'Bounce moved the hit target: {before} -> {actual}; Dock {initial_dock} -> {dock_geometry()}'
            assert sample['y'] >= 5 and sample['y'] + sample['height'] <= dock_geometry()[3] - 4, 'Icon animation reached the clipped scroll boundary'
            # A filled square may squash/stretch by a few percent, never lose rows.
            assert .85 <= sample['height'] / sample['width'] <= 1.2, f'Animated square appears cropped: {sample}; Dock={dock_geometry()}; pin={rect(pin())}'
            time.sleep(.035)
        ys = [sample['y'] for sample in frames]
        assert len(frames) >= 6, 'Too few frames to verify motion'
        if bouncing: assert max(ys) - min(ys) >= 2, 'Launch fixture did not animate'
        else: assert max(ys) - min(ys) <= 1, 'Reduced/disabled motion still bounces'
        assert subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True) == active, 'Animation or tooltip stole native focus'
        observations.append(dict(case=label, config={key: config()[key] for key in ('height', 'iconSize', 'iconSpacing', 'reduceMotion')}, hitTarget=before, glyph=baseline, hoverGlyph=magnified, frames=frames))
        print(f'Layout case passed: {label}; {len(frames)} native frames', flush=True)
        time.sleep(1.6)  # Let the launch safety timer finish before the next case.

    fixture = dict(id='deskmorph-layout.desktop', desktopId='deskmorph-layout.desktop', name='DeskMorph Layout Fixture', command='desktop:deskmorph-layout.desktop', matchClasses=['DeskMorphLayout'], iconType='custom', enabled=True)
    try:
        system_motion('true')
        initial = dict(original, position='top', enabled=True, autoHide=False, height=52, iconSize=36, iconSpacing=8,
                       showApps=True, reduceMotion=False, magnification=True, maxMagnificationScale=2,
                       bouncingLaunch=True, dynamicShadow=True, pinnedApps=[fixture] + original['pinnedApps'])
        import_config(initial, 'initial')
        wait(lambda: pin() is not None, 'Layout fixture pin missing')
        clients = re.findall(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True))
        xid = next(xid for xid in clients if re.search(r'_NET_WM_PID.*= ' + str(app.get_process_id()) + r'\b', subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID', '_NET_WM_NAME'], text=True)) and 'DeskMorph Taskbar' in subprocess.check_output(['xprop', '-id', xid, '_NET_WM_NAME'], text=True))
        native = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(), int(xid, 16))
        assert Gdk.Display.get_default().get_monitor_at_window(native).get_scale_factor() == 1
        clear_hover()
        check_motion('default', True)
        for height in (40, 90):
            focus_studio(); click('Taskbar Studio')
            set_range('height', 'Chiều cao Dock', height, height == 90)
            for icon in (24, 56):
                set_range('iconSize', 'Kích thước icon', icon, icon == 56)
                for spacing in (0, 24):
                    set_range('iconSpacing', 'Khoảng cách icon', spacing, spacing == 24)
                    clear_hover()
                    wait(lambda: dock_geometry()[3] == height, 'Native Dock height did not update')
                    before = rect(pin())
                    assert before[3] == height - 10, 'Fixed hit slot did not fit the Dock scroll viewport'
                    expected_glyph = round(min(icon, height - 14) * .68)
                    assert abs(sprite()['width'] - expected_glyph) <= 1, 'Icon size was not independently clamped'
                    dx, dy, dw, dh = dock_geometry()
                    assert dx <= before[0] and before[0] + before[2] <= dx + dw and dy <= before[1] and before[1] + before[3] <= dy + dh
                    for node in descendants(app):
                        if node.get_role_name() == 'image' and node.get_name().startswith(('CPU:', 'RAM:')):
                            wx, wy, ww, wh = rect(node)
                            assert dx <= wx and wx + ww <= dx + dw and dy <= wy and wy + wh <= dy + dh, 'System stat widget is clipped at this Dock height'
                    if original['pinnedApps']:
                        next_pin = next(node for node in descendants(app) if node.get_role_name() == 'button' and node.get_name().startswith(original['pinnedApps'][0]['name'] + ' • '))
                        assert abs(rect(next_pin)[0] - before[0] - before[2] - spacing) <= 1, 'Icon spacing did not match its separate setting'
                    check_motion(f'{height}/{icon}/{spacing}', True)
        passed.append('default and eight extreme size/spacing combinations preserve native hit targets and keep magnified/bouncing icon pixels inside viewport')
        focus_studio(); click('Giao diện'); click('Nảy icon khi mở')
        wait(lambda: not config()['bouncingLaunch'], 'Bounce toggle did not persist')
        clear_hover(); check_motion('bounce disabled', True, False)
        focus_studio(); click('Phóng to khi rê chuột')
        wait(lambda: not config()['magnification'], 'Magnification toggle did not persist')
        clear_hover(); check_motion('both disabled', False)
        focus_studio(); click('Nảy icon khi mở'); click('Phóng to khi rê chuột')
        passed.append('independent bounce and magnification toggles suppress their visual effects without changing hit slots or launch input')
        focus_studio(); click('Giao diện'); click('Giảm hoạt ảnh')
        wait(lambda: config()['reduceMotion'], 'Reduced-motion preference did not persist')
        clear_hover(); check_motion('app reduced motion', False)
        passed.append('app reduced-motion preference disables magnification and bounce while retaining launch input')
        focus_studio(); click('Giảm hoạt ảnh')
        wait(lambda: not config()['reduceMotion'], 'App reduced motion did not turn off')
        system_motion('false')
        clear_hover(); check_motion('GNOME reduced motion', False)
        system_motion('true')
        clear_hover(); check_motion('GNOME motion restored', True)
        passed.append('live GNOME enable-animations changes disable and restore WebKit reduced-motion effects in the same process')
    finally:
        system_motion(original_motion)
        try:
            if 'native' in locals():
                width, height = dock_geometry()[2:]
                save_native(xid, width, height, root / 'layout-last.png')
        finally:
            import_config(original, 'restore')
            assert config() == original, 'Layout test did not restore original configuration'
            marker.unlink(missing_ok=True)
            (root / 'layout-observations.json').write_text(json.dumps(observations, indent=2))
    report = dict(passed=passed, pid=app.get_process_id(), cases=len(observations), preferencesRestored=True)
    (root / 'layout-result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
