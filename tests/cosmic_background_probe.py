"""COSMIC compositor/background capability research inside the owned GNOME lab."""
import json
import hashlib
import gi
gi.require_version("GdkPixbuf", "2.0")
import os
import re
from pathlib import Path
import subprocess
import time
from gi.repository import Gio, GLib, GdkPixbuf


def run():
    root = Path(os.environ['DESKMORPH_COMPOSITOR_LAB'])
    assert str(root).startswith('/tmp/deskmorph-wayland-lab-')
    assert os.environ['XDG_STATE_HOME'] == str(root / 'state')
    assert os.environ['XDG_RUNTIME_DIR'] == str(root / 'runtime') and not os.environ.get('DISPLAY')
    env = dict(os.environ, XDG_CURRENT_DESKTOP='COSMIC', COSMIC_BACKEND='winit')
    metadata = json.loads((root / 'session.json').read_text())
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    def dispatch(**command):
        reply = bus.call_sync('org.gnome.Shell', '/org/deskmorph/Lab', 'org.deskmorph.Lab', 'Dispatch',
            GLib.Variant('(ss)', (metadata['DESKMORPH_PROTOTYPE_TOKEN'], json.dumps(command))),
            None, Gio.DBusCallFlags.NONE, 3000, None)
        return json.loads(reply.unpack()[0])
    def wait(predicate, message):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            value = predicate()
            if value: return value
            time.sleep(.1)
        raise AssertionError(message)
    def extension_ready():
        try: return dispatch(op='state')
        except GLib.Error as error:
            if 'UnknownMethod' in str(error) or 'UnknownObject' in str(error): return None
            raise
    wait(extension_ready, 'Owned GNOME lab extension did not become ready')
    config_dir = root / 'config/cosmic/com.system76.CosmicBackground/v1'
    config_dir.mkdir(parents=True)
    images = []
    for name, color in [('pink', 0xd13769ff), ('blue', 0x345678ff)]:
        path = root / (name + '.png')
        image = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 8, 8)
        image.fill(color); image.savev(str(path), 'png', [], [])
        images.append(path)
    template = Path('/usr/share/cosmic/com.system76.CosmicBackground/v1/all').read_text().replace('#true', 'true')
    def set_source(path, key="all", output="all"):
        document, replacements = re.subn(r'source: Path\("[^\"]*"\)', 'source: Path(' + json.dumps(str(path)) + ')', template)
        assert replacements == 1, 'Installed COSMIC background schema changed'
        document = document.replace('output: \"all\"', 'output: ' + json.dumps(output))
        temporary = config_dir / (key + '.tmp')
        temporary.write_text(document); temporary.replace(config_dir / key)
    (config_dir / 'same-on-all').write_text('true')
    set_source(images[0])
    native_edits = []
    def native_edit(output):
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(['cargo', 'test', '--locked', '--offline',
            '--manifest-path', str(repo / 'src-tauri/Cargo.toml'),
            '--target-dir', str(repo / 'src-tauri/target/agent'), '--lib',
            'cosmic_background::tests::native_lab_edit', '--', '--ignored', '--exact'],
            env=dict(env, DESKMORPH_COSMIC_EDIT_OUTPUT=output),
            capture_output=True, text=True, timeout=60)
        (root / ('cosmic-native-' + output + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0 and '1 passed' in result.stdout, result.stdout + result.stderr
        native_edits.append(dict(output=output, rustTestPassed=True))
    children = []
    try:
        with (root / 'deskmorph-launcher.log').open('w') as log:
            compositor = subprocess.Popen(['cosmic-comp', '--no-xwayland'], env=env, stdout=log, stderr=log)
            children.append(compositor)
            def nested_socket():
                assert compositor.poll() is None, 'Nested COSMIC compositor exited'
                return next((p for p in (root / 'runtime').glob('wayland-*') if not p.name.endswith('.lock')), None)
            socket = wait(nested_socket, 'Nested COSMIC socket did not appear')
            dispatch(op='target', pid=compositor.pid)
            window = wait(lambda: next((w for w in dispatch(op='state')['windows'] if w['frame']['width'] > 0 and w['frame']['height'] > 0), None), 'Nested COSMIC window did not map')
            dispatch(op='activate', id=window['id'], pid=compositor.pid)
            background = subprocess.Popen(['cosmic-bg'], env=dict(env, WAYLAND_DISPLAY=socket.name), stdout=log, stderr=log)
            children.append(background)
            time.sleep(3)
            assert background.poll() is None, 'COSMIC background exited'
            state_file = root / 'state/cosmic/com.system76.CosmicBackground/v1/wallpapers'
            wait(lambda: state_file.exists(), 'COSMIC did not write private wallpaper state')
            captures = []
            def capture_pixels(expected, label=None):
                capture = Path(dispatch(op='stageScreenshot')['path'])
                wait(lambda: Path(str(capture) + '.json').exists(), 'Nested compositor screenshot missing')
                assert json.loads(Path(str(capture) + '.json').read_text()).get('ok')
                image = GdkPixbuf.Pixbuf.new_from_file(str(capture))
                data = image.get_pixels(); stride = image.get_rowstride(); channels = image.get_n_channels()
                samples = [list(data[y*stride+x*channels:y*stride+x*channels+3]) for x,y in [(200,200),(640,360),(1000,500)]]
                captures.append(dict(label=label, file=capture.name, sha256=hashlib.sha256(capture.read_bytes()).hexdigest(), samples=samples))
                if expected is None: return True  # retained UI frame; no solid-color assertion
                return all(max(abs(a-b) for a,b in zip(rgb, expected)) <= 2 for rgb in samples)
            assert capture_pixels([209,55,105]), captures
            native_edit("all")
            time.sleep(2)
            live_updated = capture_pixels([52,86,120])
            assert live_updated, 'COSMIC background did not react to config replacement'
            # Installed winit output identity is observed from the private state,
            # not inferred from the window title or host monitor configuration.
            state_text = state_file.read_text()
            outputs = re.findall(r'\(\s*"([^"\\]+)"\s*,\s*Path\(', state_text)
            assert outputs == ['WINIT-0'], state_text
            output = outputs[0]
            background.terminate(); background.wait(timeout=5)
            (config_dir / 'same-on-all').write_text('false')
            (config_dir / 'backgrounds').write_text(json.dumps([output]))
            set_source(images[0], 'output.' + output, output)
            background = subprocess.Popen(['cosmic-bg'], env=dict(env, WAYLAND_DISPLAY=socket.name), stdout=log, stderr=log)
            children.append(background)
            time.sleep(3)
            assert background.poll() is None
            assert capture_pixels([209,55,105]), 'Per-output source did not override blue default'
            native_edit("batch")
            time.sleep(2)
            assert capture_pixels([52,86,120]), 'Live per-output source update not displayed'
            background.terminate(); background.wait(timeout=5)
            set_source(images[0])
            (config_dir / 'same-on-all').write_text('true')
            background = subprocess.Popen(['cosmic-bg'], env=dict(env, WAYLAND_DISPLAY=socket.name), stdout=log, stderr=log)
            children.append(background)
            time.sleep(3)
            assert background.poll() is None
            assert capture_pixels([209,55,105]), 'same-on-all startup did not ignore blue per-output source'
            from cosmic_wallpaper_ui_probe import verify_ui
            def prepare_ui_case(language):
                nonlocal background
                if language == 'vi':
                    (config_dir / 'all').unlink()
                    return
                background.terminate(); background.wait(timeout=5)
                (config_dir / 'same-on-all').write_text('false')
                (config_dir / 'backgrounds').write_text(json.dumps(['WINIT-0']))
                (config_dir / 'output.WINIT-0').unlink()
                set_source(images[1])
                background = subprocess.Popen(['cosmic-bg'], env=dict(env, WAYLAND_DISPLAY=socket.name), stdout=log, stderr=log)
                children.append(background)
                time.sleep(2)
                assert background.poll() is None
            ui = verify_ui(root, dict(env, WAYLAND_DISPLAY=socket.name), capture_pixels, children, log, prepare_ui_case)
            report = dict(studioUi=ui, nativeEdits=native_edits, nativeMultiFileWriteVerified=True, perOutputOverridePixelsVerified=True, livePerOutputPixelsVerified=True,
                sameOnAllStartupPixelsVerified=True, observedOutput=output,
                upstreamCommit='9520e16758693bc2f6845d52680f236d548edda2',
                versions=subprocess.check_output(['dpkg-query', '-W', 'cosmic-comp', 'cosmic-bg'], text=True).splitlines(),
                binarySha256={name: hashlib.sha256(Path('/usr/bin/' + name).read_bytes()).hexdigest() for name in ('cosmic-comp', 'cosmic-bg')},
                compositorPid=compositor.pid, backgroundPid=background.pid,
                privateStateVerified=state_file.is_file(), stateContents=state_file.read_text(),
                nestedSocket=socket.name, window=window, captures=captures, initialConfigPixelsVerified=True, liveConfigPixelsVerified=live_updated,
                scope='Actual COSMIC nested winit and cosmic-bg, private config RON path update and outer stage pixels. Native RON/GIO single/batch writes plus actual DeskMorph Studio Apply/error/Retry/Shuffle IPC and pixels in vi/en. Missing all/per-output entry creation verified. One nested COSMIC version/output; not whole COSMIC desktop certification.')
            (root / 'launcher-result.json').write_text(json.dumps(dict(cosmicProbe=report), indent=2))
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try: child.wait(timeout=5)
                except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=5)


if __name__ == '__main__': run()
