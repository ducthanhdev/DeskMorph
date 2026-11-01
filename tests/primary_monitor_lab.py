#!/usr/bin/python3
"""Opt-in primary-only GNOME policy spike on an owned headless compositor.
Never connects to the host bus/display or injects host input.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import secrets
import shutil
import subprocess
import tempfile
import time
from gi.repository import Gio, GLib
from wayland_lab import connection, call, owned_descendants, active
from mutter_scaling_probe import snapshot, configuration, topology

IFACE = 'org.gnome.Mutter.DisplayConfig'
OBJECT = '/org/gnome/Mutter/DisplayConfig'


def session(root):
    assert os.environ.get('DESKMORPH_COMPOSITOR_LAB') == str(root)
    assert os.environ['XDG_RUNTIME_DIR'] == str(root/'runtime')
    assert not os.environ.get('DISPLAY')
    (root/'bus').write_text(os.environ['DBUS_SESSION_BUS_ADDRESS'])
    os.execvp('gnome-shell', ['gnome-shell', '--headless', '--wayland', '--no-x11',
        '--virtual-monitor=1280x720', '--virtual-monitor=1024x768', '--wayland-display=primary-lab'])


def run(output):
    root = Path(tempfile.mkdtemp(prefix='deskmorph-primary-lab-'))
    for part in ('runtime','config','data','cache','home','state'):
        (root/part).mkdir(mode=0o700)
    env = dict(os.environ, DESKMORPH_COMPOSITOR_LAB=str(root), XDG_RUNTIME_DIR=str(root/'runtime'),
        XDG_CONFIG_HOME=str(root/'config'), XDG_DATA_HOME=str(root/'data'), XDG_CACHE_HOME=str(root/'cache'),
        XDG_STATE_HOME=str(root/'state'), HOME=str(root/'home'), XDG_SESSION_TYPE='wayland',
        XDG_CURRENT_DESKTOP='GNOME', GSETTINGS_BACKEND='keyfile', LIBGL_ALWAYS_SOFTWARE='1', WAYLAND_DISPLAY='primary-lab')
    env['DESKMORPH_PRIMARY_LAB_TOKEN'] = secrets.token_hex(32)
    for key in ('DISPLAY','DBUS_SESSION_BUS_ADDRESS','AT_SPI_BUS_ADDRESS','SESSION_MANAGER','XDG_SESSION_ID'):
        env.pop(key,None)
    report = dict(passed=False, policyCertified=False, hostMutation=False, hostInput=False, root=str(root), cases=[], scope='Primary-only VERIFY, TEMPORARY and persistent request with explicit GNOME Shell Keep/Revert on an owned headless compositor; persistence across a new desktop session and client crash recovery are not certified')
    process = None
    def stop_session(session):
        if not session:
            return
        try: os.killpg(session.pid, signal.SIGTERM)
        except ProcessLookupError: return
        try: session.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(session.pid, signal.SIGKILL)
            session.wait(timeout=5)
    def start_session():
        with (root/'session.log').open('a') as log:
            return subprocess.Popen(['dbus-run-session','--','/usr/bin/python3',str(Path(__file__).resolve()),'--session',str(root)],env=env,stdout=log,stderr=log,start_new_session=True)
    def wait_display(session):
        deadline=time.monotonic()+35
        while time.monotonic()<deadline:
            assert session.poll() is None, 'Owned compositor exited'
            try:
                owned_bus=connection((root/'bus').read_text())
                proxy=Gio.DBusProxy.new_sync(owned_bus,Gio.DBusProxyFlags.NONE,None,IFACE,OBJECT,IFACE,None)
                observed=snapshot(proxy)
                if len(observed['logicalMonitors'])==2:
                    return owned_bus, proxy, observed
            except (OSError,GLib.Error): pass
            time.sleep(.2)
        raise AssertionError('Private two-monitor compositor not ready')
    try:
        extension = root/'data/gnome-shell/extensions/deskmorph-primary-lab@deskmorph.local'
        extension.mkdir(parents=True)
        shutil.copyfile(Path(__file__).with_name('primary_monitor_extension.js'), extension/'extension.js')
        (extension/'metadata.json').write_text(json.dumps(dict(uuid='deskmorph-primary-lab@deskmorph.local', name='DeskMorph primary monitor lab', description='Private test only', version=1, **{'shell-version':['46']})))
        subprocess.run(['gsettings','set','org.gnome.shell','enabled-extensions',"['deskmorph-primary-lab@deskmorph.local']"],env=env,check=True)
        subprocess.run(['gsettings','set','org.gnome.shell','disable-user-extensions','false'],env=env,check=True)
        process = start_session()
        bus, proxy, before = wait_display(process)
        # Headless Shell can start before its extension manager observes the
        # keyfile. Enable only this extension on the owned session bus.
        call(bus, 'org.gnome.Shell.Extensions', '/org/gnome/Shell/Extensions',
            'org.gnome.Shell.Extensions', 'EnableExtension',
            GLib.Variant('(s)', ('deskmorph-primary-lab@deskmorph.local',)))
        end=time.monotonic()+5
        while time.monotonic()<end:
            try:
                exists=call(bus,'org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','NameHasOwner',GLib.Variant('(s)',('org.deskmorph.PrimaryLab',))).unpack()[0]
                if exists: break
            except GLib.Error: pass
            time.sleep(.1)
        else: raise AssertionError('Primary lab extension did not start')
        report['before']=topology(before)
        target=json.loads(json.dumps(before))
        for i,m in enumerate(target['logicalMonitors']): m['primary']=not before['logicalMonitors'][i]['primary']
        serial=snapshot(proxy)['configSerial']
        proxy.call_sync('ApplyMonitorsConfig',configuration(target,serial,0),Gio.DBusCallFlags.NONE,5000,None)
        report['cases'].append(dict(name='verify-primary-only',passed=True))
        proxy.call_sync('ApplyMonitorsConfig',configuration(target,snapshot(proxy)['configSerial'],1),Gio.DBusCallFlags.NONE,5000,None)
        observed=snapshot(proxy)
        assert topology(observed)==topology(target),'Temporary primary change did not preserve topology'
        report['cases'].append(dict(name='temporary-primary-only-preserves-layout',passed=True))
        proxy.call_sync('ApplyMonitorsConfig',configuration(before,observed['configSerial'],1),Gio.DBusCallFlags.NONE,5000,None)
        # Persistent requests use Shell's confirmation. First prove explicit
        # revert, then explicit keep; no virtual host input is involved.
        args=configuration(target,snapshot(proxy)['configSerial'],1)
        # Harness helper permits only 0/1; build method 2 explicitly for the isolated lab.
        payload=GLib.Variant.new_tuple(args.get_child_value(0),GLib.Variant('u',2),args.get_child_value(2),args.get_child_value(3))
        proxy.call_sync('ApplyMonitorsConfig',payload,Gio.DBusCallFlags.NONE,5000,None)
        assert topology(snapshot(proxy))==topology(target)
        report['cases'].append(dict(name='persistent-request-applies-preview',passed=True))
        pending=root/'confirmation-pending'
        end=time.monotonic()+5
        while time.monotonic()<end:
            if pending.exists(): break
            time.sleep(.25)
        else: raise AssertionError('GNOME Shell confirmation signal was not observed')
        call(bus,'org.deskmorph.PrimaryLab','/org/deskmorph/PrimaryLab','org.deskmorph.PrimaryLab','Complete',GLib.Variant('(sb)',(env['DESKMORPH_PRIMARY_LAB_TOKEN'],False)))
        end=time.monotonic()+5
        while time.monotonic()<end:
            if topology(snapshot(proxy))==topology(before): break
            time.sleep(.1)
        else: raise AssertionError('Explicit GNOME revert did not restore baseline')
        report['cases'].append(dict(name='shell-explicit-revert-restores-baseline',passed=True))
        pending.unlink()
        args=configuration(target,snapshot(proxy)['configSerial'],1)
        payload=GLib.Variant.new_tuple(args.get_child_value(0),GLib.Variant('u',2),args.get_child_value(2),args.get_child_value(3))
        proxy.call_sync('ApplyMonitorsConfig',payload,Gio.DBusCallFlags.NONE,5000,None)
        end=time.monotonic()+5
        while time.monotonic()<end:
            if pending.exists(): break
            time.sleep(.1)
        else: raise AssertionError('GNOME Shell keep confirmation was not observed')
        call(bus,'org.deskmorph.PrimaryLab','/org/deskmorph/PrimaryLab','org.deskmorph.PrimaryLab','Complete',GLib.Variant('(sb)',(env['DESKMORPH_PRIMARY_LAB_TOKEN'],True)))
        end=time.monotonic()+5
        while time.monotonic()<end:
            if topology(snapshot(proxy))==topology(target): break
            time.sleep(.1)
        else: raise AssertionError('Explicit GNOME keep did not retain target topology')
        report['cases'].append(dict(name='shell-explicit-keep-retains-target',passed=True))
        # A fresh private GNOME Shell process reads the same owned config. This
        # proves persistence across a compositor restart, not a host login.
        stop_session(process)
        process = start_session()
        _, _, restarted = wait_display(process)
        assert topology(restarted)==topology(target), 'Kept primary did not survive private Shell restart'
        report['cases'].append(dict(name='kept-primary-survives-shell-restart',passed=True))
        report['policyCertified']=True
        report['monitorsXmlPresent']=(root/'config/monitors.xml').exists()
        report['publicConfirmationObservation']='No confirmation result method/signal in DisplayConfig introspection; active topology alone cannot distinguish kept preview from persisted configuration.'
        report['passed']=True
    except Exception as e:
        import traceback
        report.update(error=repr(e),traceback=traceback.format_exc())
        raise
    finally:
        pids=owned_descendants(root)
        stop_session(process)
        for pid in pids:
            if active(pid):
                try: os.kill(pid,signal.SIGTERM)
                except ProcessLookupError: pass
        deadline=time.monotonic()+5
        while any(active(pid) for pid in pids) and time.monotonic()<deadline:
            time.sleep(.1)
        for pid in pids:
            if active(pid):
                try: os.kill(pid,signal.SIGKILL)
                except ProcessLookupError: pass
        deadline=time.monotonic()+3
        while any(active(pid) for pid in pids) and time.monotonic()<deadline:
            time.sleep(.1)
        report['ownedProcessesExited']=not any(active(pid) for pid in pids)
        report['passed']=report['passed'] and report['ownedProcessesExited']
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(output,flush=True)
        assert report['ownedProcessesExited'], 'Owned lab processes did not exit'

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--session',type=Path,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.session: session(args.session)
    elif args.run and args.output: run(args.output.resolve())
    else: parser.error('--run --output required')
