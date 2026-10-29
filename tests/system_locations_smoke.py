"""System actions through native UI with private desktop entries/XDG/MIME.

Only an owned GTK monitor fixture opens a window. Downloads/Trash receivers
record arguments without accessing host files. Associations stay private.
"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
from urllib.parse import unquote, urlparse
from gi.repository import Atspi, Gio
from dock_layout_smoke import descendants


def run(app, config_home, click, focus_studio, native_keys, test_app, start_app, set_app):
    root = Path('/tmp/deskmorph-desktop-test')
    owned = Path(tempfile.mkdtemp(prefix='system-locations-', dir=root))
    config_path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = config_path.read_bytes()
    apps = owned / 'data/applications'
    settings = owned / 'config'
    binaries = owned / 'bin'
    for directory in (apps, settings, binaries, owned / 'empty'):
        directory.mkdir(parents=True, exist_ok=True)
    for tool in ('xprop', 'pactl'):
        source = shutil.which(tool)
        if source:
            (binaries / tool).symlink_to(source)
    monitor_ids = ['org.gnome.SystemMonitor.desktop', 'gnome-system-monitor.desktop', 'org.gnome.Usage.desktop',
                   'org.kde.plasma-systemmonitor.desktop', 'plasma-systemmonitor.desktop', 'ksysguard.desktop']
    file_managers = [entry.get_id() for entry in Gio.AppInfo.get_all() if isinstance(entry, Gio.DesktopAppInfo)
                     and 'FileManager' in (entry.get_categories() or '').split(';')]
    def hide(desktop_id):
        assert desktop_id and '/' not in desktop_id
        (apps / desktop_id).write_text('[Desktop Entry]\nType=Application\nName=Hidden fixture\nExec=/bin/false\nHidden=true\n')
    for desktop_id in monitor_ids + file_managers:
        hide(desktop_id)
    receiver = owned / 'record receiver.py'
    receiver.write_text('''#!/usr/bin/python3
import json,os,sys
from pathlib import Path
root=Path(os.environ['DESKMORPH_SYSTEM_RECEIVER'])
mode=sys.argv[1]
data={'argv':sys.argv[2:],'pid':os.getpid()}
if mode=='monitor':
 import gi
 gi.require_version('Gtk','3.0');gi.require_version('GdkX11','3.0')
 from gi.repository import Gtk,GdkX11
 window=Gtk.Window(title='DeskMorph Owned System Monitor')
 window.set_wmclass('deskmorph-system-fixture','DeskMorphSystemFixture')
 window.add(Gtk.Label(label='Owned system monitor launch fixture'))
 window.connect('destroy',lambda *_:Gtk.main_quit())
 window.show_all()
 data['xid']=hex(GdkX11.X11Window.get_xid(window.get_window()))
 root.joinpath(mode+'.json').write_text(json.dumps(data))
 Gtk.main()
else:
 root.joinpath(mode+'.json').write_text(json.dumps(data))
''')
    receiver.chmod(0o700)
    # The private PATH has no terminal. The first monitor entry is detected
    # but GIO rejects its Terminal=true launch; the second opens owned GTK.
    (apps / monitor_ids[0]).write_text('[Desktop Entry]\nType=Application\nName=Primary monitor fixture\nExec=/bin/true\nTerminal=true\n')
    (apps / 'org.kde.plasma-systemmonitor.desktop').write_text('[Desktop Entry]\nType=Application\nName=Fallback monitor fixture\n'
        f'Exec=/usr/bin/python3 "{receiver}" monitor\n')
    manager_id = '000.deskmorph-system-files.desktop'
    (apps / manager_id).write_text('[Desktop Entry]\nType=Application\nName=Files receiver fixture\n'
        f'Exec=/usr/bin/python3 "{receiver}" files --profile "two words" %U\nCategories=FileManager;\nMimeType=inode/directory;\n')
    (apps / 'deskmorph-trash-receiver.desktop').write_text('[Desktop Entry]\nType=Application\nName=Trash receiver fixture\n'
        f'Exec=/usr/bin/python3 "{receiver}" trash %U\nMimeType=x-scheme-handler/trash;\n')
    downloads = owned / 'Downloaded files ; $(touch never)'
    downloads.mkdir()
    (settings / 'user-dirs.dirs').write_text(f'XDG_DOWNLOAD_DIR="{downloads}"\n')
    (settings / 'mimeapps.list').write_text('[Default Applications]\n'
        f'inode/directory={manager_id};\nx-scheme-handler/trash=deskmorph-trash-receiver.desktop;\n')
    sentinel = owned / 'data/Trash/files/sentinel.txt'
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text('preserve fixture trash')
    env = {'XDG_DATA_HOME': str(owned / 'data'), 'XDG_CONFIG_HOME': str(settings),
           'XDG_CONFIG_DIRS': str(owned / 'empty'), 'XDG_CACHE_HOME': str(owned / 'cache'),
           'PATH': str(binaries), 'DESKMORPH_SYSTEM_RECEIVER': str(owned)}
    fixture_pids, app_pids, passed = [], [], []

    def stopped(pid):
        stat = Path(f'/proc/{pid}/stat')
        try:
            return stat.read_text().rsplit(')', 1)[1].split()[0] == 'Z'
        except FileNotFoundError:
            return True

    def stop_app():
        try:
            current = test_app()
        except RuntimeError:
            return
        pid = current.get_process_id()
        assert pid == app.get_process_id()
        os.kill(pid, signal.SIGTERM)
        wait(lambda: stopped(pid), 'Owned app did not stop')
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass

    def start(overrides=None):
        nonlocal app
        app = start_app(env_overrides=overrides)
        set_app(app)
        app_pids.append(app.get_process_id())
        time.sleep(.8)  # Let initial toplevel focus/map callbacks finish before opening a popup.

    def wait(predicate, message):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            time.sleep(.15)
        raise AssertionError(message)

    def find(name):
        return next((node for node in descendants(app) if node.get_name() == name and node.get_role_name() == 'button'), None)

    def all_text():
        output = []
        for node in descendants(app):
            try:
                output.append(Atspi.Text.get_text(node, 0, -1))
            except Exception:
                pass
        return '\n'.join(output)

    def popup():
        focus_studio()
        if not find('Mở Downloads'):
            click('Tiện ích hệ thống', 'button')
        wait(lambda: find('Mở Downloads'), 'System actions missing')

    def enabled(name):
        node = find(name)
        return node.get_state_set().contains(Atspi.StateType.ENABLED) if node else None

    def read_marker(mode):
        marker = owned / (mode + '.json')
        wait(marker.exists, 'Missing launch receiver: ' + mode)
        data = json.loads(marker.read_text())
        if data['pid'] not in fixture_pids:
            fixture_pids.append(data['pid'])
        return data

    def stop_monitor():
        marker = owned / 'monitor.json'
        if not marker.exists():
            return
        pid = json.loads(marker.read_text())['pid']
        if stopped(pid):
            return
        cmd = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
        assert str(receiver).encode() in cmd and b'monitor' in cmd
        os.kill(pid, signal.SIGTERM)
        wait(lambda: stopped(pid), 'Owned monitor fixture survived cleanup')

    try:
        stop_app()
        fixture = json.loads(original)
        fixture['config'].update(enabled=True, showSystem=True, autoHide=False, language='vi')
        config_path.write_text(json.dumps(fixture))
        start(env)
        popup()
        wait(lambda: all(enabled(name) for name in ('Mở Downloads', 'Mở Thùng rác', 'Mở giám sát hệ thống')), 'Supported actions are disabled')
        click('Mở giám sát hệ thống')
        monitor = read_marker('monitor')
        props = subprocess.check_output(['xprop', '-id', monitor['xid'], '_NET_WM_NAME', '_NET_WM_PID'], text=True)
        assert 'DeskMorph Owned System Monitor' in props and str(monitor['pid']) in props
        stop_monitor()
        passed.append('detected primary launch rejected by GIO, fallback desktop ID opens owned GTK window')
        popup()
        click('Mở Downloads')
        files = read_marker('files')
        assert files['argv'][:2] == ['--profile', 'two words'] and len(files['argv']) == 3
        argument = files['argv'][2]
        actual = unquote(urlparse(argument).path) if argument.startswith('file://') else argument
        assert actual == str(downloads) and not (owned / 'never').exists()
        passed.append('XDG Downloads path and desktop argv preserved with spaces and literal shell characters')
        (owned / 'files.json').unlink()
        downloads.rmdir()
        click('Mở Downloads')
        wait(lambda: 'Thư mục Downloads theo XDG chưa tồn tại.' in all_text(), 'Missing directory did not show localized error')
        assert not downloads.exists() and not (owned / 'files.json').exists()
        downloads.mkdir()
        click('Mở Downloads')
        read_marker('files')
        passed.append('missing Downloads does not launch or create directory; click after restore retries successfully')
        click('Mở Thùng rác')
        trash = read_marker('trash')
        assert trash['argv'] == ['trash:///'] and sentinel.read_text() == 'preserve fixture trash'
        passed.append('Trash URI goes to private desktop handler; fixture trash contents preserved')
        stop_app()
        for desktop_id in monitor_ids + [manager_id, 'deskmorph-trash-receiver.desktop']:
            hide(desktop_id)
        start(env)
        popup()
        try:
            wait(lambda: all(enabled(name) is False for name in ('Mở Downloads', 'Mở Thùng rác', 'Mở giám sát hệ thống')), 'Missing capabilities leave active buttons')
        except AssertionError:
            frames = [node.get_name() for node in descendants(app) if node.get_role_name() == 'frame']
            active_window = subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)
            raise AssertionError('Missing capabilities: ' + json.dumps({name: enabled(name) for name in ('Mở Downloads', 'Mở Thùng rác', 'Mở giám sát hệ thống')}) + '\n' + repr(frames) + '\n' + active_window + '\n' + all_text())
        for message in ('Chưa tìm thấy ứng dụng quản lý tệp phù hợp.', 'Chưa tìm thấy trình xử lý Thùng rác trên desktop này.',
                        'Chưa tìm thấy ứng dụng giám sát hệ thống được hỗ trợ.'):
            assert message in all_text(), 'Missing capability reason: ' + message
        native_keys(chord=[0xff1b])
        passed.append('missing monitor, file manager and Trash handler disable actions and explain why')
        report = {'passed': passed, 'testPids': app_pids[:], 'fixturePids': fixture_pids[:],
                  'downloadsArgv': files['argv'], 'trashArgv': trash['argv'], 'monitorWindow': monitor,
                  'scope': 'Controlled desktop receivers through real IPC/GIO; not certification of third-party monitor packages or a production Trash browser.'}
    finally:
        stop_monitor()
        stop_app()
        config_path.write_bytes(original)
        shutil.rmtree(owned)
        start()
    report.update(normalPid=app.get_process_id(), preferencesRestored=config_path.read_bytes() == original, fixturesRemoved=not owned.exists())
    assert report['preferencesRestored'] and report['fixturesRemoved']
    (root / 'system-locations-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return app
