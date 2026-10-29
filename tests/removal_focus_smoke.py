"""Native focused deletion, fallback, rename and preset form keyboard checks."""
import json
import os
from pathlib import Path
import signal
import time
from gi.repository import Atspi
from dock_layout_smoke import descendants


def run(app, config_home, click, focus_studio, native_keys, test_app, start_app, set_app):
    root = Path('/tmp/deskmorph-desktop-test')
    path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = path.read_bytes()
    owned = []
    observations = []
    def wait(predicate, message):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(.12)
        raise AssertionError(message)
    def stop():
        try:
            pid = test_app().get_process_id()
        except RuntimeError:
            return
        assert pid == app.get_process_id()
        assert f'DESKMORPH_CONFIG_HOME={config_home}'.encode() in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
        os.kill(pid, signal.SIGTERM)
        def stopped():
            try:
                return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z'
            except FileNotFoundError:
                return True
        wait(stopped, 'Owned app did not exit')
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass
    def start():
        nonlocal app
        app = start_app(); set_app(app); owned.append(app.get_process_id())
    def controls():
        frame = next(n for n in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Studio')
        return [n for n in descendants(frame) if n.get_role_name() in ('button', 'entry', 'check box', 'slider', 'combo box', 'toggle button')]
    def find(name):
        return next((n for n in controls() if n.get_name() == name), None)
    def focused(name):
        return any(n.get_name() == name and n.get_state_set().contains(Atspi.StateType.FOCUSED) for n in controls())
    def focus(name):
        node = wait(lambda: find(name), 'Missing control: ' + name)
        assert node.get_component_iface().grab_focus()
        wait(lambda: focused(name), 'No focus: ' + name)
    def enter():
        native_keys(chord=[0xff0d])
    try:
        for language in ('vi', 'en'):
            stop()
            fixture = json.loads(original)
            cfg = fixture['config']
            appearance_keys = ('position', 'height', 'iconSize', 'iconSpacing', 'opacity', 'borderRadius', 'accentColor', 'bouncingLaunch', 'dynamicShadow', 'magnification', 'maxMagnificationScale', 'reduceMotion')
            appearance = {key: cfg[key] for key in appearance_keys}
            cfg.update(language=language, wallpaperScheduleEnabled=False,
                       pinnedApps=[dict(id=f'focus-{i}', name=f'Focus Pin {i}', command='/bin/true', iconType='custom', matchClasses=[], enabled=True) for i in (1, 2)],
                       presets=[dict(id=f'focus-{i}', name=f'Focus Preset {i}', appearance=appearance) for i in (1, 2)],
                       wallpaperFolders=['/tmp/deskmorph-focus-folder-1', '/tmp/deskmorph-focus-folder-2'])
            path.write_text(json.dumps(fixture))
            start(); focus_studio()
            labels = dict(apps='Ứng dụng', unpin='Bỏ ghim', search='Tìm ứng dụng', appearance='Giao diện', remove='Xóa', rename='Đổi tên', preset='Tên preset', wallpaper='Hình nền', folder='Thư mục ảnh') if language == 'vi' else dict(apps='Applications', unpin='Unpin', search='Search applications', appearance='Appearance', remove='Delete', rename='Rename', preset='Preset name', wallpaper='Wallpapers', folder='Image folder')
            focus(labels['apps']); enter()
            for i in (1, 2):
                focus(f"{labels['unpin']} Focus Pin {i}"); enter()
                target = f"{labels['unpin']} Focus Pin 2" if i == 1 else labels['search']
                wait(lambda: focused(target), 'Pin removal lost focus: ' + target)
                observations.append(dict(language=language, operation=f'unpin {i}', focus=target))
            focus(labels['appearance']); enter()
            color_name = 'Màu chủ đạo' if language == 'vi' else 'Accent color'
            focus(color_name); native_keys(value='#336699'); enter()
            wait(lambda: json.loads(path.read_text())['config']['accentColor'] == '#336699', 'Enter did not save hex accent')
            observations.append(dict(language=language, operation='save accent with Enter', color='#336699'))
            focus(f"{labels['rename']} Focus Preset 1"); enter()
            wait(lambda: focused(labels['preset']), 'Rename did not focus preset name')
            native_keys(value='Focus Renamed'); enter()
            wait(lambda: any(p['name'] == 'Focus Renamed' for p in json.loads(path.read_text())['config']['presets']), 'Enter did not submit preset rename')
            for name in ('Focus Renamed', 'Focus Preset 2'):
                focus(f"{labels['remove']} {name}"); enter()
                target = f"{labels['remove']} Focus Preset 2" if name == 'Focus Renamed' else labels['preset']
                wait(lambda: focused(target), 'Preset removal lost focus: ' + target)
                observations.append(dict(language=language, operation='remove ' + name, focus=target))
            focus(labels['wallpaper']); enter()
            for i in (1, 2):
                focus(f"{labels['remove']} /tmp/deskmorph-focus-folder-{i}"); enter()
                target = f"{labels['remove']} /tmp/deskmorph-focus-folder-2" if i == 1 else labels['folder']
                wait(lambda: focused(target), 'Folder removal lost focus: ' + target)
                observations.append(dict(language=language, operation=f'remove folder {i}', focus=target))
            assert not json.loads(path.read_text())['config']['pinnedApps']
            assert not json.loads(path.read_text())['config']['presets']
            assert not json.loads(path.read_text())['config']['wallpaperFolders']
    finally:
        stop(); path.write_bytes(original); start()
    report = dict(observations=observations, fixturePids=owned[:-1], normalPid=owned[-1], configRestored=path.read_bytes() == original, renameEnterSubmits=True)
    assert report['configRestored']
    (root / 'removal-focus-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))
    return app
