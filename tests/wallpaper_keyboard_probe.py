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
    for i in range(26):
        pixel.fill(0xd13769ff if i == 1 else 0x345678ff)
        pixel.savev(str(images / f'image-{i:02}.png'), 'png', [], [])
    other = root / 'other'; other.mkdir()
    pixel.savev(str(other / 'other.jpg'), 'jpeg', [], [])
    observations = []
    captures = []
    dispatch(op='prepare')
    for language in ('vi', 'en'):
        config_home = root / ('wallpaper-' + language)
        config_file = config_home / 'com.ducthanhdev.deskmorph/config.json'
        config_file.parent.mkdir(parents=True)
        config = json.loads((repo / 'src/config/defaults.json').read_text())
        config.update(language=language, enabled=False, reduceMotion=True,
            wallpaperFolders=[str(images), str(other)], wallpaperFavorites=[str(images / 'image-00.png')],
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
            labels = dict(tab='Hình nền', next='Trang sau', previous='Trang trước', favorites='Chỉ ảnh yêu thích', favorite='Yêu thích', shuffle='Đổi ngẫu nhiên', apply='Áp dụng', retry='Thử lại', search='Tìm hình nền', folder='Lọc theo thư mục', format='Định dạng') if language == 'vi' else dict(tab='Wallpapers', next='Next page', previous='Previous page', favorites='Favorites only', favorite='Favorite', shuffle='Shuffle now', apply='Apply', retry='Retry', search='Search wallpapers', folder='Filter by folder', format='Format')
            def find(name): return next((n for n in descendants(app) if n.get_name() == name and n.get_role_name() in ('button', 'toggle button', 'entry', 'check box', 'combo box')), None)
            def focus(name):
                node = wait(lambda: find(name), 'Missing control: ' + name)
                assert node.get_component_iface().grab_focus()
                wait(lambda: find(name).get_state_set().contains(Atspi.StateType.FOCUSED), 'AT-SPI seed focus failed: ' + name)
            def key(code): dispatch(op='key', code=code)
            def focused(name):
                return (node := find(name)) and node.get_state_set().contains(Atspi.StateType.FOCUSED)
            def background_pixels(expected, label):
                path = Path(dispatch(op='backgroundScreenshot')['path'])
                done = Path(str(path) + '.json')
                wait(done.exists, 'Compositor screenshot did not finish')
                assert json.loads(done.read_text()).get('ok'), done.read_text()
                image = GdkPixbuf.Pixbuf.new_from_file(str(path))
                data = image.get_pixels(); stride = image.get_rowstride(); channels = image.get_n_channels()
                samples = []
                for x, y in ((200, 200), (640, 360), (1000, 500)):
                    rgb = list(data[y * stride + x * channels:y * stride + x * channels + 3])
                    samples.append(dict(x=x, y=y, rgb=rgb))
                assert all(max(abs(a-b) for a,b in zip(s['rgb'], expected)) <= 2 for s in samples), samples
                captures.append(dict(language=language, label=label, file=path.name,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(), width=image.get_width(), height=image.get_height(), samples=samples))
                dispatch(op='activate', id=studio['id'], pid=process.pid)
                wait(lambda: any(w['focused'] for w in dispatch(op='state')['windows']), 'Studio focus did not return after screenshot')
            focus(labels['tab']); key(28)
            wait(lambda: find(labels['next']), 'Image scan did not produce pagination')
            focus(labels['next']); key(28)
            wait(lambda: focused(labels['previous']), 'Last-page disabled Next lost keyboard focus')
            key(28)
            wait(lambda: focused(labels['next']), 'First-page disabled Previous lost keyboard focus')
            def favorite_count():
                return sum(n.get_role_name() in ('button', 'toggle button') and n.get_name().startswith(labels['favorite'] + ' ')
                    for n in descendants(app))
            wait(lambda: favorite_count() == 24, 'First page did not contain 24 images')
            # Native select keys; no AT-SPI set-value or renderer injection.
            focus(labels['folder']); key(107)
            wait(lambda: favorite_count() == 1, 'Folder End did not select the second image root')
            wait(lambda: focused(labels['folder']), 'Folder filtering lost focus')
            focus(labels['format']); key(107)
            wait(lambda: favorite_count() == 0, 'Format filter did not intersect folder filter')
            wait(lambda: focused(labels['format']), 'Empty format result lost focus')
            key(102)
            wait(lambda: favorite_count() == 1, 'Format Home did not restore all formats')
            focus(labels['folder']); key(102)
            wait(lambda: favorite_count() == 24, 'Folder Home did not restore first page')
            focus(labels['search']); key(44)
            wait(lambda: favorite_count() == 0, 'Typed Z did not filter images to empty')
            wait(lambda: focused(labels['search']), 'Empty search result lost focus')
            key(14)
            wait(lambda: favorite_count() == 24, 'Backspace did not restore the first page')
            focus(labels['favorites']); key(57)
            favorite = labels['favorite'] + ' image-00.png'
            wait(lambda: find(favorite), 'Favorite filter lost its only image')
            focus(favorite); key(28)
            wait(lambda: focused(labels['search']), 'Unfavorite in favorites-only lost focus instead of returning to search')
            focus(labels['favorites']); key(57)
            apply_name = labels['apply'] + ' image-01.png'
            wait(lambda: find(apply_name), 'Apply image missing after clearing favorites filter')
            focus(apply_name); key(28)
            def setting_path(key='picture-uri'):
                return subprocess.check_output(['gsettings', 'get', 'org.gnome.desktop.background', key], env=env, text=True).strip()
            wait(lambda: (images / 'image-01.png').as_uri() in setting_path(), 'Apply did not update private GNOME setting')
            wait(lambda: focused(apply_name), 'Successful Apply lost focus')
            wait(lambda: (images / 'image-01.png').as_uri() in setting_path('picture-uri-dark'), 'Apply did not update private dark wallpaper setting')
            background_pixels([209, 55, 105], 'applied-image-01')
            missing = images / 'image-02.png'
            missing.unlink()
            failed_name = labels['apply'] + ' image-02.png'
            focus(failed_name); key(28)
            wait(lambda: find(labels['retry']), 'Missing-file Apply did not expose Retry')
            wait(lambda: focused(failed_name), 'Failed Apply lost focus')
            assert (images / 'image-01.png').as_uri() in setting_path(), 'Failed Apply changed private wallpaper setting'
            pixel.savev(str(missing), 'png', [], [])
            focus(labels['retry']); key(28)
            wait(lambda: missing.as_uri() in setting_path(), 'Retry did not apply restored image')
            wait(lambda: focused(labels['search']), 'Removed Retry did not restore search focus')
            wait(lambda: missing.as_uri() in setting_path('picture-uri-dark'), 'Retry did not update private dark setting')
            background_pixels([52, 86, 120], 'retried-image-02')
            # Deliberately distinguish the two keys in private settings, so a
            # dark-mode capture cannot pass by accidentally reading the light key.
            subprocess.run(['gsettings', 'set', 'org.gnome.desktop.background', 'picture-uri', (images / 'image-01.png').as_uri()], env=env, check=True)
            subprocess.run(['gsettings', 'set', 'org.gnome.desktop.interface', 'color-scheme', 'prefer-dark'], env=env, check=True)
            time.sleep(.5)
            background_pixels([52, 86, 120], 'dark-selects-image-02')
            subprocess.run(['gsettings', 'set', 'org.gnome.desktop.interface', 'color-scheme', 'default'], env=env, check=True)
            time.sleep(.5)
            background_pixels([209, 55, 105], 'light-selects-image-01')
            subprocess.run(['gsettings', 'set', 'org.gnome.desktop.background', 'picture-uri', missing.as_uri()], env=env, check=True)
            before_shuffle = setting_path()
            focus(labels['shuffle']); key(28)
            wait(lambda: setting_path() != before_shuffle, 'Shuffle did not change private wallpaper')
            wait(lambda: focused(labels['shuffle']), 'Shuffle lost focus')
            assert root.as_uri() in setting_path() and setting_path() == setting_path('picture-uri-dark')
            saved = json.loads(config_file.read_text())['config']
            assert saved['wallpaperFavorites'] == [] and saved['wallpaperScheduleEnabled'] is False
            assert saved['reduceMotion'] is True
            observations.append(dict(language=language, reducedMotion=True, lastPageFocusPrevious=True,
                firstPageFocusNext=True, favoriteFilterSpace=True, unfavoriteEnterFocusSearch=True,
                persistedFavoriteRemoval=True, folderEndHome=True, formatEndHomeIntersection=True,
                searchZBackspace=True, filterFocusRetained=True, successfulApplyFocus=True, failedApplyFocus=True, shuffleFocus=True, shuffleUsesPrivateFixture=True,
                retryRestoredFile=True, privateLightDarkSettingsVerified=True, compositorLightDarkPixelsVerified=True, failedApplyKeepsPrevious=True, removedRetryFocusSearch=True, onlyPrivateWallpaperSettings=True))
        finally:
            process.terminate()
            try: process.wait(timeout=8)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
    (root / 'launcher-result.json').write_text(json.dumps(dict(wallpaperKeyboard=observations, backgroundCaptures=captures,
        binarySha256=hashlib.sha256(binary.read_bytes()).hexdigest(), scope='Private GNOME46 native Wayland Studio, actual Enter/Space/Home/End/Z/Backspace keys after AT-SPI focus seeds. vi/en with reduced motion. Wallpaper applies only to private keyfile GNOME settings; no host input/settings, full Tab order, chooser or screen-reader claim.'), indent=2))


if __name__ == '__main__': run()
