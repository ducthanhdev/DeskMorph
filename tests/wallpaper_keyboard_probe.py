"""Actual Studio keyboard input on the owned compositor and private AT-SPI bus."""
import json
import hashlib
import os
from pathlib import Path
import subprocess
import time
import gi
gi.require_version('Atspi', '2.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Atspi, Gio, GLib, GdkPixbuf


def run():
    root = Path(os.environ['DESKMORPH_COMPOSITOR_LAB'])
    assert str(root).startswith('/tmp/deskmorph-wayland-lab-')
    assert os.environ['XDG_RUNTIME_DIR'] == str(root / 'runtime') and not os.environ.get('DISPLAY')
    metadata = json.loads((root / 'session.json').read_text())
    repo = Path(__file__).resolve().parents[1]
    binary = Path(os.environ.get('DESKMORPH_LAB_BINARY', repo / 'src-tauri/target/agent/debug/deskmorph'))
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    def dispatch(**command):
        reply = bus.call_sync('org.gnome.Shell', '/org/deskmorph/Lab', 'org.deskmorph.Lab', 'Dispatch',
            GLib.Variant('(ss)', (metadata['DESKMORPH_PROTOTYPE_TOKEN'], json.dumps(command))),
            None, Gio.DBusCallFlags.NONE, 3000, None)
        return json.loads(reply.unpack()[0])
    def wait(predicate, message):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            value = predicate()
            if value: return value
            time.sleep(.1)
        raise AssertionError(message)
    def descendants(node):
        if not node: return
        yield node
        for i in range(node.get_child_count()): yield from descendants(node.get_child_at_index(i))
    images = root / 'images'; images.mkdir()
    pixel = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 8, 8)
    pixel.fill(0x345678ff)
    for i in range(26): pixel.savev(str(images / f'image-{i:02}.png'), 'png', [], [])
    observations = []
    dispatch(op='prepare')
    for language in ('vi', 'en'):
        config_home = root / ('wallpaper-' + language)
        config_file = config_home / 'com.ducthanhdev.deskmorph/config.json'
        config_file.parent.mkdir(parents=True)
        config = json.loads((repo / 'src/config/defaults.json').read_text())
        config.update(language=language, enabled=False, reduceMotion=True,
            wallpaperFolders=[str(images)], wallpaperFavorites=[str(images / 'image-00.png')],
            wallpaperScheduleEnabled=False)
        config_file.write_text(json.dumps(dict(schemaVersion=1, revision=0, config=config)))
        env = dict(os.environ, DESKMORPH_CONFIG_HOME=str(config_home), WEBKIT_DISABLE_DMABUF_RENDERER='1')
        with (root / 'deskmorph-launcher.log').open('a') as log:
            process = subprocess.Popen([str(binary)], env=env, stdout=log, stderr=log)
        try:
            dispatch(op='target', pid=process.pid)
            app = wait(lambda: next((a for a in descendants(Atspi.get_desktop(0))
                if a.get_role_name() == 'application' and a.get_process_id() == process.pid), None), 'Studio AT-SPI not ready')
            studio = wait(lambda: next((w for w in dispatch(op='state')['windows'] if w['title'] == 'DeskMorph Studio'), None), 'Studio did not map')
            dispatch(op='activate', id=studio['id'], pid=process.pid)
            wait(lambda: any(w['focused'] for w in dispatch(op='state')['windows']), 'Studio did not focus')
            labels = dict(tab='Hình nền', next='Trang sau', previous='Trang trước', favorites='Chỉ ảnh yêu thích', favorite='Yêu thích', search='Tìm hình nền') if language == 'vi' else dict(tab='Wallpapers', next='Next page', previous='Previous page', favorites='Favorites only', favorite='Favorite', search='Search wallpapers')
            def find(name): return next((n for n in descendants(app) if n.get_name() == name and n.get_role_name() in ('button', 'toggle button', 'entry', 'check box')), None)
            def focus(name):
                node = wait(lambda: find(name), 'Missing control: ' + name)
                assert node.get_component_iface().grab_focus()
                wait(lambda: find(name).get_state_set().contains(Atspi.StateType.FOCUSED), 'AT-SPI seed focus failed: ' + name)
            def key(code): dispatch(op='key', code=code)
            def focused(name):
                return (node := find(name)) and node.get_state_set().contains(Atspi.StateType.FOCUSED)
            focus(labels['tab']); key(28)
            wait(lambda: find(labels['next']), 'Image scan did not produce pagination')
            focus(labels['next']); key(28)
            wait(lambda: focused(labels['previous']), 'Last-page disabled Next lost keyboard focus')
            key(28)
            wait(lambda: focused(labels['next']), 'First-page disabled Previous lost keyboard focus')
            focus(labels['favorites']); key(57)
            favorite = labels['favorite'] + ' image-00.png'
            wait(lambda: find(favorite), 'Favorite filter lost its only image')
            focus(favorite); key(28)
            wait(lambda: focused(labels['search']), 'Unfavorite in favorites-only lost focus instead of returning to search')
            saved = json.loads(config_file.read_text())['config']
            assert saved['wallpaperFavorites'] == [] and saved['wallpaperScheduleEnabled'] is False
            assert saved['reduceMotion'] is True
            observations.append(dict(language=language, reducedMotion=True, lastPageFocusPrevious=True,
                firstPageFocusNext=True, favoriteFilterSpace=True, unfavoriteEnterFocusSearch=True,
                persistedFavoriteRemoval=True, noWallpaperApply=True))
        finally:
            process.terminate()
            try: process.wait(timeout=8)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
    (root / 'launcher-result.json').write_text(json.dumps(dict(wallpaperKeyboard=observations,
        binarySha256=hashlib.sha256(binary.read_bytes()).hexdigest(), scope='Private GNOME46 native Wayland Studio, actual Enter/Space keys after AT-SPI focus seeds. vi/en with reduced motion. No wallpaper apply, host input, full Tab order, chooser or screen-reader claim.'), indent=2))


if __name__ == '__main__': run()
