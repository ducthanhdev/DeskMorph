"""Verify production startup discovers an omitted Flatpak export and launches its ID."""
import json
import os
from pathlib import Path
import signal
import time
from dock_layout_smoke import descendants


def run(app, config_home, click, focus_studio, native_keys, test_app, start_app, set_app):
    root = Path('/tmp/deskmorph-desktop-test')
    config_path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = config_path.read_bytes()
    export = root / 'data/flatpak/exports/share'
    desktop = export / 'applications/deskmorph-export-probe.desktop'
    marker = root / 'export-probe-launched'
    assert not desktop.exists() and not marker.exists(), 'Refuse to overwrite existing fixtures'
    desktop.parent.mkdir(parents=True, exist_ok=True)
    desktop.write_text('[Desktop Entry]\nType=Application\nName=DeskMorph Export Probe\n'
                       f'Exec=/usr/bin/touch {marker}\nIcon=utilities-terminal\n')
    def stop_owned():
        try: current = test_app()
        except RuntimeError: return
        assert current.get_process_id() == app.get_process_id()
        pid = current.get_process_id()
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 6
        while Path(f'/proc/{pid}').exists():
            try:
                if Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z': break
            except FileNotFoundError: break
            if time.monotonic() > deadline: raise AssertionError('Isolated app did not stop')
            time.sleep(.1)
        try: os.waitpid(pid, os.WNOHANG)
        except ChildProcessError: pass
    report = None
    try:
        stop_owned()
        app = start_app(env_overrides={'XDG_DATA_DIRS': '/usr/local/share:/usr/share',
                                      'FLATPAK_USER_DIR': str(root / 'data/flatpak')})
        set_app(app)
        startup_env = Path(f'/proc/{app.get_process_id()}/environ').read_bytes().split(b'\0')
        assert b'XDG_DATA_DIRS=/usr/local/share:/usr/share' in startup_env
        focus_studio(); click('Taskbar Studio')
        if json.loads(config_path.read_text())['config']['autoHide']:
            click('Tự động ẩn Dock Chạm cạnh màn hình để hiện lại; Dock giữ hiện khi bạn thao tác popup.')
        click('Tìm ứng dụng')
        entry = next(n for n in descendants(app) if n.get_name() == 'Tìm ứng dụng' and n.get_role_name() == 'entry')
        assert entry.get_component_iface().grab_focus()
        time.sleep(.2); native_keys(value='deskmorph export probe')
        time.sleep(.8)
        matches = [n for n in descendants(app) if n.get_role_name() == 'button' and n.get_name() == 'Mở DeskMorph Export Probe']
        assert len(matches) == 1, [(n.get_role_name(), n.get_name()) for n in descendants(app) if 'Export' in (n.get_name() or '')]
        click('Mở DeskMorph Export Probe')
        deadline = time.monotonic() + 5
        while not marker.exists():
            if time.monotonic() > deadline: raise AssertionError('Export desktop-ID launch did not create marker')
            time.sleep(.1)
        report = {'pid': app.get_process_id(), 'startupDataDirs': '/usr/local/share:/usr/share',
                  'export': str(export), 'passed': ['production startup export fallback', 'one desktop-ID result', 'launcher desktop-ID launch marker'],
                  'scope': 'Owned export-layout fixture; not a packaged Flatpak or Snap runtime'}
    finally:
        stop_owned()
        config_path.write_bytes(original)
        desktop.unlink()
        marker.unlink(missing_ok=True)
        app = start_app()
        set_app(app)
    report['normalPid'] = app.get_process_id()
    report['preferencesRestored'] = config_path.read_bytes() == original
    assert report['preferencesRestored']
    (root / 'exports-result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    return app
