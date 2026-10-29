#!/usr/bin/python3
"""GNOME headless capability probe on a private bus, runtime and settings tree.

Default mode does not inject input. Opt-in prototype/launcher/shortcut modes
use virtual input only inside the owned compositor. Never uses the host display,
Shell unsafe mode or host settings. Each report states the measured UI scope.
"""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import secrets
import shutil
import sys
from gi.repository import Gio, GLib


MARKER = 'DESKMORPH_COMPOSITOR_LAB'
SOCKET = 'deskmorph-lab'


def connection(address):
    return Gio.DBusConnection.new_for_address_sync(address,
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)


def call(bus, destination, path, interface, method, args=None, timeout=5000):
    return bus.call_sync(destination, path, interface, method, args, None, Gio.DBusCallFlags.NONE, timeout, None)


def owned(pid, root):
    try:
        return f'{MARKER}={root}'.encode() in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
    except OSError:
        return False


def active(pid):
    try: return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] != 'Z'
    except OSError: return False


def owned_descendants(root):
    pending = [os.getpid()]
    found = set()
    while pending:
        parent = pending.pop()
        try: children = Path(f'/proc/{parent}/task/{parent}/children').read_text().split()
        except OSError: continue
        for value in children:
            pid = int(value)
            if pid not in found and owned(pid, root):
                found.add(pid); pending.append(pid)
    return found


def globals_on(socket):
    lib = C.CDLL('libwayland-client.so.0')
    class Interface(C.Structure):
        _fields_ = [('name', C.c_char_p), ('version', C.c_int), ('method_count', C.c_int),
            ('methods', C.c_void_p), ('event_count', C.c_int), ('events', C.c_void_p)]
    lib.wl_display_connect.argtypes = [C.c_char_p]; lib.wl_display_connect.restype = C.c_void_p
    lib.wl_proxy_marshal_flags.argtypes = [C.c_void_p, C.c_uint, C.POINTER(Interface), C.c_uint, C.c_uint]
    lib.wl_proxy_marshal_flags.restype = C.c_void_p
    lib.wl_proxy_add_listener.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p]; lib.wl_proxy_add_listener.restype = C.c_int
    lib.wl_display_roundtrip.argtypes = [C.c_void_p]; lib.wl_display_roundtrip.restype = C.c_int
    lib.wl_proxy_destroy.argtypes = [C.c_void_p]; lib.wl_display_disconnect.argtypes = [C.c_void_p]
    display = lib.wl_display_connect(os.fsencode(socket)); assert display, 'Cannot connect to the owned Wayland socket'
    registry = None
    interfaces = []
    @C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_uint, C.c_char_p, C.c_uint)
    def added(data, registry, name, interface, version):
        interfaces.append(dict(interface=interface.decode(), version=version))
    @C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_uint)
    def removed(data, registry, name): pass
    class Listener(C.Structure): _fields_ = [('added', C.c_void_p), ('removed', C.c_void_p)]
    # Callback references stay alive through roundtrip and proxy destruction.
    listener = Listener(C.cast(added, C.c_void_p), C.cast(removed, C.c_void_p))
    try:
        interface = Interface.in_dll(lib, 'wl_registry_interface')
        registry = lib.wl_proxy_marshal_flags(display, 1, C.byref(interface), 1, 0, None)
        assert registry and lib.wl_proxy_add_listener(registry, C.byref(listener), None) == 0
        assert lib.wl_display_roundtrip(display) >= 0
        return sorted(interfaces, key=lambda item: item['interface'])
    finally:
        if registry: lib.wl_proxy_destroy(registry)
        lib.wl_display_disconnect(display)


def session(root):
    assert os.environ.get(MARKER) == str(root)
    assert os.environ['XDG_RUNTIME_DIR'] == str(root / 'runtime') and not os.environ.get('DISPLAY')
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    # Activated GTK portal/helper processes must use the same owned socket.
    values = {key: os.environ[key] for key in [MARKER, 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR',
        'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'GSETTINGS_BACKEND', 'GDK_BACKEND',
        'XDG_SESSION_TYPE', 'XDG_CURRENT_DESKTOP']}
    if os.environ.get('DESKMORPH_PROTOTYPE_TOKEN'):
        values['DESKMORPH_PROTOTYPE_TOKEN'] = os.environ['DESKMORPH_PROTOTYPE_TOKEN']
    if os.environ.get('DESKMORPH_COSMIC_TEST'):
        values['DESKMORPH_COSMIC_TEST'] = '1'
    if os.environ.get('DESKMORPH_WALLPAPER_TEST'):
        values['DESKMORPH_WALLPAPER_TEST'] = '1'
    if os.environ.get('DESKMORPH_SNAP_GUI_TEST'):
        values['DESKMORPH_SNAP_GUI_TEST'] = '1'
    if os.environ.get('DESKMORPH_SNAP_TEST'):
        values['DESKMORPH_SNAP_TEST'] = '1'
    if os.environ.get('DESKMORPH_TERMINAL_TEST'):
        values['DESKMORPH_TERMINAL_TEST'] = '1'
    if os.environ.get('DESKMORPH_LAB_BINARY'):
        values['DESKMORPH_LAB_BINARY'] = os.environ['DESKMORPH_LAB_BINARY']
    call(bus, 'org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
        'UpdateActivationEnvironment', GLib.Variant('(a{ss})', (values,)))
    metadata = dict(values, busAddress=os.environ['DBUS_SESSION_BUS_ADDRESS'], gnomePid=os.getpid())
    (root / 'session.json').write_text(json.dumps(metadata))
    os.execvp('gnome-shell', ['gnome-shell', '--headless', '--wayland', '--no-x11',
        '--virtual-monitor=1280x720', '--wayland-display=' + os.environ['WAYLAND_DISPLAY']])


def probe(root, metadata, launcher=False, shortcut=False):
    assert owned(metadata['gnomePid'], root)
    assert Path(f'/proc/{metadata["gnomePid"]}/exe').resolve().name == 'gnome-shell'
    bus = connection(metadata['busAddress'])
    result = dict(gnomePid=metadata['gnomePid'], globals=globals_on(Path(metadata['WAYLAND_DISPLAY']) if Path(metadata['WAYLAND_DISPLAY']).is_absolute() else root / 'runtime' / SOCKET))
    result['displayState'] = call(bus, 'org.gnome.Mutter.DisplayConfig', '/org/gnome/Mutter/DisplayConfig',
        'org.gnome.Mutter.DisplayConfig', 'GetCurrentState').unpack()
    result['probes'] = {}
    cases = [
        ('windows', 'org.gnome.Shell.Introspect', '/org/gnome/Shell/Introspect', 'org.gnome.Shell.Introspect', 'GetWindows', None),
        ('shellEval', 'org.gnome.Shell', '/org/gnome/Shell', 'org.gnome.Shell', 'Eval', GLib.Variant('(s)', ('global.get_window_actors().length',))),
        ('globalShortcuts', 'org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop',
            'org.freedesktop.DBus.Properties', 'Get', GLib.Variant('(ss)', ('org.freedesktop.portal.GlobalShortcuts', 'version'))),
    ]
    for key, destination, path, interface, method, args in cases:
        try:
            result['probes'][key] = dict(value=call(bus, destination, path, interface, method, args, timeout=8000).unpack())
        except GLib.Error as error:
            result['probes'][key] = dict(error=str(error))
    result['packages'] = subprocess.run(['dpkg-query', '-W', 'gnome-shell', 'libmutter-14-0',
        'gnome-settings-daemon', 'xdg-desktop-portal', 'xdg-desktop-portal-gnome', 'xdg-desktop-portal-gtk'],
        capture_output=True, text=True, check=False).stdout.splitlines()
    result['portalBackends'] = {p.name: p.read_text() for p in sorted(Path('/usr/share/xdg-desktop-portal/portals').glob('*.portal'))}
    # GSettings is the proposed GNOME wallpaper API. This only verifies the lab's
    # settings roundtrip; visibility and wallpaper adapter behavior are separate.
    env = dict(os.environ, **{k: v for k, v in metadata.items() if k.isupper()}, DBUS_SESSION_BUS_ADDRESS=metadata['busAddress'])
    env.pop('DISPLAY', None)
    def settings(*args):
        return subprocess.check_output(['gsettings', *args], env=env, text=True).strip()
    old = settings('get', 'org.gnome.desktop.background', 'picture-uri')
    def write_read(value):
        # The keyfile backend is shared by startup helpers in this private lab.
        # Wait for their initial settings writes to settle, then require two
        # consecutive reads; never interpret a successful writer exit as proof.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            settings('set', 'org.gnome.desktop.background', 'picture-uri', value)
            time.sleep(.2)
            if settings('get', 'org.gnome.desktop.background', 'picture-uri') == value:
                time.sleep(.2)
                if settings('get', 'org.gnome.desktop.background', 'picture-uri') == value: return
        raise AssertionError('Private wallpaper settings roundtrip did not settle')
    try:
        write_read("'file://" + str(root / 'wallpaper-probe.png') + "'")
        result['wallpaperSettingsRoundtrip'] = True
    finally:
        write_read(old)
    pids = {metadata['gnomePid']}
    names = call(bus, 'org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'ListNames').unpack()[0]
    for name in names:
        try:
            pid = call(bus, 'org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                'GetConnectionUnixProcessID', GLib.Variant('(s)', (name,))).unpack()[0]
            if owned(pid, root): pids.add(pid)
        except GLib.Error: pass  # A private helper may exit between ListNames and PID lookup.
    result['ownedBusPids'] = sorted(pids)
    if launcher:
        # The distro launcher may choose a systemd-backed accessibility broker,
        # unavailable on this private session. Use a dedicated daemon/registry.
        address = 'unix:path=' + str(root / 'a11y.sock')
        config = root / 'a11y.conf'
        config.write_text('<busconfig><type>accessibility</type><listen>' + address + '</listen><auth>EXTERNAL</auth><policy context="default"><allow user="*"/><allow own="*"/><allow send_destination="*"/><allow receive_sender="*"/></policy></busconfig>')
        env['AT_SPI_BUS_ADDRESS'] = address
        with (root / 'accessibility.log').open('w') as log:
            a11y = subprocess.Popen(['dbus-daemon', '--nofork', '--config-file=' + str(config)], env=env, stdout=log, stderr=log)
            registry = None
            try:
                deadline = time.monotonic() + 5
                while not (root / 'a11y.sock').exists():
                    assert a11y.poll() is None and time.monotonic() < deadline
                    time.sleep(.1)
                registry = subprocess.Popen(['/usr/libexec/at-spi2-registryd'], env=env, stdout=log, stderr=log)
                with (root / 'launcher-probe.log').open('w') as output:
                    worker = 'cosmic_background_probe.py' if env.get('DESKMORPH_COSMIC_TEST') else 'wallpaper_keyboard_probe.py' if env.get('DESKMORPH_WALLPAPER_TEST') else 'wayland_shortcut_probe.py' if shortcut else 'wayland_launcher_probe.py'
                    subprocess.run(['/usr/bin/python3', str(Path(__file__).with_name(worker))], env=env, stdout=output, stderr=output, timeout=120, check=True)
            finally:
                for child in (registry, a11y):
                    if child and child.poll() is None:
                        child.terminate()
                        try: child.wait(timeout=5)
                        except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=5)
        result['launcher'] = json.loads((root / 'launcher-result.json').read_text())
    elif metadata.get('DESKMORPH_PROTOTYPE_TOKEN'):
        sys.path.insert(0, str(Path(__file__).with_name('wayland_prototype')))
        from probe import run as run_prototype
        result['prototype'] = run_prototype(root, metadata, bus, call)
    bus.close_sync(None)
    return result


def run(output, prototype=False, launcher=False, shortcut=False, binary=None, terminal=False, snap=False, snap_gui=False, wallpaper=False, cosmic=False):
    snap = snap or snap_gui
    launcher = launcher or shortcut or terminal or snap or wallpaper or cosmic
    # Reap private D-Bus service grandchildren as well as the direct supervisor.
    libc = C.CDLL(None)
    assert libc.prctl(36, 1, 0, 0, 0) == 0, 'Cannot establish child subreaper'
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='deskmorph-wayland-lab-') as directory:
        root = Path(directory)
        for name in ['runtime', 'config', 'data', 'cache']: (root / name).mkdir(mode=0o700)
        env = dict(os.environ, **{MARKER: str(root)}, XDG_RUNTIME_DIR=str(root / 'runtime'),
            XDG_CONFIG_HOME=str(root / 'config'), XDG_DATA_HOME=str(root / 'data'), XDG_CACHE_HOME=str(root / 'cache'),
            XDG_SESSION_TYPE='wayland', XDG_CURRENT_DESKTOP='GNOME', GSETTINGS_BACKEND='keyfile',
            GDK_BACKEND='wayland', WAYLAND_DISPLAY=SOCKET, LIBGL_ALWAYS_SOFTWARE='1')
        for key in ['DISPLAY', 'AT_SPI_BUS_ADDRESS', 'SESSION_MANAGER', 'DESKTOP_STARTUP_ID', 'XDG_SESSION_ID']:
            env.pop(key, None)
        if cosmic:
            env['DESKMORPH_COSMIC_TEST'] = '1'
        if wallpaper:
            env['DESKMORPH_WALLPAPER_TEST'] = '1'
        if snap:
            env['DESKMORPH_SNAP_TEST'] = '1'
        socket_path = root / 'runtime' / SOCKET
        if snap_gui:
            socket_path = Path('/run/user') / str(os.getuid()) / ('wayland-9' + secrets.token_hex(6))
            assert not socket_path.exists() and not socket_path.with_suffix('.lock').exists()
            env['WAYLAND_DISPLAY'] = str(socket_path)
            env['DESKMORPH_SNAP_GUI_TEST'] = '1'
        if terminal:
            env['DESKMORPH_TERMINAL_TEST'] = '1'
        if binary:
            binary = binary.resolve()
            assert binary.is_file(), 'Lab binary is missing'
            env['DESKMORPH_LAB_BINARY'] = str(binary)
        if prototype or launcher:
            env['DESKMORPH_PROTOTYPE_TOKEN'] = secrets.token_hex(32)
            extension = root / 'data/gnome-shell/extensions/deskmorph-lab@deskmorph.local'
            shutil.copytree(Path(__file__).with_name('wayland_prototype'), extension)
            if launcher:
                (extension / 'extension.js').rename(extension / 'base_extension.js')
                shutil.copyfile(extension / 'launcher_extension.js', extension / 'extension.js')
            for key, value in [('enabled-extensions', "['deskmorph-lab@deskmorph.local']"), ('disable-user-extensions', 'false')]:
                subprocess.run(['gsettings', 'set', 'org.gnome.shell', key, value], env=env, check=True)
        result = None
        process = None
        started = time.monotonic()
        try:
            with (root / 'session.log').open('w') as log:
                process = subprocess.Popen(['dbus-run-session', '--', '/usr/bin/python3', str(Path(__file__).resolve()),
                    '--session', str(root)], env=env, stdout=log, stderr=log, start_new_session=True)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None: raise AssertionError('Owned GNOME compositor exited before readiness')
                if (root / 'session.json').exists() and socket_path.exists():
                    metadata = json.loads((root / 'session.json').read_text())
                    try:
                        bus = connection(metadata['busAddress'])
                        call(bus, 'org.gnome.Mutter.DisplayConfig', '/org/gnome/Mutter/DisplayConfig',
                            'org.gnome.Mutter.DisplayConfig', 'GetCurrentState', timeout=1000)
                        bus.close_sync(None)
                        break
                    except GLib.Error: pass
                time.sleep(.1)
            else: raise AssertionError('Owned compositor readiness timed out')
            result = probe(root, metadata, launcher, shortcut)
            result.update(kind='GNOME headless launcher probe' if launcher else 'GNOME headless extension prototype' if prototype else 'GNOME headless capability probe', hostDisplayUsed=False, inputInjected=prototype or launcher, hostInputInjected=False,
                unsafeModeEnabled=False, privateSettings=True, elapsedSeconds=round(time.monotonic() - started, 3))
        except Exception as error:
            result = dict(kind='GNOME headless failed probe', passed=False,
                error=str(error), hostDisplayUsed=False, hostInputInjected=False,
                privateSettings=True, elapsedSeconds=round(time.monotonic() - started, 3))
            raise
        finally:
            # Preserve worker diagnostics even if confined child cleanup fails.
            for name in ('launcher-probe', 'deskmorph-launcher'):
                if (root / (name + '.log')).exists():
                    output.with_suffix('.' + name + '.log').write_text((root / (name + '.log')).read_text())
            if process:
                try: os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError: pass
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
            pids = set(result.get('ownedBusPids', []) if result else []) | owned_descendants(root)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    while os.waitpid(-1, os.WNOHANG)[0]: pass
                except ChildProcessError: pass
                pids.update(owned_descendants(root))
                live = [pid for pid in pids if active(pid)]
                if not live: break
                for pid in live:
                    if owned(pid, root):
                        try: os.kill(pid, signal.SIGTERM)
                        except (ProcessLookupError, PermissionError): pass
                time.sleep(.1)
            for pid in pids:
                if active(pid) and owned(pid, root):
                    try: os.kill(pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError): pass
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                try:
                    while os.waitpid(-1, os.WNOHANG)[0]: pass
                except ChildProcessError: pass
                if not any(active(pid) for pid in pids): break
                time.sleep(.1)
            log = (root / 'session.log').read_text()
            output.with_suffix('.log').write_text(log)
            for capture in root.glob('background-*.png'):
                shutil.copyfile(capture, output.with_name(output.stem + '-' + capture.name))
            if (root / 'fixture.log').exists():
                output.with_suffix('.fixture.log').write_text((root / 'fixture.log').read_text())
            for name in ('launcher-probe', 'deskmorph-launcher', 'accessibility', 'media-keys', 'shortcut-background'):
                if (root / (name + '.log')).exists(): output.with_suffix('.' + name + '.log').write_text((root / (name + '.log')).read_text())
            assert not any(active(pid) for pid in pids), 'Owned lab process did not exit'
            # xdg-document-portal may leave a disconnected FUSE mount after its
            # process exits. Never recurse into it or touch the host portal.
            document_mount = root / 'runtime/doc'
            def portal_mounted():
                return any(line.split()[4] == str(document_mount)
                    for line in Path('/proc/self/mountinfo').read_text().splitlines())
            for _ in range(4):
                if not portal_mounted(): break
                subprocess.run(['fusermount3', '-uz', str(document_mount)], check=True,
                    capture_output=True, text=True, timeout=5)
            assert not portal_mounted(), 'Owned portal mount did not detach'
            if result: result['ownedPortalMountRemoved'] = True
            if snap_gui:
                for endpoint in (socket_path, Path(str(socket_path) + '.lock')):
                    if endpoint.exists():
                        assert endpoint.stat().st_uid == os.getuid()
                        endpoint.unlink()
                if result: result['ownedWaylandSocketRemoved'] = True
            if result:
                result['ownedChildPids'] = sorted(pids)
                result['ownedProcessesExited'] = not any(active(pid) for pid in pids)
                assert result['ownedProcessesExited'], 'Owned lab process did not exit'
                output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
                print(json.dumps(dict(output=str(output), gnomePid=result.get('gnomePid'), probes=result.get('probes'),
                    ownedProcessesExited=result['ownedProcessesExited']), ensure_ascii=False), flush=True)
            elif log:
                print(log[-2000:], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--session', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--prototype', action='store_true', help='Run lab-only GNOME extension and native window prototype')
    parser.add_argument('--launcher-test', action='store_true', help='Exercise the actual DeskMorph CLI launcher on private Wayland')
    parser.add_argument('--shortcut-test', action='store_true', help='Exercise GNOME custom shortcut through private gsd-media-keys')
    parser.add_argument('--cosmic-test', action='store_true', help='Probe nested COSMIC compositor/background with private config')
    parser.add_argument('--wallpaper-test', action='store_true', help='Native Studio wallpaper keyboard/focus checks in private lab')
    parser.add_argument('--snap-gui-test', action='store_true', help='Map installed Chromium Snap on the private compositor using an owned runtime socket')
    parser.add_argument('--snap-test', action='store_true', help='Launch installed Chromium Snap headless with an isolated profile through DeskMorph UI')
    parser.add_argument('--terminal-test', action='store_true', help='Launch a real terminal from the actual launcher in the private lab')
    parser.add_argument('--binary', type=Path, help='Use this executable for the launcher UI probe')
    args = parser.parse_args()
    if args.cosmic_test and (args.wallpaper_test or args.shortcut_test or args.terminal_test or args.snap_test or args.snap_gui_test or args.binary):
        parser.error('--cosmic-test requires its own run')
    if args.wallpaper_test and (args.shortcut_test or args.terminal_test or args.snap_test or args.snap_gui_test):
        parser.error('--wallpaper-test requires its own run')
    if (args.snap_test or args.snap_gui_test) and (args.shortcut_test or args.terminal_test):
        parser.error('--snap-test cannot be combined with shortcut or terminal modes')
    if args.terminal_test and args.shortcut_test:
        parser.error('--terminal-test cannot be combined with --shortcut-test')
    if args.binary and (not (args.launcher_test or args.terminal_test or args.snap_test or args.snap_gui_test or args.wallpaper_test) or args.shortcut_test):
        parser.error('--binary requires a launcher, terminal, or Snap mode and cannot be combined with --shortcut-test')
    if args.session: session(args.session)
    elif args.output: run(args.output.resolve(), args.prototype, args.launcher_test, args.shortcut_test, args.binary, args.terminal_test, args.snap_test, args.snap_gui_test, args.wallpaper_test, args.cosmic_test)
    else: parser.error('--output is required')
