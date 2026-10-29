"""Verify icon pixels across launcher, pinned/unpinned Dock and native window list."""
import json
import os
from pathlib import Path
import re
import select
import shutil
import signal
import subprocess
import tempfile
import time
import gi
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Atspi, GdkPixbuf
from dock_layout_smoke import descendants, native_pixels


def run(app, config_home, click, focus_studio, native_keys, test_app, start_app, set_app):
    root = Path('/tmp/deskmorph-desktop-test')
    owned = Path(tempfile.mkdtemp(prefix='icon-render-', dir=root))
    config_path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = config_path.read_bytes()
    entries = owned / 'share/applications'; entries.mkdir(parents=True)
    absolute = owned / 'absolute.svg'
    absolute.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><path fill="#f125a9" d="M0 0h256v256H0z"/></svg>')
    theme_root = owned / 'share/icons/hicolor'
    (theme_root / '64x64/apps').mkdir(parents=True)
    (theme_root / 'index.theme').write_text('[Icon Theme]\nName=Hicolor\nDirectories=64x64/apps\n[64x64/apps]\nSize=64\nType=Fixed\nContext=Applications\n')
    png = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 64, 64)
    png.fill(0x1fdb57ff); png.savev(str(theme_root / '64x64/apps/deskmorph-render-test.png'), 'png', [], [])
    entry = entries / 'deskmorph-icon-probe.desktop'
    def write_entry(icon): entry.write_text('[Desktop Entry]\nType=Application\nName=DeskMorph Icon Probe\nExec=/bin/true\nStartupWMClass=DeskMorphIconRenderFixture\nIcon=' + str(icon) + '\n')
    write_entry(absolute)
    pin = dict(id='deskmorph-icon-probe.desktop', desktopId='deskmorph-icon-probe.desktop', name='DeskMorph Icon Probe',
               command='desktop:deskmorph-icon-probe.desktop', matchClasses=['deskmorphiconrenderfixture'], iconType='custom', enabled=True)
    env = {'XDG_DATA_DIRS': str(owned / 'share') + ':/usr/local/share:/usr/share'}
    fixture_process = None
    observations = []

    def stop():
        try: current = test_app()
        except RuntimeError: return
        pid = current.get_process_id(); assert pid == app.get_process_id()
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
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            value = predicate()
            if value: return value
            time.sleep(.1)
        raise AssertionError(message)
    def node(name): return next((n for n in descendants(app) if n.get_role_name() == 'button' and n.get_name() == name), None)
    def pixels(name, title, rgb):
        button = node(name)
        if not button: return 0
        clients = subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True)
        for xid in re.findall(r'0x[0-9a-fA-F]+', clients):
            props = subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID', '_NET_WM_NAME'], text=True)
            if not re.search(r'_NET_WM_PID.*= ' + str(app.get_process_id()) + r'\b', props) or f'= "{title}"' not in props: continue
            raw = subprocess.check_output(['xwininfo', '-id', xid], text=True)
            x, y, w, h = [int(re.search(re.escape(label) + r':\s*(-?\d+)', raw).group(1)) for label in ('Absolute upper-left X', 'Absolute upper-left Y', 'Width', 'Height')]
            rect = button.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
            left, top = max(0, rect.x-x), max(0, rect.y-y)
            width, height = min(w-left, rect.width), min(h-top, rect.height)
            if width <= 0 or height <= 0: return 0
            data, stride, size, offsets = native_pixels(xid, left, top, width, height)
            return sum(all(abs(data[row*stride+column*size+offset]-expected) <= 3 for offset, expected in zip(offsets, rgb)) for row in range(height) for column in range(width))
        return 0
    def sample(name, title, rgb, label):
        count = wait(lambda: (count if (count := pixels(name, title, rgb)) >= 100 else 0), 'Icon pixels missing: ' + label)
        observations.append({'surface': label, 'rgb': rgb, 'matchingPixels': count})
    def search():
        focus_studio(); click('Tìm ứng dụng')
        field = next(n for n in descendants(app) if n.get_role_name() == 'entry' and n.get_name() == 'Tìm ứng dụng')
        assert field.get_component_iface().grab_focus(); time.sleep(.2); native_keys(value='deskmorph icon probe')
        wait(lambda: node('Mở DeskMorph Icon Probe'), 'Icon app missing from launcher')
    try:
        stop()
        settings = json.loads(original)
        settings['config'].update(enabled=True, autoHide=False, position='top', language='vi', magnification=False, bouncingLaunch=False, reduceMotion=True, pinnedApps=[pin])
        config_path.write_text(json.dumps(settings))
        app = start_app(env_overrides=env); set_app(app)
        fixture_env = dict(os.environ, DESKMORPH_CONFIG_HOME=config_home, DESKMORPH_WINDOW_FIXTURE_CLASS='DeskMorphIconRenderFixture')
        fixture_process = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('desktop_smoke.py')), '--window-fixture'], env=fixture_env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        assert select.select([fixture_process.stdout], [], [], 8)[0], 'Fixture did not start'
        windows = json.loads(fixture_process.stdout.readline()); assert len(windows) == 3
        wait(lambda: node('DeskMorph Icon Probe • 3 cửa sổ'), 'Owned windows not grouped')
        for label, icon, rgb in [('absolute SVG', absolute, [241,37,169]), ('hicolor PNG', 'deskmorph-render-test', [31,219,87])]:
            write_entry(icon)
            focus_studio(); sample('DeskMorph Icon Probe • 3 cửa sổ', 'DeskMorph Taskbar', rgb, label + ' pinned Dock')
            search(); sample('Mở DeskMorph Icon Probe', 'DeskMorph Context Menu', rgb, label + ' launcher')
            native_keys(chord=[0xff1b]); focus_studio(); click('DeskMorph Icon Probe • 3 cửa sổ')
            sample('DeskMorph Window Test 1', 'DeskMorph Context Menu', rgb, label + ' window row')
            native_keys(chord=[0xff1b])
        search(); click('Bỏ ghim DeskMorph Icon Probe'); native_keys(chord=[0xff1b]); focus_studio()
        sample('DeskMorphIconRenderFixture • 3 cửa sổ', 'DeskMorph Taskbar', [31,219,87], 'hicolor PNG unpinned Dock')
        click('DeskMorphIconRenderFixture • 3 cửa sổ'); sample('DeskMorph Window Test 2', 'DeskMorph Context Menu', [31,219,87], 'hicolor PNG unpinned window row')
        native_keys(chord=[0xff1b])
        # Unknown names retain native windows and use the frontend SVG fallback.
        write_entry('deskmorph-missing-icon-name')
        search(); wait(lambda: pixels('Mở DeskMorph Icon Probe', 'DeskMorph Context Menu', [31,219,87]) == 0, 'Missing icon retained old image')
        assert node('Mở DeskMorph Icon Probe')
        native_keys(chord=[0xff1b])
        cache = root / 'cache/com.ducthanhdev.deskmorph/application-icons-v1'
        cached = list(cache.glob('*.png')); assert cached and len(cached) <= 512
        assert all(file.stat().st_size <= 32768 and max(GdkPixbuf.Pixbuf.get_file_info(str(file))[1:]) <= 64 for file in cached)
        report = {'pid': app.get_process_id(), 'fixturePid': fixture_process.pid, 'observations': observations,
                  'missingIconKeepsApplication': True, 'cachedFiles': len(cached), 'cacheBoundsVerified': True,
                  'scope': 'Native reference-scale X11 pixel checks; custom theme switching separately tested in private IconTheme'}
    finally:
        if fixture_process:
            if fixture_process.poll() is None: fixture_process.terminate()
            fixture_process.wait(timeout=5)
        stop(); config_path.write_bytes(original); shutil.rmtree(owned)
        app = start_app(); set_app(app)
    report.update(normalPid=app.get_process_id(), preferencesRestored=config_path.read_bytes() == original, fixturesRemoved=not owned.exists(), ownedWindowFixtureExited=fixture_process.poll() is not None)
    assert report['preferencesRestored'] and report['fixturesRemoved'] and report['ownedWindowFixtureExited']
    (root / 'icon-render-result.json').write_text(json.dumps(report, indent=2)); print(json.dumps(report))
    return app
