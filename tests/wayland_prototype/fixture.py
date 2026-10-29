#!/usr/bin/python3
"""Two owned native Wayland windows; no host display accepted."""
import os
from pathlib import Path
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, Gio

root = os.environ['DESKMORPH_COMPOSITOR_LAB']
assert root.startswith('/tmp/deskmorph-wayland-lab-')
assert os.environ['XDG_RUNTIME_DIR'] == root + '/runtime' and not os.environ.get('DISPLAY')
application = Gtk.Application(application_id='org.deskmorph.LabFixture', flags=Gio.ApplicationFlags.NON_UNIQUE)
def activate(app):
    assert isinstance(Gdk.Display.get_default(), Gdk.Display) and 'Wayland' in Gdk.Display.get_default().__class__.__name__
    for number in (1, 2):
        window = Gtk.ApplicationWindow(application=app, title='DeskMorph Wayland fixture ' + str(number))
        window.set_default_size(360, 220)
        window.add(Gtk.Label(label='Isolated native Wayland fixture ' + str(number)))
        window.show_all()
    Path(root + '/fixture-ready').write_text(str(os.getpid()))
application.connect('activate', activate)
application.run([])
