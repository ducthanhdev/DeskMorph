#!/usr/bin/python3
"""Owned GTK applications for native desktop-entry launch tests."""
import json
import os
from pathlib import Path
import sys
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('GdkX11', '3.0')
from gi.repository import Gio, Gtk, GdkX11

assert os.environ.get('DESKMORPH_CONFIG_HOME') == '/tmp/deskmorph-desktop-test/config'
mode = sys.argv[1]
assert mode in ('multi', 'single', 'action')
log = Path('/tmp/deskmorph-desktop-test/launch-events.jsonl')

def record(**event):
    with log.open('a') as stream:
        stream.write(json.dumps(dict(pid=os.getpid(), mode=mode, **event)) + '\n')

if mode == 'action':
    record(event='action', arguments=sys.argv[2:])
    raise SystemExit(0)

app = Gtk.Application(application_id='org.deskmorph.LaunchFixture.' + mode,
                      flags=Gio.ApplicationFlags.NON_UNIQUE if mode == 'multi' else Gio.ApplicationFlags.FLAGS_NONE)

def activate(application):
    window = application.get_active_window()
    if window is None:
        window = Gtk.ApplicationWindow(application=application, title='DeskMorph Launch ' + mode)
        window.set_wmclass('deskmorph-launch-' + mode, 'DeskMorphLaunch' + mode.title())
        window.set_default_size(300, 150)
        window.add(Gtk.Label(label='Launch fixture: ' + mode))
        window.show_all()
    window.present()
    record(event='activate', xid=hex(GdkX11.X11Window.get_xid(window.get_window())))

app.connect('activate', activate)
raise SystemExit(app.run([sys.argv[0]]))
