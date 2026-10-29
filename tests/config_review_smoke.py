"""Native reset review keyboard focus/confirm/cancel/no-change/undo, vi/en."""
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
    owned_files = []
    def wait(predicate, message):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(.12)
        details = [(n.get_role_name(), n.get_name()) for n in descendants(app) if n.get_state_set().contains(Atspi.StateType.FOCUSED) or n.get_role_name() in ('file chooser', 'alert', 'landmark')]
        raise AssertionError(message + ': ' + repr(details))
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
            cfg.update(language=language, height=64, accentColor='#345678', wallpaperScheduleEnabled=False)
            path.write_text(json.dumps(fixture))
            start(); focus_studio()
            labels = dict(system='Hệ thống', reset='Khôi phục cấu hình mặc định', review='Xem thay đổi trước khi nhập', confirm='Xác nhận khôi phục', cancel='Hủy', undo='Hoàn tác') if language == 'vi' else dict(system='System', reset='Restore default configuration', review='Review changes before importing', confirm='Confirm restore', cancel='Cancel', undo='Undo')
            def document():
                return json.loads(path.read_text())
            def region_focused():
                return any(n.get_name() == labels['review'] and n.get_state_set().contains(Atspi.StateType.FOCUSED) for n in descendants(app))
            focus(labels['system']); enter()
            before = document()
            focus(labels['reset']); enter()
            wait(region_focused, 'Review region did not receive keyboard focus')
            assert document() == before, 'Opening review changed config/revision'
            native_keys(chord=[0xff09]); wait(lambda: focused(labels['confirm']), 'Tab did not reach confirm')
            native_keys(chord=[0xff09]); wait(lambda: focused(labels['cancel']), 'Tab did not reach Cancel')
            enter(); wait(lambda: focused(labels['reset']), 'Cancel did not restore trigger focus')
            assert document() == before
            enter(); wait(region_focused, 'Second review did not focus region')
            native_keys(chord=[0xff09]); enter()
            wait(lambda: document()['revision'] == before['revision'] + 1, 'Confirm did not commit exactly once')
            wait(lambda: focused(labels['undo']), 'Confirm did not focus Undo')
            defaults = json.loads((Path(__file__).resolve().parents[1] / 'src/config/defaults.json').read_text())
            expected = dict(defaults, language=language, presets=before['config']['presets'])
            assert document()['config'] == expected, 'Reset scope differs'
            enter(); wait(lambda: document()['config'] == before['config'], 'Undo did not restore exact config')
            wait(lambda: focused(labels['reset']), 'Undo did not restore trigger focus')
            assert document()['revision'] == before['revision'] + 2
            # Reset again, then a no-change review must skip the disabled confirm.
            enter(); wait(region_focused, 'Third review did not focus region')
            native_keys(chord=[0xff09]); enter()
            wait(lambda: document()['config'] == expected, 'Second reset did not apply')
            focus(labels['reset']); enter(); wait(region_focused, 'No-change review did not focus region')
            confirm = find(labels['confirm'])
            assert confirm and not confirm.get_state_set().contains(Atspi.StateType.ENABLED)
            unchanged = document()
            native_keys(chord=[0xff09]); wait(lambda: focused(labels['cancel']), 'Disabled confirm was not skipped')
            enter(); wait(lambda: focused(labels['reset']), 'No-change Cancel lost trigger focus')
            assert document() == unchanged
            import_label = 'Nhập cấu hình' if language == 'vi' else 'Import configuration'
            import_confirm = 'Áp dụng cấu hình đã nhập' if language == 'vi' else 'Apply imported configuration'
            import_file = root / f'config-review-import-{app.get_process_id()}-{language}.json'
            assert not import_file.exists()
            owned_files.append(import_file)
            imported = dict(document()['config'], iconSpacing=13)
            import_file.write_text(json.dumps(dict(schemaVersion=1, config=imported)))
            def chooser():
                return next((n for n in descendants(app) if n.get_role_name() == 'file chooser' and n.get_name() == 'Select File'), None)
            focus(import_label); enter(); wait(chooser, 'Import chooser did not open with Enter')
            focus_studio('Select File'); native_keys(chord=[0xff1b])
            wait(lambda: focused(import_label), 'Chooser Cancel did not restore import button focus')
            def open_import():
                focus(import_label); enter(); wait(chooser, 'Import chooser absent')
                focus_studio('Select File'); native_keys(chord=[0xffe3, ord('l')]); native_keys(value=str(import_file))
                open_button = next(n for n in descendants(chooser()) if n.get_role_name() == 'button' and n.get_name() == 'Open')
                assert open_button.get_component_iface().grab_focus()
                enter(); wait(region_focused, 'Imported review did not receive focus after chooser')
            before_import = document()
            open_import()
            native_keys(chord=[0xff09]); wait(lambda: focused(import_confirm), 'Import Tab did not reach confirm')
            native_keys(chord=[0xff09]); wait(lambda: focused(labels['cancel']), 'Import Tab did not reach Cancel')
            enter(); wait(lambda: focused(import_label), 'Import Cancel lost trigger focus')
            assert document() == before_import
            open_import(); native_keys(chord=[0xff09]); enter()
            wait(lambda: document()['config'] == imported, 'Import confirmation did not apply reviewed config')
            wait(lambda: focused(labels['undo']), 'Import confirmation did not focus Undo')
            enter(); wait(lambda: document()['config'] == before_import['config'], 'Import Undo failed')
            wait(lambda: focused(import_label), 'Import Undo did not restore import trigger')
            observations.append(dict(language=language, previewFocus=True, confirmCancelTabOrder=True, cancelReturnsTrigger=True, confirmFocusesUndo=True, undoRestoresExactConfig=True, undoReturnsTrigger=True, noChangeConfirmDisabledAndSkipped=True, previewAndCancelPreserveRevision=True, chooserEscapeRestoresImportFocus=True, importReviewFocus=True, importCancelPreservesRevision=True, importConfirmUndoFocus=True))
    finally:
        stop()
        for file in owned_files:
            file.unlink(missing_ok=True)
        path.write_bytes(original); start()
    report = dict(observations=observations, fixturePids=owned[:-1], normalPid=owned[-1], configRestored=path.read_bytes() == original, scope='Native X11 reset review, vi/en; initial System/reset focus through AT-SPI, subsequent Tab/Enter real; GTK import chooser Enter/Escape/path selection, review/cancel/confirm/undo')
    assert report['configRestored']
    (root / 'config-review-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))
    return app
