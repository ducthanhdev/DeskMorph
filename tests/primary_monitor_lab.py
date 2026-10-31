#!/usr/bin/python3
"""Opt-in primary-only GNOME policy spike on an owned headless compositor.
Never connects to the host bus/display or injects host input.
"""
import argparse
import json
import os
from pathlib import Path
import signal
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
        XDG_CURRENT_DESKTOP='GNOME', GSETTINGS_BACKEND='memory', LIBGL_ALWAYS_SOFTWARE='1', WAYLAND_DISPLAY='primary-lab')
    for key in ('DISPLAY','DBUS_SESSION_BUS_ADDRESS','AT_SPI_BUS_ADDRESS','SESSION_MANAGER','XDG_SESSION_ID'):
        env.pop(key,None)
    report = dict(passed=False, policyCertified=False, hostMutation=False, hostInput=False, root=str(root), cases=[], scope='Primary-only VERIFY, TEMPORARY and persistent request auto-revert on an owned headless compositor; keep, persistence and client crash recovery are not certified')
    process = None
    try:
        with (root/'session.log').open('w') as log:
            process = subprocess.Popen(['dbus-run-session','--','/usr/bin/python3',str(Path(__file__).resolve()),'--session',str(root)],env=env,stdout=log,stderr=log,start_new_session=True)
        deadline=time.monotonic()+35
        while time.monotonic()<deadline:
            assert process.poll() is None, 'Owned compositor exited'
            try:
                bus=connection((root/'bus').read_text())
                proxy=Gio.DBusProxy.new_sync(bus,Gio.DBusProxyFlags.NONE,None,IFACE,OBJECT,IFACE,None)
                before=snapshot(proxy)
                if len(before['logicalMonitors'])==2: break
            except (OSError,GLib.Error): pass
            time.sleep(.2)
        else: raise AssertionError('Private two-monitor compositor not ready')
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
        # Persistent requests use the compositor confirmation timeout.
        args=configuration(target,snapshot(proxy)['configSerial'],1)
        # Harness helper permits only 0/1; build method 2 explicitly for the isolated lab.
        payload=GLib.Variant.new_tuple(args.get_child_value(0),GLib.Variant('u',2),args.get_child_value(2),args.get_child_value(3))
        proxy.call_sync('ApplyMonitorsConfig',payload,Gio.DBusCallFlags.NONE,5000,None)
        assert topology(snapshot(proxy))==topology(target)
        report['cases'].append(dict(name='persistent-request-applies-preview',passed=True))
        end=time.monotonic()+27
        while time.monotonic()<end:
            if topology(snapshot(proxy))==topology(before): break
            time.sleep(.25)
        else: raise AssertionError('Persistent preview did not auto-revert in 27 seconds')
        report['cases'].append(dict(name='compositor-auto-revert-without-confirm',passed=True))
        report['monitorsXmlPresent']=(root/'config/monitors.xml').exists()
        report['publicConfirmationObservation']='No confirmation result method/signal in DisplayConfig introspection; active topology alone cannot distinguish kept preview from persisted configuration.'
        report['passed']=True
    except Exception as e:
        import traceback
        report.update(error=repr(e),traceback=traceback.format_exc())
        raise
    finally:
        pids=owned_descendants(root)
        if process:
            try: os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError: pass
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: os.killpg(process.pid,signal.SIGKILL); process.wait(timeout=5)
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
