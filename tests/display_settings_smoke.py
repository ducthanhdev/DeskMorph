#!/usr/bin/python3
"""Owned native Display Settings UI, real read-only host topology, AT-SPI only.
Uses a temporary GIO display-settings fixture; never launches host Settings,
changes host topology or sends host keyboard/mouse input.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import gi
gi.require_version('Atspi','2.0')
from gi.repository import Atspi, Gio, GLib
from dock_layout_smoke import descendants
REPO=Path(__file__).resolve().parents[1]


def run(binary,output):
    root=Path(tempfile.mkdtemp(prefix='deskmorph-display-ui-'))
    profile=root/'config/com.ducthanhdev.deskmorph/config.json'
    profile.parent.mkdir(parents=True)
    apps=root/'data/applications';apps.mkdir(parents=True)
    fixture=root/'display_settings_fixture.py'
    fixture.write_text('from pathlib import Path\nPath('+repr(str(root/'settings-opened'))+').write_text("opened")\n')
    (apps/'gnome-display-panel.desktop').write_text('[Desktop Entry]\nType=Application\nName=Owned display settings fixture\nExec=/usr/bin/python3 '+str(fixture)+'\nNoDisplay=true\n')
    bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
    before=bus.call_sync('org.gnome.Mutter.DisplayConfig','/org/gnome/Mutter/DisplayConfig','org.gnome.Mutter.DisplayConfig','GetCurrentState',None,None,Gio.DBusCallFlags.NONE,5000,None).unpack()
    primary=next(group[5][0][0] for group in before[2] if group[4])
    report=dict(passed=False,binarySha256=hashlib.sha256(binary.read_bytes()).hexdigest(),hostInput=False,hostMutation=False,settingsFixture=True,runs=[])
    process=None
    def wait(fn,message):
        end=time.monotonic()+15
        while time.monotonic()<end:
            assert process.poll() is None,'Owned app exited'
            try:
                value=fn()
                if value:return value
            except GLib.Error:pass
            time.sleep(.15)
        raise AssertionError(message)
    def stop():
        if process and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=12)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
    try:
        for language in ('vi','en'):
            labels=json.loads((REPO/'src/i18n/messages.json').read_text())[language]
            cfg=json.loads((REPO/'src/config/defaults.json').read_text());cfg.update(language=language,enabled=False,launcherShortcut='',wallpaperScheduleEnabled=False)
            profile.write_text(json.dumps(dict(schemaVersion=1,revision=0,config=cfg,warning=None)))
            with (root/'app.log').open('a') as log:
                process=subprocess.Popen([str(binary)],cwd=REPO,env=dict(os.environ,DESKMORPH_CONFIG_HOME=str(root/'config'),XDG_DATA_HOME=str(root/'data'),WEBKIT_DISABLE_DMABUF_RENDERER='1'),stdout=log,stderr=log)
            def owned():
                desktop=Atspi.get_desktop(0)
                return next((desktop.get_child_at_index(i) for i in range(desktop.get_child_count()) if desktop.get_child_at_index(i).get_process_id()==process.pid),None)
            app=wait(owned,'Owned app inaccessible')
            def tree():return list(descendants(app))
            def button(name):return next((n for n in tree() if n.get_role_name()=='button' and n.get_name()==name),None)
            def action(node):
                assert node.get_application().get_process_id()==process.pid
                assert node.get_action_iface().do_action(0)
            action(wait(lambda:button(labels['displaysTab']),'Displays tab missing'))
            def text(node):
                value=node.get_text_iface()
                return node.get_name()+' '+(Atspi.Text.get_text(value,0,-1) if value else '')
            wait(lambda:any(labels['displayRecoveryUnverified'] in text(n) for n in tree()),'Capability explanation absent')
            primary_buttons=wait(lambda:[n for n in tree() if n.get_role_name()=='button' and n.get_name().endswith(labels['displayAlreadyPrimary'])],'Primary status missing')
            assert len(primary_buttons)==1
            for group in before[2]:
                suffix=labels['displayAlreadyPrimary'] if group[4] else labels['displaySetPrimary']
                node=wait(lambda:next((n for n in tree() if n.get_role_name()=='button' and n.get_name().endswith(suffix)),None),'Display status/action absent')
                assert not node.get_state_set().contains(Atspi.StateType.ENABLED),'Unverified mutation must be disabled'
            all_names=[n.get_name() for n in tree()]
            assert any(primary in name for name in all_names),'Primary connector absent'
            action(button(labels['displayRefresh']))
            wait(lambda:any(n.get_role_name()=='button' and n.get_name().endswith(labels['displayAlreadyPrimary']) for n in tree()),'Refresh failed')
            marker=root/'settings-opened'
            if marker.exists():marker.unlink()
            action(button(labels['displayOpenSettings']))
            wait(marker.exists,'GIO settings fixture did not launch')
            report['runs'].append(dict(language=language,primary=primary,logicalMonitors=len(before[2]),disabledMutation=True,refresh=True,gioSettingsFixture=True))
            stop()
        after=bus.call_sync('org.gnome.Mutter.DisplayConfig','/org/gnome/Mutter/DisplayConfig','org.gnome.Mutter.DisplayConfig','GetCurrentState',None,None,Gio.DBusCallFlags.NONE,5000,None).unpack()
        assert before==after,'Host display state changed during read-only UI test'
        report['hostStateUnchanged']=True
        report['passed']=True
    except Exception as e:
        import traceback
        report.update(error=repr(e),traceback=traceback.format_exc())
        if 'tree' in locals():
            try: report['ownedAccessibleText']=[dict(role=n.get_role_name(),name=n.get_name()) for n in tree() if n.get_name()][:160]
            except GLib.Error: pass
        raise
    finally:
        stop();report['ownedAppExited']=not process or process.poll() is not None
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(output,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true');parser.add_argument('--binary',type=Path,default=REPO/'src-tauri/target/agent/debug/deskmorph');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not args.run:parser.error('--run required')
    run(args.binary.resolve(),args.output.resolve())
