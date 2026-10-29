"""Real failed launches, filesystem writes and deleted wallpapers, using the owned GUI only."""
import json
import os
from pathlib import Path
import subprocess
import time
from gi.repository import Atspi
from dock_layout_smoke import descendants


def run(app, config_home, click, focus_studio, native_keys, type_entry, native_click_node):
    root = Path('/tmp/deskmorph-desktop-test')
    config_path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    snapshot = lambda: json.loads(config_path.read_text())
    original = snapshot()['config']
    mode = config_path.parent.stat().st_mode & 0o777
    executable = root / 'error-retry-executable'
    marker = root / 'error-retry-marker'
    image = root / 'error-retry-wallpaper.png'
    entry = root / 'data/applications/deskmorph-error-retry.desktop'
    previous_wallpaper = {key: subprocess.check_output(['gsettings', 'get', 'org.gnome.desktop.background', key], text=True).strip() for key in ('picture-uri', 'picture-uri-dark')}
    passed = []

    def node(name, role=None):
        return next((n for n in descendants(app) if n.get_name() == name and (role is None or n.get_role_name() == role)), None)

    def text():
        return '\n'.join(n.get_name() + (' ' + Atspi.Text.get_text(n.get_text_iface(), 0, -1) if n.get_text_iface() else '') for n in descendants(app))

    def wait(predicate, message):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(.15)
        raise AssertionError(message + '\n' + text()[-3500:])

    def import_config(value, label):
        file = root / f'error-retry-{label}.json'
        file.write_text(json.dumps({'schemaVersion': 1, 'config': value}))
        focus_studio(); click('Hệ thống'); click('Nhập cấu hình'); focus_studio('Select File')
        native_keys(chord=[0xffe3, ord('l')]); native_keys(value=str(file)); native_keys(chord=[0xff0d])
        time.sleep(.8); click('Áp dụng cấu hình đã nhập')
        wait(lambda: snapshot()['config'] == value, 'Error fixture config import failed')

    def make_executable():
        executable.write_text('#!/bin/sh\nprintf done > /tmp/deskmorph-desktop-test/error-retry-marker\n')
        executable.chmod(0o700)

    try:
        executable.unlink(missing_ok=True); marker.unlink(missing_ok=True)
        pin = dict(id='error-retry-test', name='Error Retry Test', command=str(executable), matchClasses=['errorretrytest'], iconType='custom', enabled=True)
        initial = dict(original, language='vi', enabled=True, autoHide=False, height=40, showApps=True, wallpaperScheduleEnabled=False,
                       pinnedApps=[pin] + [p for p in original['pinnedApps'] if p['id'] != pin['id']])
        import_config(initial, 'setup')
        click('Error Retry Test • 0 cửa sổ', 'button')
        wait(lambda: 'app_launch_failed; launch_app' in text(), 'Dock did not display launch error code and command')
        time.sleep(3.5)
        assert 'app_launch_failed; launch_app' in text(), 'Window polling erased action failure'
        assert not marker.exists(), 'Failed launch reported false success'
        focus_studio(); click('Hệ thống'); click('English')
        wait(lambda: snapshot()['config']['language'] == 'en', 'Language change did not persist')
        wait(lambda: 'Unable to launch application' in text() and 'app_launch_failed; launch_app' in text(), 'Retained Dock error did not translate to English')
        focus_studio('DeskMorph Taskbar')
        detail = node('Details', 'button')
        assert detail is not None and detail.get_component_iface().grab_focus()
        native_keys(chord=[0xff0d])
        wait(lambda: 'No such file or directory (os error 2)' in text(), 'Keyboard did not reveal original launch diagnostic')
        # Keep the minimum-height retry geometry check on the collapsed disclosure.
        native_keys(chord=[0xff0d])
        focus_studio(); click('Tiếng Việt')
        wait(lambda: snapshot()['config']['language'] == 'vi' and node('Chi tiết', 'button') is not None, 'Retained Dock error did not return to Vietnamese')
        passed.append('retained Dock error translates vi/en live; language persists; Enter opens diagnostic disclosure without replaying launch')
        retry_bounds = node('Thử lại', 'button').get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        dock_bounds = node('DeskMorph Taskbar', 'frame').get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        assert retry_bounds.y >= dock_bounds.y and retry_bounds.y + retry_bounds.height <= dock_bounds.y + dock_bounds.height, 'Retry button clipped outside minimum-height Dock'
        make_executable(); focus_studio('DeskMorph Taskbar'); native_click_node(node('Thử lại', 'button'))
        wait(marker.exists, 'Dock retry did not launch the repaired executable')
        wait(lambda: 'app_launch_failed; launch_app' not in text(), 'Successful retry did not clear launch error')
        passed.append('Dock missing executable error survives >2 window polls; repair + explicit Retry dispatches exact command')

        # A desktop entry exists but its executable disappears before dispatch.
        marker.unlink()
        make_executable()
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text(f'[Desktop Entry]\nType=Application\nName=Error Retry Catalogue\nExec={executable}\nIcon=application-x-executable\n')
        click('Tìm ứng dụng', 'button')
        wait(lambda: node('Tìm ứng dụng', 'entry') is not None, 'Launcher search not ready')
        focus_studio('DeskMorph Context Menu')
        assert node('Tìm ứng dụng', 'entry').get_component_iface().grab_focus()
        native_keys(value='Error Retry Catalogue')
        click('Làm mới', 'button')
        wait(lambda: node('Mở Error Retry Catalogue', 'button') is not None, 'Retry desktop entry did not reach launcher')
        saved_entry = entry.read_text()
        stale_button = node('Mở Error Retry Catalogue', 'button')
        entry.unlink()
        assert stale_button.get_action_iface().do_action(0)
        wait(lambda: 'app_missing; launch_installed_app' in text(), 'GIO launch failure did not keep launcher with an error')
        entry.write_text(saved_entry)
        make_executable(); click('Thử lại', 'button')
        wait(marker.exists, 'Launcher retry did not dispatch repaired desktop entry')
        passed.append('desktop entry removed after listing stays in launcher with context; restore + Retry launches original desktop ID even after results refresh')

        focus_studio(); click('Hệ thống')
        before = snapshot()
        config_path.parent.chmod(0o500)
        try:
            click('Giữ Dock khi đóng Studio')
            wait(lambda: 'config_write; patch_config' in text(), 'Filesystem save failure not exposed')
            assert snapshot() == before, 'Failed configuration save changed disk state'
            time.sleep(2)
            assert 'config_write; patch_config' in text()
        finally:
            config_path.parent.chmod(mode)
        click('Thử lại', 'button')
        wait(lambda: snapshot()['config']['keepDockOnClose'] != before['config']['keepDockOnClose'], 'Save Retry only reloaded instead of persisting the failed patch')
        assert snapshot()['revision'] == before['revision'] + 1, 'Retry wrote extra revisions'
        passed.append('read-only config directory leaves disk/revision unchanged and shows code/context; Retry persists original patch exactly once')

        # A different webview commits while Studio retains the failed patch.
        before = snapshot()
        config_path.parent.chmod(0o500)
        try:
            click('Giữ Dock khi đóng Studio')
            wait(lambda: 'config_write; patch_config' in text(), 'Second write failure not exposed')
        finally:
            config_path.parent.chmod(mode)
        focus_studio('DeskMorph Taskbar')
        native_click_node(node('Error Retry Test • 0 cửa sổ', 'button'), button=3)
        click('Bỏ ghim', 'button')
        wait(lambda: not any(p['id'] == pin['id'] for p in snapshot()['config']['pinnedApps']), 'Concurrent popup mutation did not commit')
        concurrent = snapshot()
        focus_studio(); click('Thử lại', 'button')
        wait(lambda: 'config_conflict; patch_config' in text(), 'Stale retry overwrote concurrent edit')
        assert snapshot() == concurrent
        assert snapshot()['config']['keepDockOnClose'] == before['config']['keepDockOnClose']
        click('Thử lại', 'button')
        wait(lambda: 'config_conflict; patch_config' not in text(), 'Conflict reload did not acknowledge current state')
        passed.append('Studio failed patch followed by popup unpin: Retry rejects stale revision without extra writes; reload keeps concurrent data')

        import gi
        gi.require_version('GdkPixbuf', '2.0')
        from gi.repository import GdkPixbuf
        pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 64, 36)
        pixbuf.fill(0x48b9c7ff); pixbuf.savev(str(image), 'png', [], [])
        value = dict(snapshot()['config'], wallpaperFolders=[str(root / 'error-retry-library')])
        library = root / 'error-retry-library'; library.mkdir(exist_ok=True)
        target = library / image.name; target.write_bytes(image.read_bytes())
        import_config(value, 'wallpaper')
        click('Hình nền')
        wait(lambda: node('Áp dụng ' + image.name) is not None, 'Retry wallpaper not scanned')
        target.unlink()
        current = subprocess.check_output(['gsettings', 'get', 'org.gnome.desktop.background', 'picture-uri'], text=True).strip()
        click('Áp dụng ' + image.name)
        wait(lambda: 'set_wallpaper_failed; set_wallpaper' in text(), 'Deleted wallpaper did not display structured error')
        assert 'Đã áp dụng hình nền.' not in text(), 'Failed wallpaper change showed success'
        assert subprocess.check_output(['gsettings', 'get', 'org.gnome.desktop.background', 'picture-uri'], text=True).strip() == current
        target.write_bytes(image.read_bytes()); click('Thử lại', 'button')
        wait(lambda: subprocess.check_output(['gsettings', 'get', 'org.gnome.desktop.background', 'picture-uri'], text=True).strip().strip("'") == target.as_uri(), 'Wallpaper Retry did not reapply original path')
        wait(lambda: 'set_wallpaper_failed; set_wallpaper' not in text(), 'Wallpaper error remained after successful Retry')
        passed.append('deleted image fails without GNOME URI change or false success; restore + Retry applies exact original path')
        report = dict(pid=app.get_process_id(), passed=passed)
        (root / 'command-errors-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(report, ensure_ascii=False), flush=True)
    finally:
        config_path.parent.chmod(mode)
        if snapshot()['config']['language'] != 'vi':
            focus_studio(); click('System'); click('Tiếng Việt')
        entry.unlink(missing_ok=True); executable.unlink(missing_ok=True); marker.unlink(missing_ok=True)
        for key, value in previous_wallpaper.items():
            subprocess.run(['gsettings', 'set', 'org.gnome.desktop.background', key, value], check=True)
        import_config(original, 'restore')
        assert snapshot()['config'] == original
