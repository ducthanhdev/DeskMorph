#!/usr/bin/python3
"""Isolated MPRIS fixture; never controls an existing player."""
import argparse
import json
import sys
from pathlib import Path
import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib

parser = argparse.ArgumentParser()
parser.add_argument('--name', required=True)
parser.add_argument('--identity', required=True)
parser.add_argument('--log', required=True)
parser.add_argument('--artwork', default='')
parser.add_argument('--can-next', action='store_true')
args = parser.parse_args()
assert args.name.startswith('org.mpris.MediaPlayer2.deskmorph_test_')
path = '/org/mpris/MediaPlayer2'
interface = 'org.mpris.MediaPlayer2.Player'
state = {'PlaybackStatus': GLib.Variant('s', 'Playing'),
         'CanControl': GLib.Variant('b', True), 'CanPlay': GLib.Variant('b', True),
         'CanPause': GLib.Variant('b', True), 'CanGoNext': GLib.Variant('b', args.can_next), 'CanGoPrevious': GLib.Variant('b', True),
         'Metadata': GLib.Variant('a{sv}', {'xesam:title': GLib.Variant('s', args.identity + ' Track'), 'xesam:artist': GLib.Variant('as', ['Fixture Artist']), 'mpris:artUrl': GLib.Variant('s', args.artwork)})}
xml = '''<node><interface name="org.mpris.MediaPlayer2"><property name="Identity" type="s" access="read"/></interface>
<interface name="org.mpris.MediaPlayer2.Player"><method name="Play"/><method name="Pause"/><method name="Next"/><method name="Previous"/>
<property name="PlaybackStatus" type="s" access="read"/><property name="CanControl" type="b" access="read"/>
<property name="CanPlay" type="b" access="read"/><property name="CanPause" type="b" access="read"/>
<property name="CanGoNext" type="b" access="read"/><property name="CanGoPrevious" type="b" access="read"/><property name="Metadata" type="a{sv}" access="read"/>
</interface></node>'''
connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
connection.set_exit_on_close(False)
def emit(changed):
    connection.emit_signal(None, path, 'org.freedesktop.DBus.Properties', 'PropertiesChanged', GLib.Variant('(sa{sv}as)', (interface, changed, [])))
def method(conn, sender, object_path, iface, method_name, params, invocation):
    with Path(args.log).open('a') as out: out.write(json.dumps({'method': method_name}) + '\n')
    if method_name in ('Play', 'Pause'):
        state['PlaybackStatus'] = GLib.Variant('s', 'Playing' if method_name == 'Play' else 'Paused')
        emit({'PlaybackStatus': state['PlaybackStatus']})
    invocation.return_value(GLib.Variant('()', ()))
def get_property(conn, sender, object_path, iface, key):
    return GLib.Variant('s', args.identity) if key == 'Identity' else state.get(key)
for info in Gio.DBusNodeInfo.new_for_xml(xml).interfaces:
    connection.register_object(path, info, method, get_property, None)
def ready(*unused):
    Path(args.log + '.ready').write_text('ready')
def lost(*unused):
    raise SystemExit('Fixture name lost')
Gio.bus_own_name_on_connection(connection, args.name, Gio.BusNameOwnerFlags.NONE, ready, lost)
def command(source, condition):
    line = source.readline()
    if not line: return False
    payload = json.loads(line)
    if 'title' in payload:
        state['Metadata'] = GLib.Variant('a{sv}', {'xesam:title': GLib.Variant('s', payload['title'])})
        emit({'Metadata': state['Metadata']})
    return True
GLib.io_add_watch(sys.stdin, GLib.IO_IN, command)
GLib.MainLoop().run()
