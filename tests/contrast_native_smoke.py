#!/usr/bin/python3
"""Read-only native Dock backing pixels on the isolated DeskMorph process."""
import json
from pathlib import Path
import os
import signal
import subprocess
import time
from desktop_smoke import test_app
from dock_layout_smoke import descendants
from gi.repository import Gdk, Atspi


def capture(app, suffix):
    lock = subprocess.check_output(['gdbus','call','--session','--dest','org.gnome.ScreenSaver','--object-path','/org/gnome/ScreenSaver','--method','org.gnome.ScreenSaver.GetActive'],text=True)
    assert 'false' in lock, 'Desktop must be unlocked for native pixel evidence'
    root=Path('/tmp/deskmorph-desktop-test')
    config_path=root / 'config/com.ducthanhdev.deskmorph/config.json'
    original=config_path.read_bytes()
    frame=next(n for n in descendants(app) if n.get_role_name()=='frame' and n.get_name()=='DeskMorph Taskbar')
    time.sleep(2)  # Config, first stats and native content-width sizing must settle.
    observations=[]
    for label in ('clock','stats'):
        deadline=time.monotonic()+8
        node=None
        while time.monotonic()<deadline:
            node=next((n for n in descendants(frame) if
                       (label=='clock' and n.get_role_name()=='button' and n.get_name() in ('Mở lịch','Open calendar')) or
                       (label=='stats' and n.get_role_name()=='image' and n.get_name().startswith('CPU:'))),None)
            if node and node.get_state_set().contains(Atspi.StateType.SHOWING):
                break
            time.sleep(.2)
        assert node is not None, 'Test profile must enable clock/stats'
        def geometry():
            box=node.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
            return (box.x,box.y,box.width,box.height)
        previous=geometry();stable_since=time.monotonic();deadline=time.monotonic()+6
        while time.monotonic()-stable_since<.8:
            time.sleep(.1)
            current=geometry()
            if current!=previous:
                previous=current;stable_since=time.monotonic()
            assert time.monotonic()<deadline,'Control layout did not stabilize'
        rect=node.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        assert rect.width>0 and rect.height>0 and node.get_state_set().contains(Atspi.StateType.SHOWING)
        pixbuf=Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(),rect.x,rect.y,rect.width,rect.height)
        assert pixbuf is not None
        pixels=pixbuf.get_pixels();stride=pixbuf.get_rowstride();channels=pixbuf.get_n_channels()
        matches=sum(all(abs(pixels[y*stride+x*channels+c]-v)<=1 for c,v in enumerate((23,34,53))) for y in range(rect.height) for x in range(rect.width))
        screenshot=root/f'contrast-native-{suffix}-{label}.png';pixbuf.savev(str(screenshot),'png',[],[])
        from collections import Counter
        common=Counter(tuple(pixels[y*stride+x*channels+c] for c in range(3)) for y in range(rect.height) for x in range(rect.width)).most_common(5)
        assert matches>=30, (label,matches,rect.width,rect.height,common,str(screenshot))
        observations.append(dict(control=label,rect=[rect.x,rect.y,rect.width,rect.height],backingPixels=matches,expectedRGB=[23,34,53],screenshot=str(screenshot)))
    assert config_path.read_bytes()==original
    report=dict(pid=app.get_process_id(),observations=observations,configUnchanged=True,inputSent=False,scope='Actual X11 Dock root pixels for opaque information backing in enabled isolated profile, tolerance 1/channel; no claim of font raster contrast or full app coverage')
    return report

def run(app, config_home, start_app, set_app):
    path=Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original=path.read_bytes()
    pids=[]; reports=[]
    def stop():
        pid=test_app().get_process_id()
        assert pid==app.get_process_id()
        assert f'DESKMORPH_CONFIG_HOME={config_home}'.encode() in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
        os.kill(pid,signal.SIGTERM)
        deadline=time.monotonic()+7
        while Path(f'/proc/{pid}/stat').exists():
            try:
                if Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[0]=='Z':break
            except FileNotFoundError:break
            assert time.monotonic()<deadline,'Owned process did not stop'
            time.sleep(.1)
        try:os.waitpid(pid,os.WNOHANG)
        except ChildProcessError:pass
    def start():
        nonlocal app
        app=start_app();set_app(app);pids.append(app.get_process_id())
    try:
        for opacity in (.2,1):
            stop()
            fixture=json.loads(original)
            fixture['config'].update(autoHide=False,showClock=True,showStats=True,enabled=True,opacity=opacity)
            path.write_text(json.dumps(fixture))
            start();reports.append(capture(app,str(opacity)))
    finally:
        stop();path.write_bytes(original);start()
    report=dict(runs=reports,fixturePids=pids[:-1],normalPid=pids[-1],configRestored=path.read_bytes()==original)
    assert report['configRestored']
    (Path('/tmp/deskmorph-desktop-test')/'contrast-native-result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return app
