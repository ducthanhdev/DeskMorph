"""Preserve legacy argv while explicit desktop identities launch via GIO."""
import json
import os
from pathlib import Path
import shutil
import signal
import tempfile
import time
from dock_layout_smoke import descendants


def run(app, config_home, click, focus_studio, native_keys, native_click, test_app, start_app, set_app):
    root = Path('/tmp/deskmorph-desktop-test')
    owned = Path(tempfile.mkdtemp(prefix='pin-identity-', dir=root))
    config_path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = config_path.read_bytes()
    entries = owned / 'share/applications'
    entries.mkdir(parents=True)
    script = owned / 'launch probe.py'
    events = owned / 'events.jsonl'
    script.write_text('import json, os, sys\nfrom pathlib import Path\n'
                      f'with Path({str(events)!r}).open("a") as log:\n'
                      '    log.write(json.dumps({"argv": sys.argv[1:], "config": os.environ.get("DESKMORPH_CONFIG_HOME")}) + "\\n")\n')
    pins = []
    for mode in ('legacy', 'desktop'):
        desktop_id = f'deskmorph-identity-{mode}.desktop'
        cls = 'DeskMorphIdentity' + mode.title()
        (entries / desktop_id).write_text('[Desktop Entry]\nType=Application\n'
            f'Name=DeskMorph Identity {mode}\nExec=/usr/bin/python3 "{script}" desktop-{mode}\nStartupWMClass={cls}\n')
        pin = dict(id='identity-' + mode, name='DeskMorph Identity ' + mode,
                   command=f'/usr/bin/python3 "{script}" legacy-{mode} "two words" "literal ; $(touch never)"',
                   matchClasses=[cls], iconType='custom', enabled=True)
        if mode == 'desktop': pin['desktopId'] = desktop_id
        pins.append(pin)
    env = {'XDG_DATA_DIRS': str(owned / 'share') + ':/usr/local/share:/usr/share'}

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

    def read_events(): return [json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []

    def wait(predicate, message):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(.1)
        raise AssertionError(message)

    def dock_node(mode):
        name = f'DeskMorph Identity {mode} • 0 cửa sổ'
        return next((n for n in descendants(app) if n.get_role_name() == 'button' and n.get_name() == name), None)

    observations = []
    try:
        stop()
        fixture = json.loads(original)
        fixture['config'].update(enabled=True, autoHide=False, language='vi', position='top',
                                 reduceMotion=True, magnification=False, bouncingLaunch=False, pinnedApps=pins)
        config_path.write_text(json.dumps(fixture))
        app = start_app(env_overrides=env); set_app(app)
        initial_pid = app.get_process_id()
        for mode in ('legacy', 'desktop'):
            wait(lambda: dock_node(mode), 'Fixture pin missing')
            # Opening the launcher proves the legacy mapping still resolves its
            # metadata while the persisted command remains authoritative.
            focus_studio(); click('Tìm ứng dụng')
            field = next(n for n in descendants(app) if n.get_role_name() == 'entry' and n.get_name() == 'Tìm ứng dụng')
            assert field.get_component_iface().grab_focus()
            time.sleep(.2); native_keys(value='deskmorph identity ' + mode)
            wait(lambda: any(n.get_name() == 'Bỏ ghim DeskMorph Identity ' + mode for n in descendants(app)), 'Pin not recognized by catalogue identity')
            native_keys(chord=[0xff1b])
            for action in ('left', 'middle', 'context'):
                before = len(read_events())
                focus_studio()
                native_click(dock_node(mode), button=3 if action == 'context' else 2 if action == 'middle' else 1)
                if action == 'context': click('Mở ứng dụng')
                wait(lambda: len(read_events()) == before + 1, 'Launch did not produce one event')
                event = read_events()[-1]
                expected = ['legacy-legacy', 'two words', 'literal ; $(touch never)'] if mode == 'legacy' else ['desktop-desktop']
                assert event['argv'] == expected, (mode, action, event)
                assert event['config'] == config_home
                observations.append({'mode': mode, 'action': action, 'argv': event['argv']})
        assert json.loads(config_path.read_text())['config']['pinnedApps'] == pins
        stop()
        app = start_app(env_overrides=env); set_app(app)
        wait(lambda: all(dock_node(mode) for mode in ('legacy', 'desktop')), 'Pins did not survive restart')
        assert json.loads(config_path.read_text())['config']['pinnedApps'] == pins
        report = {'initialPid': initial_pid, 'restartPid': app.get_process_id(), 'observations': observations,
                  'pinsPreservedAfterRestart': True, 'scope': 'Owned native command/desktop fixtures, no existing user app launch'}
    finally:
        stop()
        config_path.write_bytes(original)
        shutil.rmtree(owned)
        app = start_app(); set_app(app)
    report.update(normalPid=app.get_process_id(), preferencesRestored=config_path.read_bytes() == original,
                  fixturesRemoved=not owned.exists())
    assert report['preferencesRestored'] and report['fixturesRemoved']
    (root / 'pin-identity-result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    return app
