"""Native unpinned context/actions keyboard checks using a private catalogue."""
import json
import os
from pathlib import Path
import select
import shutil
import signal
import subprocess
import tempfile
import time
from gi.repository import Atspi
from dock_layout_smoke import descendants


def run(app, config_home, focus_studio, native_keys, start_app, set_app):
    root = Path('/tmp/deskmorph-desktop-test')
    owned = Path(tempfile.mkdtemp(prefix='context-actions-', dir=root))
    path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = path.read_bytes()
    desktop_id = 'deskmorph-context-actions.desktop'
    entries = owned / 'share/applications'
    entries.mkdir(parents=True)
    default_marker, action_marker = owned / 'default', owned / 'action'
    (entries / desktop_id).write_text('[Desktop Entry]\nType=Application\nName=DeskMorph Context Actions\n'
        f'Exec=/usr/bin/touch {default_marker}\nStartupWMClass=DeskMorphContextActions\nActions=Mark;\n'
        f'[Desktop Action Mark]\nName=DeskMorph Keyboard Action\nExec=/usr/bin/touch {action_marker}\n')
    fixtures, app_pids, runs = [], [], []

    def stop():
        proc = Path(f'/proc/{app.get_process_id()}')
        if not proc.exists(): return
        assert f'DESKMORPH_CONFIG_HOME={config_home}'.encode() in (proc / 'environ').read_bytes().split(b'\0')
        os.kill(app.get_process_id(), signal.SIGTERM)
        deadline = time.monotonic() + 7
        while proc.exists():
            try:
                if (proc / 'stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z': break
            except FileNotFoundError: break
            assert time.monotonic() < deadline, 'Owned context action app did not stop'
            time.sleep(.1)

    def start(extra=None):
        nonlocal app
        app = start_app(env_overrides=extra); set_app(app); app_pids.append(app.get_process_id())

    def wait(predicate, message):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            value = predicate()
            if value: return value
            time.sleep(.1)
        raise AssertionError(message)

    def frame(title):
        return next((n for n in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == title), None)

    def buttons():
        return [n for n in descendants(frame('DeskMorph Context Menu')) if n.get_role_name() == 'button']

    def button(label): return next((n for n in buttons() if n.get_name() == label), None)
    def focused(node): return node.get_state_set().contains(Atspi.StateType.FOCUSED)
    def config(): return json.loads(path.read_text())['config']

    def open_menu():
        focus_studio('DeskMorph Taskbar')
        source = wait(lambda: next((n for n in descendants(frame('DeskMorph Taskbar')) if n.get_role_name() == 'button' and n.get_name().startswith(('DeskMorph Context Actions', 'DeskMorphContextActions'))), None), 'Owned action fixture group missing')
        assert source.get_component_iface().grab_focus()
        wait(lambda: focused(source), 'Unpinned source not focused')
        native_keys(chord=[0xffe1, 0xffc7])
        wait(lambda: button('DeskMorph Keyboard Action'), 'Desktop action missing from owned context')

    def enter(label):
        node = wait(lambda: button(label), 'Context button missing: ' + label)
        assert node.get_component_iface().grab_focus()
        wait(lambda: focused(node), 'Context button did not focus: ' + label)
        native_keys(chord=[0xff0d])
        wait(lambda: frame('DeskMorph Context Menu') is None, 'Successful context action did not dismiss')

    try:
        for language in ('vi', 'en'):
            stop()
            cfg = json.loads(original)
            cfg['config'].update(language=language, enabled=True, autoHide=False, showApps=True)
            assert not any(pin.get('desktopId') == desktop_id for pin in cfg['config']['pinnedApps'])
            path.write_text(json.dumps(cfg))
            before = config()
            fixture = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('desktop_smoke.py')), '--window-fixture'],
                env=dict(os.environ, DESKMORPH_CONFIG_HOME=config_home, DESKMORPH_WINDOW_FIXTURE_CLASS='DeskMorphContextActions'),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            fixtures.append(fixture)
            assert select.select([fixture.stdout], [], [], 5)[0], 'Action fixture not ready'
            state = json.loads(fixture.stdout.readline())
            assert set(state) == {'1', '2', '3'}
            start({'XDG_DATA_DIRS': str(owned / 'share') + ':/usr/local/share:/usr/share'})
            for marker in (default_marker, action_marker): marker.unlink(missing_ok=True)
            try:
                open_menu()
                enabled = [n for n in buttons() if n.get_state_set().contains(Atspi.StateType.ENABLED) and n.get_state_set().contains(Atspi.StateType.SENSITIVE)]
                wait(lambda: focused(enabled[0]), 'Unpinned menu initial focus missing')
                sequence = []
                for index, node in enumerate(enabled):
                    wait(lambda: focused(node), 'Wrong unpinned Tab target: ' + node.get_name())
                    sequence.append(node.get_name()); assert sequence[-1].strip()
                    if index + 1 < len(enabled): native_keys(chord=[0xff09])
                for node in reversed(enabled[:-1]):
                    native_keys(chord=[0xffe1, 0xff09])
                    wait(lambda: focused(node), 'Wrong unpinned reverse Tab target')
                enter('DeskMorph Keyboard Action')
                wait(action_marker.exists, 'Keyboard desktop action did not write its exact marker')
                assert not default_marker.exists(), 'Desktop action invoked the default command'
                open_menu(); enter('Mở ứng dụng' if language == 'vi' else 'Open application')
                wait(default_marker.exists, 'Keyboard default action did not run')
                open_menu(); enter('Ghim' if language == 'vi' else 'Pin')
                wait(lambda: any(pin.get('desktopId') == desktop_id for pin in config()['pinnedApps']), 'Keyboard pin did not persist desktop ID')
                open_menu(); enter('Bỏ ghim' if language == 'vi' else 'Unpin')
                wait(lambda: config() == before, 'Keyboard unpin did not restore original config fields')
                assert fixture.poll() is None, 'Action test unexpectedly stopped fixture windows'
                runs.append(dict(language=language, pid=app.get_process_id(), fixturePid=fixture.pid,
                    tabSequence=sequence, reverseMatches=True, exactDesktopActionMarker=True,
                    defaultLaunchMarker=True, keyboardPinUnpin=True, configFieldsRestored=True))
            finally:
                if fixture.poll() is None: fixture.terminate()
                fixture.wait(timeout=5)
    finally:
        for fixture in fixtures:
            if fixture.poll() is None: fixture.terminate()
            fixture.wait(timeout=5)
        stop(); path.write_bytes(original); shutil.rmtree(owned); start()
    report = dict(runs=runs, fixtureAppPids=app_pids[:-1], normalPid=app_pids[-1],
        configBytesRestored=path.read_bytes() == original, privateCatalogueRemoved=not owned.exists(),
        scope='Native GNOME X11 vi/en, owned unpinned group, Shift+F10/Tab both directions and Enter default/desktop-action/pin/unpin; AT-SPI seeds action focus, no user application launches')
    assert report['configBytesRestored'] and report['privateCatalogueRemoved']
    (root / 'context-desktop-actions-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return app
