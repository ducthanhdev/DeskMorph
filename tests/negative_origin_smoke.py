#!/usr/bin/python3
"""Opt-in native allocation audit on owned Xvfb/RandR monitors.

No host display input or topology mutation; Escape targets the owned X server. Negative RandR monitors extend
outside Xvfb's drawable root: this measures native allocations and AT-SPI
activation, not visible pixels, real mouse/keyboard, WM or mixed DPI behavior.
DESKMORPH_STUDIO_WIDGETS_LAB=1 instead checks native Studio controls on the
positive monitor with rendered-pixel contrast and private-display keys.
DESKMORPH_CONTEXT_SPEECH_LAB=1 checks the real launch error with private Orca/SD
and an owned host null sink; it sends no host display input.
DESKMORPH_STUDIO_FOCUS_LAB=1 audits five Studio pages using private Tab/ShiftTab,
control/window bounds, focus pixels and select contrast at integer scales 1/2.
DESKMORPH_DPI_SOURCE_LAB=launcher/audio/system/calendar exercises the host DPI
worker against positive private monitors before any host display trial.
DESKMORPH_AUDIO_CONTROLS_LAB=1 checks private audio keys/readback and pixels.
DESKMORPH_PRIVATE_GNOME_WM=1 with DPI_SOURCE_LAB uses one drawable1920x1080
monitor and a guarded private GNOME Shell, instead of synthetic RandR monitors.
Requires existing Xvfb/GNOME executables; never installs host packages.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[1]
BINARY = REPO / 'src-tauri/target/agent/debug/deskmorph'


def wait(predicate, message, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(.15)
    raise AssertionError(message)


def output(*command):
    return subprocess.check_output(command, text=True, timeout=5)


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=6)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def worker(root, scale, position):
    assert os.environ['DESKMORPH_GEOMETRY_LAB'] == str(root)
    assert os.environ['DISPLAY'] == (root / 'display').read_text()
    import ctypes
    import gi
    gi.require_version('Atspi', '2.0')
    gi.require_version('Gdk', '3.0')
    from gi.repository import Atspi, Gdk, GLib
    speech_test = os.environ.get('DESKMORPH_CONTEXT_SPEECH_LAB') == '1'
    description_test = os.environ.get('DESKMORPH_CONTEXT_DESCRIPTION_LAB') == '1' or speech_test
    focus_test = os.environ.get('DESKMORPH_STUDIO_FOCUS_LAB') == '1'
    studio_test = os.environ.get('DESKMORPH_STUDIO_WIDGETS_LAB') == '1' or focus_test
    audio_controls = os.environ.get('DESKMORPH_AUDIO_CONTROLS_LAB') == '1'
    system_keys = os.environ.get('DESKMORPH_SYSTEM_KEYS_LAB') == '1'
    assert not (audio_controls and system_keys), 'Select one private control audit'
    dpi_source = 'audio' if audio_controls else 'system' if system_keys else os.environ.get('DESKMORPH_DPI_SOURCE_LAB')
    assert not (description_test and studio_test), 'Select one opt-in lab mode'
    language = 'en' if (description_test or studio_test) and scale == 2 else 'vi'
    labels = json.loads((REPO / 'src/i18n/messages.json').read_text())[language]
    report = dict(passed=False, scale=scale, position=position, language=language, cases=[])
    registry_log = (root / 'registry.log').open('w')
    registry = subprocess.Popen(['/usr/libexec/at-spi2-registryd'], stdout=registry_log, stderr=registry_log)
    app = None
    speech = None
    audio_server = None
    try:
        # Explicit registry startup avoids activation through host systemd/broker.
        time.sleep(.5)
        assert registry.poll() is None
        if dpi_source:
            from mutter_native_geometry_smoke import worker as dpi_worker
            after_open = None
            if audio_controls:
                from private_audio_server import PrivateAudioServer
                from audio_native_controls import audit
                audio_server = PrivateAudioServer(root / 'private-audio', policy=True)
                audio_server.start()
                audio_server.sink('deskmorph_audio_b', 'DeskMorph_Audio_B')
                audio_server.sink('deskmorph_audio_a', 'DeskMorph_Audio_A')
                audio_server.pactl('set-sink-volume', 'deskmorph_audio_b', '37%')
                os.environ['PULSE_SERVER'] = audio_server.address
                after_open = lambda **kwargs: audit(audio_server, **kwargs)
            if system_keys:
                from system_keyboard_private import audit
                after_open = audit
            audit_language = 'en' if (audio_controls or system_keys) and scale == 2 else 'vi'
            if os.environ.get('DESKMORPH_PRIVATE_GNOME_WM') == '1':
                from private_gnome_wm import private_gnome_wm
                with private_gnome_wm(root) as wm:
                    report = dpi_worker(root, 'screen', position, dpi_source, audit_language, after_open)
                    report['windowManager'] = wm
            else:
                report = dpi_worker(root, 'right', position, dpi_source, audit_language, after_open)
            report.update(scale=scale, privateDisplay=True)
            assert report['passed'], report
            return
        display = Gdk.Display.get_default()
        monitors = []
        for i in range(display.get_n_monitors()):
            monitor = display.get_monitor(i)
            area = monitor.get_workarea()
            monitors.append(dict(name=monitor.get_model(), scale=monitor.get_scale_factor(),
                                 physicalWorkarea=[value * scale for value in (area.x, area.y, area.width, area.height)]))
        target_name = 'right' if studio_test or speech_test else 'left'
        left = 0 if studio_test or speech_test else -1920
        target = next(m for m in monitors if m['name'] == target_name)
        assert target['scale'] == scale and target['physicalWorkarea'] == [left, 0, 1920, 1080], monitors
        report['monitors'] = monitors
        cfg = json.loads((REPO / 'src/config/defaults.json').read_text())
        cfg.update(monitor=target_name, position=position, pinnedApps=[], showStats=False,
                   showShuffle=False, showAudio=True, wallpaperScheduleEnabled=False,
                   reduceMotion=True, language=language)
        if description_test or focus_test:
            missing = root / 'intentionally-missing-app'
            assert not missing.exists()
            cfg['pinnedApps'] = [dict(id='deskmorph-description-lab', name='DeskMorph Description Lab', command=str(missing), matchClasses=['DeskMorphDescriptionLab'], enabled=True, iconType='custom')]
        if focus_test:
            gi.require_version('GdkPixbuf', '2.0')
            from gi.repository import GdkPixbuf
            folder = root / 'wallpaper-fixtures'
            folder.mkdir()
            for name, color in [('black', 0x000000ff), ('white', 0xffffffff)]:
                image = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 320, 180)
                image.fill(color)
                image.savev(str(folder / (name + '.png')), 'png', [], [])
            cfg['wallpaperFolders'] = [str(folder)]
        config = root / 'config/com.ducthanhdev.deskmorph/config.json'
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps(dict(schemaVersion=1, revision=0, config=cfg, warning=None)))
        original = config.read_bytes()
        with (root / 'app.log').open('w') as log:
            app = subprocess.Popen([str(BINARY)], stdout=log, stderr=log,
                env=dict(os.environ, DESKMORPH_CONFIG_HOME=str(root / 'config'), WEBKIT_DISABLE_DMABUF_RENDERER='1'))
        report['pid'] = app.pid

        def native(title):
            assert app.poll() is None, 'Owned app exited'
            tree = output('xwininfo', '-root', '-tree')
            for xid in re.findall(r'(0x[0-9a-f]+) "' + re.escape(title) + '"', tree):
                props = output('xprop', '-id', xid, '_NET_WM_PID')
                if not re.search(r'= ' + str(app.pid) + r'\b', props):
                    continue
                info = output('xwininfo', '-id', xid)
                if 'Map State: IsViewable' not in info:
                    continue
                rect = [int(re.search(key + r':\s+(-?\d+)', info).group(1))
                        for key in ('Absolute upper-left X', 'Absolute upper-left Y', 'Width', 'Height')]
                return dict(xid=xid, rect=rect)
            return None

        def stable(title, samples=6):
            previous = None
            count = 0
            def sample():
                nonlocal previous, count
                current = native(title)
                count = count + 1 if current and current == previous else 0
                previous = current
                return current if count >= samples else None
            return wait(sample, title + ' allocation did not settle')

        def walk(node):
            if node is None:
                return
            yield node
            for i in range(node.get_child_count()):
                yield from walk(node.get_child_at_index(i))

        def owned_accessible():
            desktop = Atspi.get_desktop(0)
            return next((node for node in walk(desktop) if node.get_role_name() == 'application' and node.get_process_id() == app.pid), None)

        accessible = wait(owned_accessible, 'Owned accessibility application absent')
        def content_ready():
            try:
                return any(n.get_role_name() == 'button' and n.get_name() == labels['calendar'] for n in walk(accessible))
            except GLib.GError:
                # WebKit may replace its initial empty document during load.
                return False
        wait(content_ready, 'Dock content not ready')
        dock = stable('DeskMorph Taskbar', samples=20)
        x, y, width, height = dock['rect']
        assert left <= x and x + width <= left + 1920 and 0 <= y and y + height <= 1080, dock
        assert abs((x + width / 2) - (left + 960)) <= 2, dock
        expected_y = 16 * scale if position == 'top' else 1080 - 16 * scale - height
        assert abs(y - expected_y) <= 2 and height == 52 * scale, dock
        report['dock'] = dock
        if speech_test:
            from isolated_speech import PrivateSpeech
            speech = PrivateSpeech(root)
            speech.start()
        x11 = ctypes.CDLL('libX11.so.6')
        xtst = ctypes.CDLL('libXtst.so.6')
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        x11.XKeysymToKeycode.restype = ctypes.c_uint
        x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        def keys(popup, chord):
            # Explicit private DISPLAY: never use the inherited host connection.
            connection = x11.XOpenDisplay((root / 'display').read_text().encode())
            assert connection
            try:
                x11.XSetInputFocus(connection, int(popup['xid'], 16), 2, 0)
                x11.XSync(connection, 0)
                codes = [x11.XKeysymToKeycode(connection, sym) for sym in chord]
                assert all(codes)
                for code in codes:
                    assert xtst.XTestFakeKeyEvent(connection, code, 1, 0)
                for code in reversed(codes):
                    assert xtst.XTestFakeKeyEvent(connection, code, 0, 0)
                x11.XSync(connection, 0)
            finally:
                x11.XCloseDisplay(connection)
        if studio_test:
            # These native controls must be measured from rendered pixels:
            # computed CSS does not expose the UA's checkmark/thumb colors.
            from collections import Counter
            from contrast_audit import contrast
            subprocess.run([str(BINARY)], env=dict(os.environ, DESKMORPH_CONFIG_HOME=str(root / 'config')), check=True, timeout=8)
            studio = stable('DeskMorph Studio')
            if focus_test:
                from studio_focus_pixels import audit
                report['studioFocus'] = audit(accessible, root, scale, studio, keys, native, config, original)
                report['passed'] = True
                return
            results = dict(passed=False, initialFocus='AT-SPI seed; subsequent Space/Tab/arrows/Home/End are XTest on private DISPLAY', captures=[])
            report['widgets'] = results

            def control(label, role):
                return next((n for n in walk(accessible) if n.get_role_name() == role and n.get_name() == label), None)

            def focused(label, role):
                node = control(label, role)
                return node and node.get_state_set().contains(Atspi.StateType.FOCUSED)

            def focus_control(label, role):
                node = wait(lambda: control(label, role), 'Missing control ' + label)
                assert node.get_component_iface().grab_focus()
                keys(studio, [])
                wait(lambda: focused(label, role), 'Control focus missing ' + label)
                return node

            def read_pixels(rect):
                window = Gdk.get_default_root_window()
                assert window.get_scale_factor() == scale
                assert all(value % scale == 0 for value in rect), rect
                # GdkPixbuf takes logical window coordinates and returns
                # device pixels. Passing physical coordinates would double
                # the crop at GDK_SCALE=2 and measure unrelated content.
                image = Gdk.pixbuf_get_from_window(window, *(value // scale for value in rect))
                assert image is not None
                assert (image.get_width(), image.get_height()) == (rect[2], rect[3])
                return image

            def capture(name, node):
                time.sleep(.2)
                area = node.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
                accessible_rect = [value * scale for value in (area.x, area.y, area.width, area.height)]
                rect = list(accessible_rect)
                if node.get_role_name() == 'check box':
                    # WebKit exposes this checkbox's enclosing label rectangle.
                    # showClock has no help line; the square control occupies
                    # the rightmost label-height box in the actual flex row.
                    assert rect[2] >= rect[3] and rect[3] == 20 * scale, rect
                    rect[0] += rect[2] - rect[3]
                    rect[2] = rect[3]
                pixbuf = read_pixels(rect)
                assert pixbuf is not None
                path = root / (name + '.png')
                pixbuf.savev(str(path), 'png', [], [])
                frame = native('DeskMorph Studio')['rect']
                assert frame[0] <= rect[0] and frame[1] <= rect[1]
                assert rect[0] + rect[2] <= frame[0] + frame[2] and rect[1] + rect[3] <= frame[1] + frame[3]
                # Preserve a surrounding frame for review of real focus outlines.
                full = read_pixels(frame)
                assert full is not None
                full.savev(str(root / (name + '-window.png')), 'png', [], [])
                margin = 8 * scale
                region_rect = [rect[0] - margin, rect[1] - margin, rect[2] + 2 * margin, rect[3] + 2 * margin]
                region = read_pixels(region_rect)
                assert region is not None
                region.savev(str(root / (name + '-focus-region.png')), 'png', [], [])
                region_data = region.get_pixels()
                region_stride, region_channels = region.get_rowstride(), region.get_n_channels()
                focus_color = (103, 232, 249)
                focus_pixels = sum(tuple(region_data[y * region_stride + x * region_channels:y * region_stride + x * region_channels + 3]) == focus_color
                    for y in range(region.get_height()) for x in range(region.get_width()))
                assert focus_pixels >= 8 * scale * scale, 'Native keyboard focus outline missing from capture'
                results['captures'].append(dict(name=name, rect=rect, accessibleRect=accessible_rect, path=str(path), focusColor=list(focus_color), focusPixelCount=focus_pixels))
                pixels = pixbuf.get_pixels()
                rowstride, channels = pixbuf.get_rowstride(), pixbuf.get_n_channels()
                def pixel(x, y):
                    offset = y * rowstride + x * channels
                    return tuple(pixels[offset:offset + 3])
                return pixbuf, pixel

            def saved(field, value):
                return json.loads(config.read_text())['config'][field] == value

            # Disabled preview/restore controls must be skipped at the nav/main boundary.
            restore = wait(lambda: control(labels['restoreAppearance'], 'button'), 'Restore button missing')
            assert not restore.get_state_set().contains(Atspi.StateType.ENABLED)
            focus_control(labels['systemTab'], 'button')
            keys(studio, [0xff09])
            wait(lambda: focused(labels['enabled'], 'check box'), 'Tab did not skip disabled preview/restore controls')
            results['disabledRestoreSkippedByTab'] = True
            checkbox = focus_control(labels['showClock'], 'check box')
            checked = checkbox.get_state_set().contains(Atspi.StateType.CHECKED)
            assert checked, 'Fixture must start checked for the pixel comparison'
            image, pixel = capture('checkbox-checked-focus', checkbox)
            palette = Counter(pixel(x, y) for y in range(image.get_height()) for x in range(image.get_width()))
            # On this installed GTK/WebKit renderer, the two largest flat regions
            # of the checked control are its colored fill and white checkmark.
            dominant = palette.most_common(2)
            assert len(dominant) == 2 and all(count >= 20 * scale * scale for _, count in dominant), dominant
            fill, mark = (value for value, _ in dominant)
            assert mark == (255, 255, 255) and fill != mark, dominant
            check_ratio = contrast([*fill, 1], [*mark, 1])
            results['checkboxPixels'] = dict(fill=list(fill), mark=list(mark), samples=[count for _, count in dominant], ratio=check_ratio, threshold=3, passed=check_ratio >= 3)
            keys(studio, [0x20])
            wait(lambda: saved('showClock', False), 'Checkbox Space did not persist')
            wait(lambda: not control(labels['showClock'], 'check box').get_state_set().contains(Atspi.StateType.CHECKED), 'Native checked state did not change')
            capture('checkbox-unchecked-focus', control(labels['showClock'], 'check box'))
            keys(studio, [0x20])
            wait(lambda: saved('showClock', True), 'Checkbox restore missing')
            keys(studio, [0xff09])
            wait(lambda: focused(labels['showStats'], 'check box'), 'Tab did not reach following checkbox')
            keys(studio, [0xffe1, 0xff09])
            wait(lambda: focused(labels['showClock'], 'check box'), 'Shift+Tab did not return to checkbox')
            results['checkboxSpaceAndTabReverse'] = True

            height = focus_control(labels['height'], 'slider')
            start = json.loads(config.read_text())['config']['height']
            image, pixel = capture('range-focus', height)
            centerline = Counter(pixel(x, image.get_height() // 2) for x in range(2 * scale, image.get_width() - 2 * scale))
            assert centerline[fill] >= 20 * scale and centerline[mark] >= 4 * scale, centerline.most_common(4)
            unfilled, count = next((value, count) for value, count in centerline.most_common() if value not in (fill, mark))
            assert count > 20 * scale
            ratios = dict(thumbToFill=contrast([*mark, 1], [*fill, 1]), thumbToUnfilled=contrast([*mark, 1], [*unfilled, 1]), fillToUnfilled=contrast([*fill, 1], [*unfilled, 1]))
            results['rangePixels'] = dict(fill=list(fill), thumb=list(mark), unfilled=list(unfilled), ratios=ratios, threshold=3, passed=min(ratios.values()) >= 3)
            keys(studio, [0xff53])
            wait(lambda: saved('height', start + 1), 'Range Right did not persist')
            keys(studio, [0xff51])
            wait(lambda: saved('height', start), 'Range Left restore missing')
            results['rangeArrowKeys'] = True
            position = focus_control(labels['position'], 'combo box')
            capture('select-focus', position)
            keys(studio, [0xff50])
            wait(lambda: saved('position', 'bottom'), 'Select Home failed')
            keys(studio, [0xff57])
            wait(lambda: saved('position', 'top'), 'Select End failed')
            results['selectHomeEnd'] = True
            results['privateConfigFieldsRestored'] = json.loads(config.read_text())['config'] == cfg
            assert results['privateConfigFieldsRestored']
            results['passed'] = results['checkboxPixels']['passed'] and results['rangePixels']['passed']
            report['passed'] = results['passed']
            assert results['passed'], 'Native checkbox/range pixels below 3:1'
            return
        sources = [(labels['searchApps'], 'DeskMorph Context Menu'),
                             (labels['audio'], 'DeskMorph Context Menu'),
                             (labels['systemTools'], 'DeskMorph Context Menu'),
                             (labels['calendar'], 'DeskMorph Calendar')]
        # Speech mode isolates the launch error; unrelated popup churn belongs
        # to the default allocation suite and can flood Orca's event queue.
        for label, title in ([] if speech_test else sources):
            def source():
                frame = next((n for n in walk(accessible) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Taskbar'), None)
                return next((n for n in walk(frame) if n.get_role_name() == 'button' and n.get_name() == label), None)
            button = wait(source, 'Dock button absent: ' + label)
            current_dock = stable('DeskMorph Taskbar')
            x, y, width, height = current_dock['rect']
            assert left <= x and x + width <= left + 1920 and 0 <= y and y + height <= 1080, current_dock
            assert abs(x + width / 2 - (left + 960)) <= 2, current_dock
            anchor = button.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
            # GTK AT-SPI screen extents use GDK logical coordinates.
            center = (anchor.x + anchor.width / 2) * scale
            assert x <= center <= x + width, (label, center, dock)
            assert button.get_action_iface().do_action(0), label
            popup = stable(title)
            px, py, pw, ph = popup['rect']
            assert left <= px and px + pw <= left + 1920 and 0 <= py and py + ph <= 1080, popup
            expected_x = round(max(left + 10 * scale, min(center - pw / 2, left + 1920 - 10 * scale - pw)))
            # Read product placement contract: horizontal inset is 10 logical px.
            assert abs(px - expected_x) <= 2, (label, center, popup, expected_x)
            gap = py - (y + height) if position == 'top' else y - (py + ph)
            ideal_y = y + height + 14 * scale if position == 'top' else y - ph - 14 * scale
            expected_py = max(10 * scale, min(ideal_y, 1080 - ph - 10 * scale))
            assert abs(py - expected_py) <= 2, (label, popup, expected_py)
            report['cases'].append(dict(source=label, dock=current_dock, sourceLogicalRect=[anchor.x, anchor.y, anchor.width, anchor.height], sourcePhysicalCenter=center, popup=popup, gap=gap))
            keys(popup, [0xff1b])
            wait(lambda: native(title) is None, 'Popup did not close: ' + label)
        if description_test:
            taskbar = next(n for n in walk(accessible) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Taskbar')
            pin = wait(lambda: next((n for n in walk(taskbar) if n.get_role_name() == 'button' and n.get_name().startswith('DeskMorph Description Lab •')), None), 'Description fixture pin absent')
            assert pin.get_component_iface().grab_focus()
            keys(native('DeskMorph Taskbar'), [0xffe1, 0xffc7])
            popup = stable('DeskMorph Context Menu')
            def launch_button():
                frame = next((n for n in walk(accessible) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Context Menu'), None)
                return next((n for n in walk(frame) if n.get_role_name() == 'button' and n.get_name() == labels['newLaunch']), None)
            launch = wait(launch_button, 'Fixture launch action absent')
            assert launch.get_component_iface().grab_focus()
            if speech_test:
                keys(popup, [0xff0d])
            else:
                assert launch.get_action_iface().do_action(0)
            expected = 'Không mở được ứng dụng' if language == 'vi' else 'Unable to launch application'
            wait(lambda: expected in launch_button().get_description(), 'Native launch error description missing')
            wait(lambda: launch_button().get_state_set().contains(Atspi.StateType.FOCUSED), 'Failed launch lost focus')
            report['nativeDescription'] = dict(language=language, expected=expected, observed=launch_button().get_description(), focusRetained=True, action='AT-SPI owned missing command; XTest Shift+F10 entry', scope='Native accessibility description, no Orca or warning/force coverage')
            if speech_test:
                report['nativeDescription']['action'] = 'Private XTest Shift+F10 and Enter on the owned missing command'
                report['nativeDescription']['scope'] = 'Native description/focus followed by real Orca speech observation'
                report['isolatedSpeech'] = speech.observe(expected)
                assert report['isolatedSpeech']['passed'], 'Private Orca launch speech failed'
            keys(popup, [0xff1b])
            wait(lambda: native('DeskMorph Context Menu') is None, 'Fixture menu did not dismiss')
        assert config.read_bytes() == original, 'Private profile changed'
        report['configUnchanged'] = True
        report['passed'] = True
    except Exception as error:
        report['error'] = repr(error)
        raise
    finally:
        cleanup_error = None
        if speech is not None:
            try:
                speech.close()
            except Exception as error:
                cleanup_error = error
                report.update(passed=False, speechCleanupError=repr(error))
        if app is not None:
            stop(app)
            report['appExitCode'] = app.returncode
        if audio_server is not None:
            audio_server.stop()
            report['privateAudioProcessesExited'] = all(p.poll() is not None for p in audio_server.processes)
        stop(registry)
        registry_log.close()
        (root / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        if cleanup_error is not None:
            raise cleanup_error


def run():
    xvfb = os.environ.get('DESKMORPH_XVFB', '/tmp/xvfb-root/usr/bin/Xvfb')
    assert Path(xvfb).is_file(), 'Set DESKMORPH_XVFB to an existing Xvfb executable'
    focus_test = os.environ.get('DESKMORPH_STUDIO_FOCUS_LAB') == '1'
    studio_test = os.environ.get('DESKMORPH_STUDIO_WIDGETS_LAB') == '1' or focus_test
    audio_controls = os.environ.get('DESKMORPH_AUDIO_CONTROLS_LAB') == '1'
    system_keys = os.environ.get('DESKMORPH_SYSTEM_KEYS_LAB') == '1'
    assert not (audio_controls and system_keys), 'Select one private control audit'
    dpi_source = 'audio' if audio_controls else 'system' if system_keys else os.environ.get('DESKMORPH_DPI_SOURCE_LAB')
    wm_test = os.environ.get('DESKMORPH_PRIVATE_GNOME_WM') == '1'
    assert not system_keys or wm_test, 'System key audit requires private GNOME WM'
    assert not wm_test or (dpi_source and not studio_test and os.environ.get('DESKMORPH_CONTEXT_DESCRIPTION_LAB') != '1' and os.environ.get('DESKMORPH_CONTEXT_SPEECH_LAB') != '1'), 'Private WM mode requires only DPI_SOURCE_LAB'
    speech_test = os.environ.get('DESKMORPH_CONTEXT_SPEECH_LAB') == '1'
    root = Path(tempfile.mkdtemp(prefix='deskmorph-negative-origin-'))
    report = dict(passed=False, root=str(root), runnerSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), studioWidgetsRequested=studio_test, studioFocusRequested=focus_test, contextSpeechRequested=speech_test, contextDescriptionRequested=os.environ.get('DESKMORPH_CONTEXT_DESCRIPTION_LAB') == '1', binarySha256=hashlib.sha256(BINARY.read_bytes()).hexdigest(), runs=[],
        scope='Native allocation/AT-SPI activation on virtual negative-origin RandR monitors, top/bottom at GTK integer scales 1/2',
        limits=['No window manager; negative monitor lies outside Xvfb drawable root',
                'AT-SPI opens sources; XTest Escape dismisses on the owned display only',
                'Does not prove visible pixels, host input, physical topology, fractional scaling or mixed DPI'])
    try:
        if studio_test:
            report.update(scope='Native Studio checkbox/range/select keys and rendered pixels in vi/scale1, en/scale2 on positive Xvfb monitor', limits=['No window manager, physical display, host input, fractional/mixed DPI or Orca proof', 'AT-SPI seeds control focus; XTest then sends actual Space/Tab/Shift+Tab/arrows/Home/End on the owned DISPLAY', 'Pixel palette/centerline checks target this installed GTK/WebKit native renderer, not every platform or theme'])
        if focus_test:
            report.update(scope='Native Studio five-page Tab/reverse/disabled traversal with focus pixels and window bounds, vi/scale1 and en/scale2 in private Xvfb', limits=['No host input, window manager, fractional DPI, Orca or all dynamic states proof', 'AT-SPI seeds navigation focus; subsequent traversal uses private XTest Tab/Shift+Tab', 'Focus pixel count and control bounds do not by themselves prove every outline edge is unclipped'])
        if dpi_source:
            report.update(scope='DPI geometry worker on private positive Xvfb monitor, integer scales1/2, top/bottom, source=' + dpi_source, limits=['Worker/coordinate checks only; no host WM, fractional/mixed DPI, physical pixels or keyboard acceptance'])
        if wm_test:
            report.update(scope='Native DPI worker with GNOME Shell on one drawable1920x1080 Xvfb monitor, integer GTK scales1/2, top/bottom, source=' + dpi_source, limits=['No physical monitor, host input, output-scale fractional/mixed DPI, negative origin or popup sequencing proof', 'Private Shell startup overview is dismissed with private Escape before app launch'])
        if system_keys:
            report.update(scope='Private GNOME X11 system actions via XTest Enter, receiver fixtures, vi/scale1 and en/scale2, top/bottom', limits=['No host input, files, app launches or system preferences mutation', 'AT-SPI seeds control focus; XTest Enter invokes private desktop receivers; not whole-app Tab route or third-party package certification'])
        if audio_controls:
            report.update(scope='Private audio native output/volume/mute keys and rendered control samples, vi/scale1 and en/scale2, top/bottom', limits=['No host audio/display mutation; PipeWire/Pulse have private sockets and hardware-free null sinks', 'AT-SPI seeds control focus; actual XTest Space/Left/Right activate controls on private DISPLAY', 'Pixel ratios cover enumerated native control paints and focus in the reference renderer, not arbitrary themes or full accessibility certification'])
        if speech_test:
            report.update(scope='Native launch error description/focus and Orca speech, vi/scale1 and en/scale2, top/bottom on positive Xvfb monitor', limits=['No host display input, window manager, physical monitor, fractional/mixed DPI or full context keyboard suite proof', 'Private Orca/session/a11y buses; synthesis captured on owned host null sink without speaker playback', 'Whole-application announcements and human evaluation of intelligibility remain outside these fixtures'])
        for scale in (1, 2):
            for position in (('top',) if studio_test else ('top', 'bottom')):
                case = root / f'scale{scale}-{position}'
                case.mkdir()
                env = dict(os.environ, DESKMORPH_GEOMETRY_LAB=str(case))
                if speech_test:
                    env['DESKMORPH_PRIVATE_SPEECH_HOST_PULSE'] = os.environ.get('PULSE_SERVER') or f'unix:/run/user/{os.getuid()}/pulse/native'
                for key in ('AT_SPI_BUS_ADDRESS', 'DBUS_SESSION_BUS_ADDRESS', 'DBUS_STARTER_ADDRESS', 'DBUS_STARTER_BUS_TYPE', 'WAYLAND_DISPLAY', 'SESSION_MANAGER', 'GTK_MODULES'):
                    env.pop(key, None)
                for key, name in [('XDG_CONFIG_HOME', 'config'), ('XDG_DATA_HOME', 'data'), ('XDG_CACHE_HOME', 'cache'), ('XDG_STATE_HOME', 'state'), ('XDG_RUNTIME_DIR', 'runtime')]:
                    folder = case / name
                    folder.mkdir(mode=0o700)
                    env[key] = str(folder)
                env.update(GDK_BACKEND='x11', GDK_SCALE=str(scale), GDK_DPI_SCALE='1', GSETTINGS_BACKEND='keyfile',
                    XDG_CURRENT_DESKTOP='GNOME', XDG_SESSION_TYPE='x11', GTK_MODULES='atk-bridge', NO_AT_BRIDGE='0',
                    DBUS_SYSTEM_BUS_ADDRESS='unix:path=' + str(case / 'no-system-bus'), PULSE_SERVER='unix:' + str(case / 'no-audio'))
                with (case / 'xvfb.log').open('w') as log:
                    server = subprocess.Popen([xvfb, '-displayfd', '1', '-screen', '0', ('1920x1080x24' if wm_test else '3840x2160x24' if studio_test or speech_test or dpi_source else '3840x1080x24'), '-nolisten', 'tcp', '-ac', '-noreset'], env=env, stdout=subprocess.PIPE, stderr=log, text=True)
                bus = session = None
                try:
                    assert select.select([server.stdout], [], [], 8)[0], 'Xvfb readiness timeout'
                    number = server.stdout.readline().strip()
                    assert number.isdigit()
                    env['DISPLAY'] = ':' + number
                    (case / 'display').write_text(env['DISPLAY'])
                    for name, geometry in ([] if wm_test else [('left', '1920/527x1080/296+-1920+0'), ('right', '1920/344x1080/193+0+0')]):
                        subprocess.run(['xrandr', '--setmonitor', name, geometry, 'none'], env=env, check=True, timeout=5)
                    conf = case / 'a11y.conf'
                    conf.write_text(Path('/usr/share/defaults/at-spi2/accessibility.conf').read_text().replace('unix:dir=/tmp', 'unix:path=' + str(case / 'a11y.sock')))
                    with (case / 'a11y.log').open('w') as log:
                        bus = subprocess.Popen(['dbus-daemon', '--config-file=' + str(conf), '--nofork', '--print-address'], env=env, stdout=subprocess.PIPE, stderr=log, text=True)
                    assert select.select([bus.stdout], [], [], 5)[0]
                    env['AT_SPI_BUS_ADDRESS'] = bus.stdout.readline().strip()
                    assert env['AT_SPI_BUS_ADDRESS'].startswith('unix:')
                    with (case / 'session.log').open('w') as log:
                        session = subprocess.Popen(['dbus-run-session', '--', '/usr/bin/python3', str(Path(__file__).resolve()), '--worker', str(case), str(scale), position], env=env, stdout=log, stderr=log, start_new_session=True)
                    # Five-page pixel traversal includes the installed app
                    # catalogue; unlike a popup smoke its work scales with it.
                    assert session.wait(timeout=300 if focus_test or system_keys else 90) == 0, str(case / 'session.log')
                    print(json.dumps(dict(scale=scale, position=position, passed=True)), flush=True)
                finally:
                    if session is not None:
                        try:
                            os.killpg(session.pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                        stop(session)
                    if bus is not None:
                        stop(bus)
                    stop(server)
                    result_file = case / 'result.json'
                    if result_file.exists():
                        report['runs'].append(json.loads(result_file.read_text()))
        report['passed'] = True
    except Exception as error:
        report['error'] = repr(error)
        raise
    finally:
        (root / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(str(root / 'result.json'), flush=True)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        worker(Path(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
    else:
        run()
