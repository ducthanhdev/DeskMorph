#!/usr/bin/python3
"""Opt-in native allocation audit on owned Xvfb/RandR monitors.

No host display input or topology mutation; Escape targets the owned X server. Negative RandR monitors extend
outside Xvfb's drawable root: this measures native allocations and AT-SPI
activation, not visible pixels, real mouse/keyboard, WM or mixed DPI behavior.
Requires an existing Xvfb executable; never installs host packages.
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
    description_test = os.environ.get('DESKMORPH_CONTEXT_DESCRIPTION_LAB') == '1'
    language = 'en' if description_test and scale == 2 else 'vi'
    labels = json.loads((REPO / 'src/i18n/messages.json').read_text())[language]
    report = dict(passed=False, scale=scale, position=position, language=language, cases=[])
    registry_log = (root / 'registry.log').open('w')
    registry = subprocess.Popen(['/usr/libexec/at-spi2-registryd'], stdout=registry_log, stderr=registry_log)
    app = None
    try:
        # Explicit registry startup avoids activation through host systemd/broker.
        time.sleep(.5)
        assert registry.poll() is None
        display = Gdk.Display.get_default()
        monitors = []
        for i in range(display.get_n_monitors()):
            monitor = display.get_monitor(i)
            area = monitor.get_workarea()
            monitors.append(dict(name=monitor.get_model(), scale=monitor.get_scale_factor(),
                                 physicalWorkarea=[value * scale for value in (area.x, area.y, area.width, area.height)]))
        target = next(m for m in monitors if m['name'] == 'left')
        assert target['scale'] == scale and target['physicalWorkarea'] == [-1920, 0, 1920, 1080], monitors
        report['monitors'] = monitors
        cfg = json.loads((REPO / 'src/config/defaults.json').read_text())
        cfg.update(monitor='left', position=position, pinnedApps=[], showStats=False,
                   showShuffle=False, showAudio=True, wallpaperScheduleEnabled=False,
                   reduceMotion=True, language=language)
        if description_test:
            missing = root / 'intentionally-missing-app'
            assert not missing.exists()
            cfg['pinnedApps'] = [dict(id='deskmorph-description-lab', name='DeskMorph Description Lab', command=str(missing), matchClasses=['DeskMorphDescriptionLab'], enabled=True, iconType='custom')]
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
        assert -1920 <= x < 0 and x + width <= 0 and 0 <= y and y + height <= 1080, dock
        assert abs((x + width / 2) - (-960)) <= 2, dock
        expected_y = 16 * scale if position == 'top' else 1080 - 16 * scale - height
        assert abs(y - expected_y) <= 2 and height == 52 * scale, dock
        report['dock'] = dock
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
        for label, title in [(labels['searchApps'], 'DeskMorph Context Menu'),
                             (labels['audio'], 'DeskMorph Context Menu'),
                             (labels['systemTools'], 'DeskMorph Context Menu'),
                             (labels['calendar'], 'DeskMorph Calendar')]:
            def source():
                frame = next((n for n in walk(accessible) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Taskbar'), None)
                return next((n for n in walk(frame) if n.get_role_name() == 'button' and n.get_name() == label), None)
            button = wait(source, 'Dock button absent: ' + label)
            current_dock = stable('DeskMorph Taskbar')
            x, y, width, height = current_dock['rect']
            assert -1920 <= x < 0 and x + width <= 0 and 0 <= y and y + height <= 1080, current_dock
            assert abs(x + width / 2 + 960) <= 2, current_dock
            anchor = button.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
            # GTK AT-SPI screen extents use GDK logical coordinates.
            center = (anchor.x + anchor.width / 2) * scale
            assert x <= center <= x + width, (label, center, dock)
            assert button.get_action_iface().do_action(0), label
            popup = stable(title)
            px, py, pw, ph = popup['rect']
            assert -1920 <= px < 0 and px + pw <= 0 and 0 <= py and py + ph <= 1080, popup
            expected_x = round(max(-1920 + 10 * scale, min(center - pw / 2, -10 * scale - pw)))
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
            assert launch.get_action_iface().do_action(0)
            expected = 'Không mở được ứng dụng' if language == 'vi' else 'Unable to launch application'
            wait(lambda: expected in launch_button().get_description(), 'Native launch error description missing')
            wait(lambda: launch_button().get_state_set().contains(Atspi.StateType.FOCUSED), 'Failed launch lost focus')
            report['nativeDescription'] = dict(language=language, expected=expected, observed=launch_button().get_description(), focusRetained=True, action='AT-SPI owned missing command; XTest Shift+F10 entry', scope='Native accessibility description, no Orca or warning/force coverage')
            keys(popup, [0xff1b])
            wait(lambda: native('DeskMorph Context Menu') is None, 'Fixture menu did not dismiss')
        assert config.read_bytes() == original, 'Private profile changed'
        report['configUnchanged'] = True
        report['passed'] = True
    except Exception as error:
        report['error'] = repr(error)
        raise
    finally:
        if app is not None:
            stop(app)
            report['appExitCode'] = app.returncode
        stop(registry)
        registry_log.close()
        (root / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')


def run():
    xvfb = os.environ.get('DESKMORPH_XVFB', '/tmp/xvfb-root/usr/bin/Xvfb')
    assert Path(xvfb).is_file(), 'Set DESKMORPH_XVFB to an existing Xvfb executable'
    root = Path(tempfile.mkdtemp(prefix='deskmorph-negative-origin-'))
    report = dict(passed=False, root=str(root), contextDescriptionRequested=os.environ.get('DESKMORPH_CONTEXT_DESCRIPTION_LAB') == '1', binarySha256=hashlib.sha256(BINARY.read_bytes()).hexdigest(), runs=[],
        scope='Native allocation/AT-SPI activation on virtual negative-origin RandR monitors, top/bottom at GTK integer scales 1/2',
        limits=['No window manager; negative monitor lies outside Xvfb drawable root',
                'AT-SPI opens sources; XTest Escape dismisses on the owned display only',
                'Does not prove visible pixels, host input, physical topology, fractional scaling or mixed DPI'])
    try:
        for scale in (1, 2):
            for position in ('top', 'bottom'):
                case = root / f'scale{scale}-{position}'
                case.mkdir()
                env = dict(os.environ, DESKMORPH_GEOMETRY_LAB=str(case))
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
                    server = subprocess.Popen([xvfb, '-displayfd', '1', '-screen', '0', '3840x1080x24', '-nolisten', 'tcp', '-ac', '-noreset'], env=env, stdout=subprocess.PIPE, stderr=log, text=True)
                bus = session = None
                try:
                    assert select.select([server.stdout], [], [], 8)[0], 'Xvfb readiness timeout'
                    number = server.stdout.readline().strip()
                    assert number.isdigit()
                    env['DISPLAY'] = ':' + number
                    (case / 'display').write_text(env['DISPLAY'])
                    for name, geometry in [('left', '1920/527x1080/296+-1920+0'), ('right', '1920/344x1080/193+0+0')]:
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
                    assert session.wait(timeout=90) == 0, str(case / 'session.log')
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
