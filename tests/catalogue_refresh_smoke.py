"""Live GIO -> IPC -> React catalogue changes, including first export installation."""
import json
import os
from pathlib import Path
import shutil
import signal
import tempfile
import time
from gi.repository import GLib
from dock_layout_smoke import descendants


def run(app, config_home, click, focus_studio, native_keys, test_app, start_app, set_app):
    root = Path('/tmp/deskmorph-desktop-test')
    owned = Path(tempfile.mkdtemp(prefix='catalogue-refresh-', dir=root))
    export = owned / 'flatpak/exports/share/applications'
    entry = export / 'deskmorph-refresh-probe.desktop'
    config_path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = config_path.read_bytes()
    observations = []

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

    def results():
        try: return [n.get_name() for n in descendants(app) if n.get_role_name() == 'button' and n.get_name().startswith('Mở DeskMorph Refresh Probe')]
        except GLib.GError: return None

    def wait_result(expected, label):
        started = time.monotonic()
        while time.monotonic() - started < 12:
            if results() == expected:
                observations.append({'case': label, 'seconds': round(time.monotonic() - started, 3), 'results': expected})
                return
            time.sleep(.1)
        raise AssertionError(f'{label}: expected {expected}, got {results()}')

    def replace(name, hidden=False):
        temporary = entry.with_suffix('.tmp')
        temporary.write_text('[Desktop Entry]\nType=Application\n'
                             f'Name=DeskMorph Refresh Probe {name}\nExec=/bin/true\nHidden={str(hidden).lower()}\n')
        temporary.replace(entry)

    try:
        stop()
        fixture_config = json.loads(original)
        fixture_config['config'].update(enabled=True, autoHide=False, language='vi')
        config_path.write_text(json.dumps(fixture_config))
        app = start_app(env_overrides={'FLATPAK_USER_DIR': str(owned / 'flatpak'),
                                      'XDG_DATA_DIRS': '/usr/local/share:/usr/share'})
        set_app(app)
        assert not export.exists()
        focus_studio(); click('Tìm ứng dụng')
        field = next(n for n in descendants(app) if n.get_role_name() == 'entry' and n.get_name() == 'Tìm ứng dụng')
        assert field.get_component_iface().grab_focus()
        time.sleep(.2); native_keys(value='deskmorph refresh probe')
        time.sleep(.6); wait_result([], 'initially absent export')
        export.mkdir(parents=True)
        replace('Installed')
        wait_result(['Mở DeskMorph Refresh Probe Installed'], 'first installation without restart or manual refresh')
        replace('Renamed')
        wait_result(['Mở DeskMorph Refresh Probe Renamed'], 'atomic entry rename')
        replace('Hidden', hidden=True)
        wait_result([], 'Hidden tombstone removes result')
        replace('Restored')
        wait_result(['Mở DeskMorph Refresh Probe Restored'], 'entry restored')
        click('Làm mới')
        wait_result(['Mở DeskMorph Refresh Probe Restored'], 'explicit refresh preserves current entry')
        entry.unlink()
        wait_result([], 'uninstall removes result')
        native_keys(chord=[0xff1b])
        replace('Reopened')
        time.sleep(.3)
        focus_studio(); click('Tìm ứng dụng')
        field = next(n for n in descendants(app) if n.get_role_name() == 'entry' and n.get_name() == 'Tìm ứng dụng')
        assert field.get_component_iface().grab_focus()
        time.sleep(.2); native_keys(value='deskmorph refresh probe')
        wait_result(['Mở DeskMorph Refresh Probe Reopened'], 'reopened consumer receives changed catalogue')
        report = {'pid': app.get_process_id(), 'observations': observations, 'scope': 'Live owned export fixtures, no host package installation'}
    finally:
        stop()
        config_path.write_bytes(original)
        shutil.rmtree(owned)
        app = start_app()
        set_app(app)
    report.update(normalPid=app.get_process_id(), preferencesRestored=config_path.read_bytes() == original, fixturesRemoved=not owned.exists())
    assert report['preferencesRestored'] and report['fixturesRemoved']
    (root / 'catalogue-refresh-result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    return app
