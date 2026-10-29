"""Native repaired-config warning and translated import review; owned profile only."""
import json
import os
from pathlib import Path
import signal
import re
import subprocess
import gi
gi.require_version("Gdk", "3.0")
gi.require_version("GdkX11", "3.0")
from gi.repository import Gdk, GdkX11
import time
from gi.repository import Atspi, GLib


def descendants(node):
    """A chooser can remove its AX subtree while a snapshot is being walked."""
    if node is None: return
    yield node
    try:
        children = [node.get_child_at_index(i) for i in range(node.get_child_count())]
    except GLib.Error:
        return
    for child in children:
        yield from descendants(child)


def run(app, config_home, click, focus_studio, native_keys, test_app, start_app, set_app, native_click_node):
    root = Path('/tmp/deskmorph-desktop-test')
    path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = path.read_bytes()
    recovery_before = set(path.parent.glob('*.recovery.json'))
    review_file = root / 'localized-review.json'
    pids, passed, layouts, long_ranges = [], [], [], []
    long_name = "Tên_ứng_dụng_rất_dài_" * 15

    def wait(predicate, message):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(.1)
        raise AssertionError(message + '\n' + text()[-3500:])

    def text():
        result = []
        for node in descendants(app):
            try: result.append(node.get_name() or '')
            except Exception: continue  # File chooser teardown can invalidate a copied AX node.
            try: result.append(Atspi.Text.get_text(node.get_text_iface(), 0, -1))
            except Exception: pass
        return '\n'.join(result)

    def stopped(pid):
        try: return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z'
        except FileNotFoundError: return True

    def stop():
        pid = app.get_process_id()
        assert test_app().get_process_id() == pid
        assert f'DESKMORPH_CONFIG_HOME={config_home}'.encode() in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
        os.kill(pid, signal.SIGTERM)
        wait(lambda: stopped(pid), 'Owned app did not exit')
        try: os.waitpid(pid, os.WNOHANG)
        except ChildProcessError: pass

    def start():
        nonlocal app
        app = start_app(); set_app(app); pids.append(app.get_process_id()); focus_studio()

    try:
        stop()
        document = json.loads(original)
        document['config'].update(language='en', height='invalid fixture value', enabled=True, autoHide=False, wallpaperScheduleEnabled=False)
        document['config']['pinnedApps'] = [dict(id='localization-long-name', name=long_name, command='/bin/true', iconType='custom', matchClasses=[])] + document['config']['pinnedApps']
        document['warning'] = None
        path.write_text(json.dumps(document))
        start()
        wait(lambda: 'Some configuration fields were repaired or reset to defaults' in text(), 'Repaired config warning not translated to English')
        assert 'Một số trường cấu hình được sửa' not in text(), 'Vietnamese raw warning leaked into English summary'
        assert len(set(path.parent.glob('*.recovery.json')) - recovery_before) == 1
        click('System'); click('Tiếng Việt')
        wait(lambda: 'Một số trường cấu hình được sửa hoặc dùng giá trị mặc định' in text(), 'Retained warning did not translate to Vietnamese')
        assert json.loads(path.read_text())['warning'] == 'config_repaired'
        passed.append('real invalid-height config recovers with a backup; stable warning persists and translates en/vi live')

        # Native restart must retain language and warning, independent of WebView state.
        stop(); start()
        wait(lambda: 'Một số trường cấu hình được sửa' in text(), 'Warning or language lost after native restart')
        click('Hệ thống'); click('English')
        wait(lambda: 'Some configuration fields were repaired' in text(), 'Warning did not recover English after restart')
        passed.append('native restart retains language and translatable warning code')

        snapshot = json.loads(path.read_text())
        review_config = dict(snapshot['config'], keepDockOnClose=not snapshot['config']['keepDockOnClose'],
                             wallpaperFolders=['/tmp/' + 'long-folder-name-' * 18])
        review_file.write_text(json.dumps(dict(schemaVersion=1, config=review_config)))
        click('Import configuration'); focus_studio('Select File')
        native_keys(chord=[0xffe3, ord('l')]); native_keys(value=str(review_file)); click('Open', 'button')
        wait(lambda: 'Review changes before importing' in text(), 'Import review not shown')
        wait(lambda: 'Keep Dock when Studio closes' in text() and 'Saved wallpaper folders' in text(), 'Review field labels not translated')
        assert 'keepDockOnClose' not in text() and 'wallpaperFolders' not in text(), 'Internal field names leaked into review'
        assert review_config['wallpaperFolders'][0] in text(), 'Long path data truncated in review'
        expected = 'On' if review_config['keepDockOnClose'] else 'Off'
        assert expected in text(), 'Boolean review value not translated'
        assert json.loads(path.read_text()) == snapshot, 'Review changed persisted data before approval'
        click('Tiếng Việt')
        wait(lambda: 'Thư mục hình nền đã lưu' in text() and 'Xem thay đổi trước khi nhập' in text(), 'Open review did not translate live')
        click('Hủy')
        assert json.loads(path.read_text())['config']['wallpaperFolders'] == snapshot['config']['wallpaperFolders'], 'Cancel applied reviewed folders'
        passed.append('open import review translates fields/scalar values en/vi, preserves long path and cancels without applying data')

        catalogue = json.loads((Path(__file__).resolve().parents[1] / 'src/i18n/messages.json').read_text())
        clients = re.findall(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True))
        xid = None
        for candidate in clients:
            props = subprocess.check_output(['xprop', '-id', candidate, '_NET_WM_PID', '_NET_WM_NAME'], text=True)
            if re.search(r'_NET_WM_PID.*= ' + str(app.get_process_id()) + r'\b', props) and '"DeskMorph Studio"' in props:
                xid = int(candidate, 16); break
        assert xid is not None
        display = Gdk.Display.get_default() or Gdk.Display.open(os.environ['DISPLAY'])
        window = GdkX11.X11Window.foreign_new_for_display(display, xid)
        def dimensions():
            info = subprocess.check_output(['xwininfo', '-id', hex(xid)], text=True)
            return tuple(int(re.search(r'\b' + key + r': (\d+)', info).group(1)) for key in ('Width', 'Height'))
        def layout(language, tab):
            frame = next(n for n in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Studio')
            bounds = frame.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
            checked = 0
            for node in descendants(frame):
                if node.get_role_name() not in ('button', 'check box', 'combo box', 'entry', 'slider') or not node.get_state_set().contains(Atspi.StateType.SHOWING): continue
                rect = node.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
                if rect.width <= 0 or rect.height <= 0 or rect.y < bounds.y or rect.y + rect.height > bounds.y + bounds.height: continue
                assert rect.x >= bounds.x - 2 and rect.x + rect.width <= bounds.x + bounds.width + 2, f'Horizontal overflow {language}/{tab}: {node.get_name()[:100]} rect={rect} frame={bounds}'
                checked += 1
            assert checked >= 5
            layouts.append(dict(language=language, tab=tab, windowSize=dimensions(), visibleControlsChecked=checked))
        for width, height in ((800, 600), (1280, 800)):
            window.resize(width, height); Gdk.flush()
            wait(lambda: dimensions() == (width, height), 'Owned Studio did not resize')
            for language in ('en', 'vi'):
                focus_studio(); click('Hệ thống' if json.loads(path.read_text())['config']['language'] == 'vi' else 'System')
                click('English' if language == 'en' else 'Tiếng Việt')
                labels = catalogue[language]
                for tab in ('dockTab', 'appsTab', 'appearanceTab', 'wallpaperTab', 'systemTab'):
                    click(labels[tab]); layout(language, tab)
                assert any(n.get_role_name() == 'button' and n.get_name().startswith(labels['defaultFiles'] + ' • ') for n in descendants(app)), 'Default Files Dock name did not translate'
                click(labels['appsTab'])
                assert long_name in text(), 'Long custom pin name changed or disappeared'
                frame = next(n for n in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Studio')
                bounds = frame.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
                ranges = []
                for node in descendants(frame):
                    try:
                        iface = node.get_text_iface()
                        value = Atspi.Text.get_text(iface, 0, -1)
                        offset = value.find(long_name)
                        if offset >= 0:
                            ranges.append(Atspi.Text.get_range_extents(iface, offset, offset + len(long_name), Atspi.CoordType.SCREEN))
                    except (GLib.Error, TypeError): continue
                assert ranges, 'Long-name text range not exposed by AT-SPI'
                long_ranges.append(dict(language=language, windowSize=dimensions(), ranges=[dict(x=r.x,y=r.y,width=r.width,height=r.height) for r in ranges]))
                for rect in ranges:
                    if rect.width > 0 and rect.height > 0:
                        assert rect.width <= bounds.width and rect.x >= bounds.x and rect.x + rect.width <= bounds.x + bounds.width, f'Long-name range extends outside Studio: {rect} frame={bounds}'
                summary = next(n for n in descendants(frame) if n.get_role_name() == 'unknown' and long_name in (n.get_name() or ''))
                summary_rect = summary.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
                assert summary_rect.width > 0 and summary_rect.height > 0, 'Summary geometry unavailable'
                assert summary_rect.x >= bounds.x and summary_rect.x + summary_rect.width <= bounds.x + bounds.width, 'Class-mapping summary overflows horizontally'
                long_ranges[-1]['summaryRect'] = dict(x=summary_rect.x, y=summary_rect.y, width=summary_rect.width, height=summary_rect.height)
                # This WebKit/AT-SPI version can return 0x0 for text ranges. That
                # is unavailable evidence, not a successful geometry check.
                screenshot = root / f'localization-apps-{language}-{width}.png'
                focus_studio()
                pixbuf = Gdk.pixbuf_get_from_window(display.get_default_screen().get_root_window(), bounds.x, bounds.y, bounds.width, bounds.height)
                assert pixbuf is not None
                pixbuf.savev(str(screenshot), 'png', [], [])
                long_ranges[-1].update(rangeGeometryAvailable=all(r.width > 0 and r.height > 0 for r in ranges), screenshot=str(screenshot))
                click(labels['systemTab']); click(labels['exportConfig']); focus_studio(labels['exportConfig'])
                dialog = next(n for n in descendants(app) if n.get_name() == labels['exportConfig'] and n.get_role_name() in ('dialog', 'file chooser'))
                actions = [n.get_name() for n in descendants(dialog) if n.get_role_name() == 'button']
                assert labels['save'] in actions and labels['cancel'] in actions, 'Native export labels not translated'
                cancel = next(n for n in descendants(dialog) if n.get_name() == labels['cancel'] and n.get_role_name() == 'button')
                assert cancel.get_action_iface().do_action(0)
                wait(lambda: not any(n.get_name() == labels['exportConfig'] and n.get_role_name() in ('dialog', 'file chooser') for n in descendants(app)), 'Native export cancellation failed')
        passed.append('five tabs in vi/en at 800x600 and 1280x800 keep visible controls horizontally contained; long custom name retained; native export/cancel labels translated')
        for language in ('en', 'vi'):
            focus_studio(); click('Hệ thống' if json.loads(path.read_text())['config']['language'] == 'vi' else 'System')
            click('English' if language == 'en' else 'Tiếng Việt')
            labels = catalogue[language]
            def popup_nodes():
                popup = next(n for n in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Context Menu')
                return list(descendants(popup))
            for trigger, expected, role in [('searchApps','searchApps','entry'), ('audio','audio','heading'), ('systemTools','systemTools','heading')]:
                click(labels[trigger], 'button'); focus_studio('DeskMorph Context Menu')
                wait(lambda: any(n.get_role_name() == role and n.get_name() == labels[expected] for n in popup_nodes()), 'Popup label not translated: ' + trigger)
                if trigger == 'audio':
                    wait(lambda: labels['audioOutput'] in text() or labels['audioUnavailable'] in text(), 'Audio state not translated')
                if trigger == 'systemTools':
                    assert labels['downloads'] in text() and labels['trash'] in text() and labels['systemMonitor'] in text()
                native_keys(chord=[0xff1b]); focus_studio()
            click(labels['calendar'], 'button'); focus_studio('DeskMorph Calendar')
            wait(lambda: any(n.get_name() == labels['previousMonth'] for n in descendants(app)), 'Calendar controls not translated')
            native_keys(chord=[0xff1b]); focus_studio()
            dock = next(n for n in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Taskbar')
            pin = next(n for n in descendants(dock) if n.get_role_name() == 'button' and n.get_name().startswith(long_name + ' • '))
            native_click_node(pin, button=3); focus_studio('DeskMorph Context Menu')
            wait(lambda: any(n.get_name() == labels['unpin'] and n.get_role_name() == 'button' for n in popup_nodes()), 'Context pin action not translated')
            assert labels['newLaunch'] in text() and long_name in text()
            native_keys(chord=[0xff1b]); focus_studio()
        passed.append('launcher/audio/system/calendar/context controls translate vi/en; read-only popup audit does not launch apps or change services')


    finally:
        try: stop()
        finally:
            path.write_bytes(original)
            review_file.unlink(missing_ok=True)
            for recovery in set(path.parent.glob('*.recovery.json')) - recovery_before: recovery.unlink()
            app = start_app(); set_app(app)
    report = dict(passed=passed, fixturePids=pids, normalPid=app.get_process_id(), configRestored=path.read_bytes() == original,
                  allFixturesExited=all(stopped(pid) for pid in pids), layouts=layouts, longNameRanges=long_ranges, recoveryFilesRestored=set(path.parent.glob('*.recovery.json')) == recovery_before)
    assert report['configRestored'] and report['allFixturesExited'] and report['recoveryFilesRestored']
    (root / 'localization-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return app
