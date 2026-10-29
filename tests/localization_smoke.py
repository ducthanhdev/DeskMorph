"""Native repaired-config warning and translated import review; owned profile only."""
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
    recovery_before = set(path.parent.glob('*.recovery.json'))
    review_file = root / 'localized-review.json'
    pids, passed = [], []

    def wait(predicate, message):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(.1)
        raise AssertionError(message + '\n' + text()[-3500:])

    def text():
        result = []
        for node in descendants(app):
            result.append(node.get_name() or '')
            try: result.append(Atspi.Text.get_text(node, 0, -1))
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
        native_keys(chord=[0xffe3, ord('l')]); native_keys(value=str(review_file)); native_keys(chord=[0xff0d])
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
    finally:
        try: stop()
        finally:
            path.write_bytes(original)
            review_file.unlink(missing_ok=True)
            for recovery in set(path.parent.glob('*.recovery.json')) - recovery_before: recovery.unlink()
            app = start_app(); set_app(app)
    report = dict(passed=passed, fixturePids=pids, normalPid=app.get_process_id(), configRestored=path.read_bytes() == original,
                  allFixturesExited=all(stopped(pid) for pid in pids), recoveryFilesRestored=set(path.parent.glob('*.recovery.json')) == recovery_before)
    assert report['configRestored'] and report['allFixturesExited'] and report['recoveryFilesRestored']
    (root / 'localization-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return app
