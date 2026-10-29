"""Pin/unpin through launcher, repair duplicate old IDs, and launch from Dock."""
import json
import os
from pathlib import Path
import shutil
import signal
import tempfile
import time
from dock_layout_smoke import descendants
from gi.repository import Atspi


def run(app, config_home, click, focus_studio, native_keys, test_app, start_app, set_app):
    root = Path('/tmp/deskmorph-desktop-test')
    owned = Path(tempfile.mkdtemp(prefix='pinning-', dir=root))
    config_path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = config_path.read_bytes()
    backups_before = set(config_path.parent.glob('*.recovery.json'))
    entries = owned / 'share/applications'
    entries.mkdir(parents=True)
    marker = owned / 'launched'
    desktop_id = 'deskmorph-pinning-probe.desktop'
    (entries / desktop_id).write_text('[Desktop Entry]\nType=Application\nName=DeskMorph Pin Probe\n'
        f'Exec=/usr/bin/touch {marker}\nStartupWMClass=DeskMorphPinProbe\n')
    old = dict(id='old-pinning-id', name='DeskMorph Custom Pin Name', command='desktop:' + desktop_id,
               matchClasses=['deskmorphpinprobe'], iconType='custom', enabled=False)
    duplicate = dict(old, id=desktop_id, desktopId=desktop_id, name='Duplicate old version pin')
    fixture = json.loads(original)
    fixture['config'].update(enabled=True, autoHide=False, language='vi', position='top',
                             magnification=False, bouncingLaunch=False, pinnedApps=[old, duplicate])
    fixture_bytes = json.dumps(fixture).encode()
    env = {'XDG_DATA_DIRS': str(owned / 'share') + ':/usr/local/share:/usr/share'}
    passed = []

    def stop():
        try: current = test_app()
        except RuntimeError: return
        pid = current.get_process_id()
        assert pid == app.get_process_id()
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 6
        while Path(f'/proc/{pid}').exists():
            try:
                if Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z': break
            except FileNotFoundError: break
            if time.monotonic() > deadline: raise AssertionError('Owned app did not exit')
            time.sleep(.1)
        try: os.waitpid(pid, os.WNOHANG)
        except ChildProcessError: pass

    def wait(predicate, message):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(.1)
        details = [(n.get_role_name(), n.get_name(), Atspi.Text.get_text(n.get_text_iface(), 0, -1) if n.get_text_iface() else '') for n in descendants(app)]
        raise AssertionError(message + ': ' + repr(details[-65:]))

    def pin_list(): return json.loads(config_path.read_text())['config']['pinnedApps']
    def names(): return [n.get_name() for n in descendants(app) if n.get_role_name() in ('button', 'toggle button')]
    def search():
        focus_studio(); click('Tìm ứng dụng')
        field = next(n for n in descendants(app) if n.get_role_name() == 'entry' and n.get_name() == 'Tìm ứng dụng')
        assert field.get_component_iface().grab_focus()
        time.sleep(.2); native_keys(value='deskmorph pin probe')
        wait(lambda: any(name in names() for name in ('Ghim DeskMorph Pin Probe', 'Bỏ ghim DeskMorph Pin Probe')), 'Pin fixture not found')
    def launch(name):
        marker.unlink(missing_ok=True)
        focus_studio(); click(name + ' • 0 cửa sổ')
        wait(marker.exists, 'Dock did not launch desktop ID')

    try:
        stop()
        config_path.write_bytes(fixture_bytes)
        app = start_app(env_overrides=env); set_app(app)
        initial_pid = app.get_process_id()
        backups = set(config_path.parent.glob('*.recovery.json')) - backups_before
        assert len(backups) == 1 and all(path.read_bytes() == fixture_bytes for path in backups)
        search()
        assert 'Ghim DeskMorph Pin Probe' in names()
        click('Ghim DeskMorph Pin Probe')
        wait(lambda: pin_list() == [dict(old, enabled=True)], 'Re-enabling old identity duplicated or replaced its metadata')
        wait(lambda: 'Bỏ ghim DeskMorph Pin Probe' in names(), 'Pin state did not synchronize in launcher')
        passed.append('duplicate old desktop identities repaired with recovery copy; pin re-enables original ID/name')
        native_keys(chord=[0xff1b])
        launch(old['name'])
        passed.append('Dock launches re-enabled desktop pin')
        stop(); app = start_app(env_overrides=env); set_app(app)
        first_restart = app.get_process_id()
        assert pin_list() == [dict(old, enabled=True)]
        search(); click('Bỏ ghim DeskMorph Pin Probe')
        wait(lambda: pin_list() == [], 'Unpin did not remove original legacy ID')
        wait(lambda: 'Ghim DeskMorph Pin Probe' in names(), 'Launcher did not reflect unpin')
        click('Ghim DeskMorph Pin Probe')
        wait(lambda: len(pin_list()) == 1 and pin_list()[0].get('desktopId') == desktop_id, 'Fresh canonical pin missing or duplicated')
        canonical = pin_list()
        assert canonical[0]['id'] == desktop_id and canonical[0]['command'] == 'desktop:' + desktop_id
        native_keys(chord=[0xff1b]); launch('DeskMorph Pin Probe')
        passed.append('unpin removes old ID; re-pin creates one canonical desktop ID and launches from Dock')
        stop(); app = start_app(env_overrides=env); set_app(app)
        assert pin_list() == canonical
        search()
        assert names().count('Bỏ ghim DeskMorph Pin Probe') == 1
        passed.append('both legacy and canonical pins survive restart with one launcher pin action')
        report = {'initialPid': initial_pid, 'firstRestartPid': first_restart, 'secondRestartPid': app.get_process_id(),
                  'passed': passed, 'recoveryOriginalVerified': True, 'scope': 'Owned desktop fixture and isolated config only'}
    finally:
        stop()
        config_path.write_bytes(original)
        for path in set(config_path.parent.glob('*.recovery.json')) - backups_before:
            assert path.read_bytes() == fixture_bytes, 'Refuse to remove an unrelated recovery document'
            path.unlink()
        shutil.rmtree(owned)
        app = start_app(); set_app(app)
    report.update(normalPid=app.get_process_id(), preferencesRestored=config_path.read_bytes() == original,
                  fixturesRemoved=not owned.exists())
    assert report['preferencesRestored'] and report['fixturesRemoved']
    (root / 'pinning-result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    return app
