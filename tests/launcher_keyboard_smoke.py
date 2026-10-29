"""Native launcher keyboard selection, empty results, launch error and retry."""
import json
import os
from pathlib import Path
import shutil
import signal
import tempfile
import time
from gi.repository import Atspi
from dock_layout_smoke import descendants


def run(app, config_home, click, focus_studio, native_keys, test_app, start_app, set_app):
    root = Path('/tmp/deskmorph-desktop-test')
    owned = Path(tempfile.mkdtemp(prefix='launcher-keyboard-', dir=root))
    config_path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = config_path.read_bytes()
    entries = owned / 'share/applications'
    entries.mkdir(parents=True)
    for index in (1, 2, 3):
        (entries / f'deskmorph-keyboard-{index}.desktop').write_text('[Desktop Entry]\nType=Application\n'
            f'Name=DeskMorph Keyboard {index}\nExec=/usr/bin/touch {owned / str(index)}\n')
    failing = owned / 'failure'
    def restore_executable():
        failing.write_text('#!/bin/sh\nexec /usr/bin/touch ' + str(owned / 'retry-launched') + '\n')
        failing.chmod(0o700)
    restore_executable()
    (entries / 'deskmorph-keyboard-fail.desktop').write_text('[Desktop Entry]\nType=Application\n'
        f'Name=DeskMorph Keyboard Fail\nExec={failing}\n')
    env = {'XDG_DATA_DIRS': str(owned / 'share') + ':/usr/local/share:/usr/share'}
    passed, observations = [], []

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
        raise AssertionError(message)
    def field(): return next((n for n in descendants(app) if n.get_role_name() == 'entry' and n.get_name() == 'Tìm ứng dụng' and n.get_state_set().contains(Atspi.StateType.SHOWING)), None)
    def has_text(value): return any(n.get_text_iface() and value in Atspi.Text.get_text(n.get_text_iface(), 0, -1) for n in descendants(app))
    def search(query):
        focus_studio(); click('Tìm ứng dụng')
        wait(field, 'Launcher entry not shown')
        assert field().get_component_iface().grab_focus()
        time.sleep(.2); native_keys(value=query)
        assert Atspi.Text.get_text(field().get_text_iface(), 0, -1) == query
        time.sleep(.4)
    try:
        stop()
        fixture = json.loads(original)
        fixture['config'].update(enabled=True, autoHide=False, language='vi', position='top', pinnedApps=[])
        config_path.write_text(json.dumps(fixture))
        app = start_app(env_overrides=env); set_app(app)
        initial_pid = app.get_process_id()
        search('deskmorph keyboard impossible')
        wait(lambda: has_text('Không tìm thấy ứng dụng phù hợp.'), 'Empty search state missing')
        native_keys(chord=[0xff1b]); wait(lambda: not field(), 'Escape did not dismiss launcher')
        passed.append('Dock logo opens searchable launcher; unmatched query and Escape dismissal')
        # Include Fail in the query results, then use End/Up to select numeric 3.
        for label, chords, expected in [
            ('down', [[0xff54]], 2),
            ('end then up', [[0xffe3, 0xff57], [0xff52]], 3),
            ('home', [[0xff54], [0xffe3, 0xff50]], 1),
            ('wrap up then up', [[0xff52], [0xff52]], 3),
        ]:
            for index in (1, 2, 3): (owned / str(index)).unlink(missing_ok=True)
            search('deskmorph keyboard')
            for chord in chords: native_keys(chord=chord)
            native_keys(chord=[0xff0d])
            wait(lambda: (owned / str(expected)).exists(), 'Wrong keyboard-selected desktop ID: ' + label)
            assert [index for index in (1, 2, 3) if (owned / str(index)).exists()] == [expected]
            wait(lambda: not field(), 'Successful launch did not dismiss launcher')
            observations.append({'keys': label, 'launched': expected})
        passed.append('ArrowDown/ArrowUp/wrap/CtrlHome/CtrlEnd plus Enter launch exact desktop IDs')
        search('deskmorph keyboard fail')
        wait(lambda: any(n.get_name() == 'Mở DeskMorph Keyboard Fail' for n in descendants(app)), 'Failing app absent before executable removal')
        failing.unlink()
        native_keys(chord=[0xff0d])
        wait(lambda: field() and any(n.get_name() == 'Thử lại' for n in descendants(app)), 'Native launch error did not keep launcher and retry')
        assert has_text('app_missing') or has_text('app_launch_failed')
        assert not (owned / 'retry-launched').exists()
        restore_executable(); click('Thử lại')
        wait(lambda: (owned / 'retry-launched').exists() and not field(), 'Retry did not launch restored executable and dismiss')
        passed.append('native missing executable error remains visible; retry after restore launches same desktop ID')
        report = {'pid': initial_pid, 'passed': passed, 'keyboard': observations,
                  'scope': 'Owned native fixtures; in-flight Enter lock and loading/scan-error rendering verified in real component with controlled IPC'}
    finally:
        stop()
        config_path.write_bytes(original)
        shutil.rmtree(owned)
        app = start_app(); set_app(app)
    report.update(normalPid=app.get_process_id(), preferencesRestored=config_path.read_bytes() == original, fixturesRemoved=not owned.exists())
    assert report['preferencesRestored'] and report['fixturesRemoved']
    (root / 'launcher-keyboard-result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    return app
