"""GNOME X11 WM on the negative-origin runner's owned, drawable Xvfb screen.

Never use with the host DISPLAY/buses/settings. The context owns only its Shell;
the caller owns Xvfb, the session/a11y buses and the application processes.
"""
from contextlib import contextmanager
import ctypes
import os
from pathlib import Path
import re
import subprocess
import time


@contextmanager
def private_gnome_wm(root):
    root = Path(root).resolve()
    assert root.parent.parent == Path('/tmp') and root.parent.name.startswith('deskmorph-negative-origin-')
    assert os.environ.get('DESKMORPH_GEOMETRY_LAB') == str(root)
    assert os.environ['DISPLAY'] == (root / 'display').read_text()
    assert os.environ['GSETTINGS_BACKEND'] == 'keyfile'
    assert os.environ['DBUS_SYSTEM_BUS_ADDRESS'] == 'unix:path=' + str(root / 'no-system-bus')
    assert os.environ['DBUS_SESSION_BUS_ADDRESS'].startswith('unix:path=/tmp/')
    for name in ('XDG_RUNTIME_DIR', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME'):
        assert Path(os.environ[name]).resolve().is_relative_to(root)
    shell = None
    with (root / 'gnome-shell.log').open('w') as log:
        try:
            shell = subprocess.Popen(['gnome-shell', '--x11', '--replace'],
                env=dict(os.environ, LIBGL_ALWAYS_SOFTWARE='1',
                    DBUS_SYSTEM_BUS_ADDRESS=os.environ['DBUS_SESSION_BUS_ADDRESS'],
                    DESKMORPH_X11_WM_LAB=str(root)), stdout=log, stderr=log)
            deadline = time.monotonic() + 25
            while True:
                assert shell.poll() is None, 'Private GNOME Shell exited'
                props = subprocess.check_output(['xprop', '-root', '_NET_SUPPORTING_WM_CHECK'], text=True, timeout=5)
                ids = re.findall(r'0x[0-9a-f]+', props)
                if ids:
                    name = subprocess.check_output(['xprop', '-id', ids[0], '_NET_WM_NAME'], text=True, timeout=5)
                    if 'GNOME Shell' in name:
                        break
                assert time.monotonic() < deadline, 'Private WM readiness timed out'
                time.sleep(.15)
            time.sleep(3)
            assert shell.poll() is None, 'Private Shell failed during startup'
            # A newly started Shell enters overview. Dismiss it before opening
            # test windows, only on the private DISPLAY validated above.
            x11 = ctypes.CDLL('libX11.so.6')
            xtst = ctypes.CDLL('libXtst.so.6')
            x11.XOpenDisplay.restype = ctypes.c_void_p
            x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            x11.XKeysymToKeycode.restype = ctypes.c_uint
            x11.XFlush.argtypes = [ctypes.c_void_p]
            x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
            xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
            display = x11.XOpenDisplay(None)
            assert display
            try:
                key = x11.XKeysymToKeycode(display, 0xff1b)
                assert key
                assert xtst.XTestFakeKeyEvent(display, key, 1, 0)
                assert xtst.XTestFakeKeyEvent(display, key, 0, 0)
                x11.XFlush(display)
            finally:
                x11.XCloseDisplay(display)
            time.sleep(2)
            yield dict(pid=shell.pid, name='GNOME Shell', privateDisplay=True,
                       startupOverviewDismissed=True)
        finally:
            if shell is not None and shell.poll() is None:
                shell.terminate()
                try:
                    shell.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    shell.kill()
                    shell.wait(timeout=5)
