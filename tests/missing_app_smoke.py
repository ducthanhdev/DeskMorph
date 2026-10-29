"""Retain unavailable pins, restore them live, and unpin explicitly on native UI."""
import json
import os
from pathlib import Path
import shutil
import signal
import tempfile
import time
from gi.repository import Atspi
from dock_layout_smoke import descendants


def run(app, config_home, click, focus_studio, native_keys, native_click, test_app, start_app, set_app):
    root = Path('/tmp/deskmorph-desktop-test')
    owned = Path(tempfile.mkdtemp(prefix='missing-app-', dir=root))
    config_path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = config_path.read_bytes()
    entries = owned / 'share/applications'
    entries.mkdir(parents=True)
    pins, files = [], []
    for mode in ('explicit', 'alias'):
        desktop_id = f'deskmorph-missing-{mode}.desktop'
        pin = dict(id='missing-' + mode, name='DeskMorph Missing ' + mode.title(), command='desktop:' + desktop_id,
                   matchClasses=['deskmorphmissing' + mode], iconType='custom', enabled=True)
        if mode == 'explicit': pin['desktopId'] = desktop_id
        pins.append(pin)
        file = entries / desktop_id
        body = '[Desktop Entry]\nType=Application\n' + f'Name={pin["name"]}\nExec=/usr/bin/touch {owned / (mode + "-launched")}\nStartupWMClass=DeskMorphMissing{mode}\n'
        file.write_text(body)
        files.append((file, body))
    env = {'XDG_DATA_DIRS': str(owned / 'share') + ':/usr/local/share:/usr/share'}
    unavailable = 'Ứng dụng không còn trong danh mục'
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
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(.1)
        raise AssertionError(message)
    def buttons(): return [n for n in descendants(app) if n.get_role_name() == 'button']
    def node(name): return next((n for n in buttons() if n.get_name() == name), None)
    def dock(pin, missing=False): return node(pin['name'] + ' • 0 cửa sổ' + (' • ' + unavailable if missing else ''))
    def pin_list(): return json.loads(config_path.read_text())['config']['pinnedApps']
    def has_text(text): return any(n.get_text_iface() and text in Atspi.Text.get_text(n.get_text_iface(), 0, -1) for n in descendants(app))

    try:
        stop()
        fixture = json.loads(original)
        fixture['config'].update(enabled=True, autoHide=False, language='vi', position='top',
                                 magnification=False, bouncingLaunch=False, reduceMotion=True, pinnedApps=pins)
        config_path.write_text(json.dumps(fixture))
        app = start_app(env_overrides=env); set_app(app)
        initial_pid = app.get_process_id()
        wait(lambda: all(dock(pin) for pin in pins), 'Installed pins not available')
        for file, _ in files: file.unlink()
        wait(lambda: all(dock(pin, True) for pin in pins), 'Uninstall did not label both desktop identity formats')
        assert pin_list() == pins
        passed.append('uninstall updates Dock status for explicit and command-only desktop IDs without deleting pins')
        focus_studio(); native_click(dock(pins[0], True), button=3)
        wait(lambda: node('Mở ứng dụng') and has_text(unavailable), 'Missing status absent from context menu')
        assert not node('Mở ứng dụng').get_state_set().contains(Atspi.StateType.SENSITIVE)
        assert node('Bỏ ghim').get_state_set().contains(Atspi.StateType.SENSITIVE)
        passed.append('missing menu disables launch and keeps unpin available')
        for file, body in files: file.write_text(body)
        wait(lambda: all(dock(pin) for pin in pins) and node('Mở ứng dụng').get_state_set().contains(Atspi.StateType.SENSITIVE), 'Reinstall did not restore live Dock/menu')
        click('Mở ứng dụng')
        wait(lambda: (owned / 'explicit-launched').exists(), 'Restored menu did not launch desktop entry')
        assert pin_list() == pins
        passed.append('reinstall restores live menu and Dock launch with original pins')
        for file, _ in files: file.unlink()
        wait(lambda: all(dock(pin, True) for pin in pins), 'Second uninstall not observed')
        stop(); app = start_app(env_overrides=env); set_app(app)
        restart_pid = app.get_process_id()
        wait(lambda: all(dock(pin, True) for pin in pins), 'Unavailable pins did not survive restart')
        assert pin_list() == pins
        focus_studio(); click('Ứng dụng')
        wait(lambda: has_text(unavailable) and node('Bỏ ghim ' + pins[1]['name']), 'Studio unavailable pin state missing')
        passed.append('missing pins survive restart and remain manageable in Studio')
        focus_studio(); native_click(dock(pins[0], True), button=3); click('Bỏ ghim')
        wait(lambda: pin_list() == [pins[1]], 'Context unpin removed wrong pin')
        focus_studio(); click('Ứng dụng'); click('Bỏ ghim ' + pins[1]['name'])
        wait(lambda: pin_list() == [], 'Studio unpin did not remove remaining unavailable pin')
        passed.append('explicit context and Studio unpin remove only selected unavailable pin')
        report = {'initialPid': initial_pid, 'restartPid': restart_pid, 'passed': passed,
                  'scope': 'Owned desktop entry uninstall/reinstall fixtures; temporary scan errors covered by frontend hook test'}
    finally:
        stop()
        config_path.write_bytes(original)
        shutil.rmtree(owned)
        app = start_app(); set_app(app)
    report.update(normalPid=app.get_process_id(), preferencesRestored=config_path.read_bytes() == original, fixturesRemoved=not owned.exists())
    assert report['preferencesRestored'] and report['fixturesRemoved']
    (root / 'missing-app-result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    return app
