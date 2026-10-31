#!/usr/bin/python3
"""Opt-in native multi-Dock integration on the current X11 desktop.

Owns a temporary app profile/process only. AT-SPI actions target that PID;
no host mouse/keyboard injection, display layout or user configuration changes.
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

gi.require_version('Atspi', '2.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Atspi, Gdk, GLib
from dock_layout_smoke import descendants

REPO = Path(__file__).resolve().parents[1]


def run(binary):
    assert os.environ.get('XDG_SESSION_TYPE') == 'x11'
    display = Gdk.Display.get_default()
    monitors = []
    for i in range(display.get_n_monitors()):
        monitor = display.get_monitor(i)
        area = monitor.get_workarea()
        scale = monitor.get_scale_factor()
        monitors.append(dict(name=monitor.get_model(), scale=scale,
                             area=[v * scale for v in (area.x, area.y, area.width, area.height)]))
    assert len(monitors) >= 2, 'Requires at least two active monitors'
    root = Path(tempfile.mkdtemp(prefix='deskmorph-multidock-'))
    config = root / 'config/com.ducthanhdev.deskmorph/config.json'
    config.parent.mkdir(parents=True)
    report = dict(passed=False, binarySha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                  monitors=monitors, runs=[], hostInputSent=False, hostTopologyChanged=False,
                  scope='Owned native app on actual X11 monitors, AT-SPI settings/source actions; allocation, popup source routing and lifecycle; no real keyboard/mouse or hotplug acceptance')
    process = None
    app = None

    def wait(predicate, message, seconds=15):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            assert process.poll() is None, 'Owned app exited'
            try:
                value = predicate()
                if value:
                    return value
            except GLib.Error:
                pass  # Accessible documents can be replaced during mapping.
            time.sleep(.15)
        raise AssertionError(message)

    def start():
        nonlocal process, app
        with (root / 'app.log').open('a') as log:
            process = subprocess.Popen([str(binary)], cwd=REPO, env=dict(os.environ,
                DESKMORPH_CONFIG_HOME=str(root / 'config'), WEBKIT_DISABLE_DMABUF_RENDERER='1'), stdout=log, stderr=log)
        def owned():
            desktop = Atspi.get_desktop(0)
            return next((desktop.get_child_at_index(i) for i in range(desktop.get_child_count()) if desktop.get_child_at_index(i).get_process_id() == process.pid), None)
        app = wait(owned, 'Owned app not accessible')

    def stop():
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)

    def tree():
        assert app.get_process_id() == process.pid
        return list(descendants(app))

    def frames(title):
        return [n for n in tree() if n.get_role_name() == 'frame' and n.get_name() == title and n.get_state_set().contains(Atspi.StateType.SHOWING)]

    def rect(node):
        a = node.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        return [a.x, a.y, a.width, a.height]

    def action(node):
        assert node.get_application().get_process_id() == process.pid
        assert node.get_action_iface().do_action(0)
        time.sleep(.25)

    def select(label, option):
        combo = wait(lambda: next((n for n in tree() if n.get_role_name() == 'combo box' and n.get_name() == label), None), 'Combo absent: ' + label)
        target = next(n for n in descendants(combo) if n.get_role_name() == 'menu item' and n.get_name() == option)
        action(target)

    def docks(count, position, height=52):
        def settled():
            nodes = frames('DeskMorph Taskbar')
            if len(nodes) != count:
                return None
            areas = []
            for node in nodes:
                x,y,w,h = rect(node)
                target = next((m for m in monitors if m['area'][0] <= x < m['area'][0] + m['area'][2]), None)
                if not target:
                    return None
                ax,ay,aw,ah = target['area']; scale = target['scale']
                expected_y = ay + 16*scale if position == 'top' else ay + ah - (height+16)*scale
                if h != height*scale or abs(x+w/2-ax-aw/2) > 2 or abs(y-expected_y) > 2:
                    return None
                areas.append(target['name'])
            return nodes if len(set(areas)) == count else None
        result = wait(settled, f'Incorrect Dock count/geometry: {count}/{position}')
        time.sleep(.5)
        assert settled(), 'Dock geometry did not remain stable'
        return result

    try:
        for language in ('vi','en'):
            cfg = json.loads((REPO/'src/config/defaults.json').read_text())
            cfg.update(language=language, monitor='*', height=52, pinnedApps=[], reduceMotion=True,
                       autoHide=False, launcherShortcut='', wallpaperScheduleEnabled=False)
            config.write_text(json.dumps(dict(schemaVersion=1,revision=0,config=cfg,warning=None)))
            labels = json.loads((REPO/'src/i18n/messages.json').read_text())[language]
            start()
            record = dict(language=language, sourcePopups=[], transitions=[])
            report['runs'].append(record)
            for position in ('bottom','top'):
                if position == 'top':
                    select(labels['position'], labels['top'])
                nodes = docks(len(monitors), position)
                for node in nodes:
                    dock_rect = rect(node)
                    for source,title in ((labels['searchApps'],'DeskMorph Context Menu'),(labels['audio'],'DeskMorph Context Menu'),(labels['systemTools'],'DeskMorph Context Menu'),(labels['calendar'],'DeskMorph Calendar')):
                        button = next(n for n in descendants(node) if n.get_role_name() == 'button' and n.get_name() == source)
                        action(button)
                        popup = wait(lambda: next(iter(frames(title)), None), f'Source popup absent: {language}/{position}/{source}')
                        target = next(m for m in monitors if m['area'][0] <= dock_rect[0] < m['area'][0]+m['area'][2])
                        ax,ay,aw,ah = target['area']; scale=target['scale']
                        def anchored():
                            x,y,w,h = rect(popup)
                            source_rect=rect(button)
                            center=source_rect[0]+source_rect[2]/2
                            expected_x=max(ax+10,min(round(center)-w//2,ax+aw-w-10))
                            expected_y=max(ay+10,min(dock_rect[1]+dock_rect[3]+14 if position=='top' else dock_rect[1]-h-14,ay+ah-h-10))
                            return ax<=x and x+w<=ax+aw and ay<=y and y+h<=ay+ah and abs(x-expected_x)<=2 and abs(y-expected_y)<=2
                        assert scale == 1, 'This host input-free geometry probe currently requires scale1'
                        wait(anchored,'Popup not anchored to originating Dock')
                        record['sourcePopups'].append(dict(position=position,monitor=target['name'],source=source,popup=rect(popup)))
                        if title == 'DeskMorph Calendar':
                            action(button)
                            wait(lambda:not frames(title),'Calendar toggle failed to close')
            for option,expected,count in ((labels['primary'],None,1),(labels['allMonitors'],'*',len(monitors)),
                (next(n.get_name() for n in descendants(next(n for n in tree() if n.get_role_name()=='combo box' and n.get_name()==labels['monitor'])) if n.get_role_name()=='menu item' and n.get_name().startswith(monitors[-1]['name']+' •')),monitors[-1]['name'],1),
                (labels['allMonitors'],'*',len(monitors))):
                select(labels['monitor'],option)
                wait(lambda:json.loads(config.read_text())['config']['monitor']==expected,'Monitor selection not persisted')
                selected = docks(count,'top')
                if expected != '*':
                    target = next(m for m in monitors if m['name'] == expected) if expected else monitors[next((i for i in range(display.get_n_monitors()) if display.get_monitor(i).is_primary()), 0)]
                    assert target['area'][0] <= rect(selected[0])[0] < target['area'][0] + target['area'][2], 'Single Dock on wrong monitor'
                record['transitions'].append(dict(value=expected,count=count))
            # Disable/re-enable must affect every Dock in the process.
            toggle = next(n for n in tree() if n.get_role_name()=='check box' and n.get_name()==labels['enabled'])
            action(toggle); wait(lambda:not frames('DeskMorph Taskbar'),'Disable left a Dock mapped')
            action(toggle); docks(len(monitors),'top')
            record['disableEnableAll']=True
            stop(); start(); docks(len(monitors),'top'); record['restartPersistsAll']=True
            stop()
        report['passed']=True
    except Exception as error:
        import traceback
        report.update(error=repr(error),traceback=traceback.format_exc())
        raise
    finally:
        stop()
        report['ownedProcessExited']=process is None or process.poll() is not None
        (root/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(root/'result.json',flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--binary',type=Path,default=REPO/'src-tauri/target/agent/debug/deskmorph')
    args=parser.parse_args()
    if not args.run: parser.error('--run required')
    run(args.binary.resolve())
