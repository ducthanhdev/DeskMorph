"""Guarded WM activation and XTest input for an owned private Xvfb session."""
import ctypes
import os
from pathlib import Path
import re
import subprocess
import time


class PrivateKeyboard:
    def __init__(self, root):
        self.root = Path(root).resolve()
        assert self.root.parent.parent == Path('/tmp') and self.root.parent.name.startswith('deskmorph-negative-origin-')
        assert os.environ['DESKMORPH_GEOMETRY_LAB'] == str(self.root)
        assert os.environ['DISPLAY'] == (self.root / 'display').read_text()
        self.x11 = x11 = ctypes.CDLL('libX11.so.6')
        self.xtst = xtst = ctypes.CDLL('libXtst.so.6')
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        x11.XInternAtom.restype = ctypes.c_ulong
        x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        x11.XKeysymToKeycode.restype = ctypes.c_uint
        x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]

    def owner(self, xid, pid):
        assert os.environ['DISPLAY'] == (self.root / 'display').read_text()
        props = subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID'], text=True, timeout=5)
        assert re.search(r'= ' + str(pid) + r'\b', props), 'Private input target is not owned'

    def active(self):
        props = subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True, timeout=5)
        return re.search(r'0x[0-9a-f]+', props).group(0)

    def activate(self, xid, pid):
        self.owner(xid, pid)
        if self.active() == xid:
            return
        class Message(ctypes.Structure):
            _fields_ = [('type', ctypes.c_int), ('serial', ctypes.c_ulong), ('sent', ctypes.c_int),
                ('display', ctypes.c_void_p), ('window', ctypes.c_ulong), ('message_type', ctypes.c_ulong),
                ('format', ctypes.c_int), ('data', ctypes.c_long * 5)]
        class Event(ctypes.Union):
            _fields_ = [('client', Message), ('pad', ctypes.c_long * 24)]
        x11 = self.x11
        x11.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long, ctypes.POINTER(Event)]
        connection = x11.XOpenDisplay(None)
        assert connection
        try:
            event = Event()
            event.client.type = 33
            event.client.sent = 1
            event.client.display = connection
            event.client.window = int(xid, 16)
            event.client.message_type = x11.XInternAtom(connection, b'_NET_ACTIVE_WINDOW', 0)
            event.client.format = 32
            event.client.data[0] = 2
            assert x11.XSendEvent(connection, x11.XDefaultRootWindow(connection), 0, (1 << 19) | (1 << 20), ctypes.byref(event))
            x11.XSync(connection, 0)
        finally:
            x11.XCloseDisplay(connection)
        deadline = time.monotonic() + 4
        while self.active() != xid:
            assert time.monotonic() < deadline, 'Private WM did not activate the owned window'
            time.sleep(.05)
        time.sleep(.15)

    def keys(self, xid, pid, chord):
        self.owner(xid, pid)
        assert self.active() == xid, 'Private keyboard focus changed; no input sent'
        connection = self.x11.XOpenDisplay(None)
        assert connection
        try:
            codes = [self.x11.XKeysymToKeycode(connection, key) for key in chord]
            assert all(codes)
            for code in codes:
                assert self.xtst.XTestFakeKeyEvent(connection, code, 1, 0)
            for code in reversed(codes):
                assert self.xtst.XTestFakeKeyEvent(connection, code, 0, 0)
            self.x11.XSync(connection, 0)
        finally:
            self.x11.XCloseDisplay(connection)
